import asyncio
import hashlib
import io
import os
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager

import chess
import chess.engine
import httpx
from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, RedirectResponse

from .analysis import analyse_game
from .ai import improve_commentary
from .chesscom import ChessComClient
from .database import Database
from .models import ChessComImport, MoveInput, PgnInput, PositionMove, SettingsInput, Thresholds
from .pgn import parse_pgn_games

MAX_UPLOAD = 2_000_000


def error(status: int, code: str, message: str):
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message}})


def create_app(db_path: str | None = None, run_jobs_inline: bool = False, engine_factory=None):
    path = db_path or os.getenv("DATABASE_PATH", "./data/chess-coach.db")
    database = Database(path)
    executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="chess-analysis")
    stockfish_path = os.getenv("STOCKFISH_PATH", "/usr/games/stockfish")
    make_engine = engine_factory or (lambda: chess.engine.SimpleEngine.popen_uci(stockfish_path))

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        database.init()
        database.recover_interrupted_analyses()
        yield
        executor.shutdown(wait=False, cancel_futures=True)

    application = FastAPI(
        title="Chess Coach API",
        version="1.0.0",
        lifespan=lifespan,
        root_path="/api",
    )
    application.state.db = database

    @application.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, exc: RequestValidationError):
        return error(422, "invalid_request", exc.errors()[0].get("msg", "Invalid request"))

    @application.exception_handler(HTTPException)
    async def http_error_handler(request: Request, exc: HTTPException):
        if isinstance(exc.detail, dict) and "code" in exc.detail:
            detail = exc.detail
            return error(exc.status_code, str(detail["code"]), str(detail["message"]))
        return error(exc.status_code, "http_error", str(exc.detail))

    @application.get("/", include_in_schema=False)
    def root():
        return {"name": "Chess Coach API", "docs": "/docs", "health": "/health"}

    @application.get("/health")
    def health():
        return {"status": "ok"}

    @application.get("/ready")
    def ready():
        try:
            database.init()
            with database.connect() as db:
                db.execute("SELECT 1").fetchone()
            return {"status": "ready"}
        except sqlite3.Error as exc:  # pragma: no cover
            return error(503, "database_unavailable", str(exc))

    @application.get("/settings")
    def get_settings():
        return database.get_settings()

    @application.put("/settings")
    def put_settings(settings: SettingsInput):
        return database.save_settings(settings)

    def import_text(text: str, source: str, source_prefix: str = ""):
        try:
            games = parse_pgn_games(text)
        except (ValueError, UnicodeError) as exc:
            raise HTTPException(422, {"code": "invalid_pgn", "message": str(exc)}) from exc
        added = []
        for index, game in enumerate(games):
            digest = hashlib.sha256(game.pgn.encode()).hexdigest()
            source_key = f"{source_prefix}:{index}:{digest}" if source_prefix else None
            game_id = database.add_game(game, source=source, source_key=source_key)
            if game_id:
                added.append({"id": game_id, "white": game.white, "black": game.black, "result": game.result})
        return {"imported": len(added), "games": added}

    @application.post("/games/import-pgn", status_code=201)
    def import_pgn(payload: PgnInput):
        return import_text(payload.pgn, "paste")

    @application.post("/games/upload", status_code=201)
    async def upload_pgn(file: UploadFile = File(...)):
        body = await file.read(MAX_UPLOAD + 1)
        if len(body) > MAX_UPLOAD:
            raise HTTPException(413, {"code": "too_large", "message": "PGN upload exceeds 2 MB"})
        try:
            return import_text(body.decode("utf-8"), "upload")
        except UnicodeDecodeError as exc:
            raise HTTPException(422, {"code": "invalid_pgn", "message": "PGN must be UTF-8 text"}) from exc

    @application.post("/games/import-chesscom", status_code=201)
    async def import_chesscom(payload: ChessComImport):
        async with httpx.AsyncClient() as client:
            try:
                pgns = await ChessComClient(client).fetch_recent(payload.username, payload.months)
            except ValueError as exc:
                raise HTTPException(502, {"code": "chesscom_error", "message": str(exc)}) from exc
        imported = []
        rejected = 0
        for pgn in pgns:
            try:
                result = import_text(pgn, "chess.com", payload.username.lower())
                imported.extend(result["games"])
            except HTTPException:
                rejected += 1
        return {"imported": len(imported), "rejected": rejected, "games": imported}

    @application.get("/games")
    def list_games():
        items = database.list_games()
        return {"items": items, "total": len(items)}

    @application.get("/games/{game_id}")
    def get_game(game_id: int):
        game = database.get_game(game_id)
        if not game:
            raise HTTPException(404, {"code": "not_found", "message": "Game not found"})
        return game

    def run_analysis(game_id: int):
        game_row = database.get_game(game_id)
        if not game_row:
            return
        database.set_analysis_status(game_id, "running")
        engine = None
        try:
            game = parse_pgn_games(game_row["pgn"])[0].game
            settings = database.get_settings(include_secret=True)
            thresholds = Thresholds(inaccuracy=settings["inaccuracy_threshold"], mistake=settings["mistake_threshold"],
                blunder=settings["blunder_threshold"], puzzle=settings["puzzle_threshold"])
            engine = make_engine()
            if engine is None:
                raise RuntimeError("Stockfish engine is unavailable")
            rows, puzzles = analyse_game(game, engine, settings["analysis_depth"], settings["analysis_time_ms"], thresholds)
            if settings["ai_provider"] != "disabled":
                async def add_ai_notes():
                    candidates = [row for row in rows if row["classification"] in ("inaccuracy", "mistake", "blunder")][:10]
                    notes = await asyncio.gather(*(improve_commentary(settings, row) for row in candidates))
                    for row, note in zip(candidates, notes):
                        row["coach"] = note
                asyncio.run(add_ai_notes())
            database.save_analysis(game_id, rows, puzzles)
        except Exception as exc:
            database.set_analysis_status(game_id, "failed", str(exc)[:500])
        finally:
            if engine is not None:
                try:
                    engine.quit()
                except Exception:
                    pass

    @application.post("/games/{game_id}/analysis", status_code=202)
    async def start_analysis(game_id: int):
        game = database.get_game(game_id)
        if not game:
            raise HTTPException(404, {"code": "not_found", "message": "Game not found"})
        if game["analysis_status"] in ("queued", "running"):
            return {"status": game["analysis_status"]}
        database.set_analysis_status(game_id, "queued")
        if run_jobs_inline:
            run_analysis(game_id)
        else:
            asyncio.get_running_loop().run_in_executor(executor, run_analysis, game_id)
        return {"status": database.get_game(game_id)["analysis_status"]}

    @application.get("/puzzles")
    def list_puzzles():
        items = database.list_puzzles()
        return {"items": items, "total": len(items)}

    @application.get("/puzzles/{puzzle_id}")
    def get_puzzle(puzzle_id: int):
        puzzle = database.get_puzzle(puzzle_id)
        if not puzzle:
            raise HTTPException(404, {"code": "not_found", "message": "Puzzle not found"})
        return puzzle

    @application.post("/puzzles/{puzzle_id}/hint")
    def puzzle_hint(puzzle_id: int):
        puzzle = database.get_puzzle(puzzle_id, secret=True)
        if not puzzle:
            raise HTTPException(404, {"code": "not_found", "message": "Puzzle not found"})
        updated = database.increment_hint(puzzle_id)
        level = updated["hint_level"]
        move = chess.Move.from_uci(updated["solution_uci"])
        hints = [f"Look for a move with the piece on {chess.square_name(move.from_square)}.",
                 f"The destination square is on the {chess.square_file(move.to_square) + 1} file.",
                 f"The move is {updated['solution_san']}." ]
        return {"level": level, "hint": hints[level - 1]}

    @application.post("/puzzles/{puzzle_id}/attempt")
    def puzzle_attempt(puzzle_id: int, payload: MoveInput):
        puzzle = database.get_puzzle(puzzle_id, secret=True)
        if not puzzle:
            raise HTTPException(404, {"code": "not_found", "message": "Puzzle not found"})
        board = chess.Board(puzzle["fen"])
        try:
            move = board.parse_uci(payload.move) if len(payload.move) in (4, 5) else board.parse_san(payload.move)
        except ValueError as exc:
            raise HTTPException(422, {"code": "illegal_move", "message": "Move is not legal in this position"}) from exc
        correct = move.uci() == puzzle["solution_uci"]
        database.record_attempt(puzzle_id, move.uci(), correct)
        result = {"correct": correct}
        if correct:
            result["solution"] = puzzle["solution_san"]
        return result

    @application.post("/positions/validate")
    def validate_position(payload: PositionMove):
        try:
            board = chess.Board(payload.fen)
            move = board.parse_uci(payload.move) if len(payload.move) in (4, 5) else board.parse_san(payload.move)
        except ValueError as exc:
            raise HTTPException(422, {"code": "invalid_position", "message": str(exc)}) from exc
        return {"legal": move in board.legal_moves, "uci": move.uci()}

    return application


app = create_app()
