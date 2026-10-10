"""FastAPI entry point for Chess Coach service.

Features:
- Import games from Chess.com for a given username (public API only).
- Accept uploaded PGN (OTB games) via POST.
- Analyse games with Stockfish to detect blunders, brilliant moves and generate puzzles.
- Use OpenAI LLM to produce natural‑language coaching commentary.

Environment variables:
- STOCKFISH_PATH (default: "stockfish") – path to the Stockfish binary.
- OPENAI_API_KEY – OpenAI key for LLM generation.
- CHESS_COM_USERNAME – optional default Chess.com username.
"""

import os
import json
import io
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import chess
import chess.pgn
import subprocess
import httpx

app = FastAPI(title="Chess Coach Service")

STOCKFISH_PATH = os.getenv("STOCKFISH_PATH", "stockfish")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
CHESS_COM_USERNAME = os.getenv("CHESS_COM_USERNAME")

if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY environment variable must be set")

# Helper to run Stockfish evaluation for a board position
def eval_position(board: chess.Board) -> int:
    """Return centipawn evaluation from White's perspective.
    Positive = White advantage, negative = Black advantage.
    """
    # Run Stockfish synchronously for simplicity
    try:
        proc = subprocess.run(
            [STOCKFISH_PATH],
            input="\n".join([
                f"position fen {board.fen()}",
                "go depth 15",
                "quit",
            ]) + "\n",
            capture_output=True,
            text=True,
            timeout=20,
        )
    except Exception as e:
        raise RuntimeError(f"Stockfish execution failed: {e}")
    stdout = proc.stdout
    # Parse last "score cp" line
    score = 0
    for line in stdout.splitlines():
        if line.startswith("info depth") and "score cp" in line:
            parts = line.split()
            if "cp" in parts:
                idx = parts.index("cp")
                try:
                    score = int(parts[idx + 1])
                except ValueError:
                    pass
    return score

# Simple model for analysis result
class MoveAnalysis(BaseModel):
    move_number: int
    san: str
    eval_before: int
    eval_after: int
    delta: int
    type: str  # blunder, brilliant, normal
    commentary: str = None

class GameAnalysis(BaseModel):
    game_id: str
    moves: list[MoveAnalysis]
    puzzles: list[dict]  # positions where a puzzle can be generated

# LLM helper
async def generate_commentary(prompt: str) -> str:
    import openai
    openai.api_key = OPENAI_API_KEY
    response = await openai.ChatCompletion.acreate(
        model="gpt-4o-mini",
        messages=[{"role": "system", "content": "You are a helpful chess coach. Explain the position in simple terms for an intermediate player."},
                  {"role": "user", "content": prompt}],
        temperature=0.7,
    )
    return response.choices[0].message.content.strip()

# Endpoint to import Chess.com games (public API only)
@app.get("/import/chesscom/{username}")
async def import_chesscom(username: str):
    url = f"https://api.chess.com/pub/player/{username}/games"
    async with httpx.AsyncClient() as client:
        r = await client.get(url)
    if r.status_code != 200:
        raise HTTPException(status_code=404, detail="User or games not found")
    data = r.json()
    games = []
    for game in data.get("games", []):
        if "pgn" in game:
            games.append(game["pgn"])
    return {"username": username, "games_retrieved": len(games), "pgns": games}

# Endpoint to upload OTB PGN file
@app.post("/upload")
async def upload_pgn(file: UploadFile = File(...)):
    content = await file.read()
    pgns = content.decode()
    # Assume possibly multiple games concatenated; split on blank lines
    pgns_list = [p.strip() for p in pgns.split("\n\n\n") if p.strip()]
    return {"games_uploaded": len(pgns_list)}

# Core analysis endpoint – expects a PGN string in body
class AnalyzeRequest(BaseModel):
    pgn: str
    game_id: str | None = None

@app.post("/analyse")
async def analyse_game(req: AnalyzeRequest):
    pgn_io = io.StringIO(req.pgn)
    game = chess.pgn.read_game(pgn_io)
    if game is None:
        raise HTTPException(status_code=400, detail="Invalid PGN")
    board = game.board()
    moves_analysis = []
    move_number = 1
    for node in game.mainline():
        san = node.san()
        eval_before = await eval_position(board)
        board.push(node.move)
        eval_after = await eval_position(board)
        delta = eval_after - eval_before
        move_type = "normal"
        if delta <= -200:
            move_type = "blunder"
        elif delta >= 200:
            move_type = "brilliant"
        # Build simple prompt for LLM
        prompt = f"Explain why the move {san} on move {move_number} was a {move_type}. Before move evaluation: {eval_before} centipawns, after: {eval_after}."
        commentary = await generate_commentary(prompt)
        moves_analysis.append(
            MoveAnalysis(
                move_number=move_number,
                san=san,
                eval_before=eval_before,
                eval_after=eval_after,
                delta=delta,
                type=move_type,
                commentary=commentary,
            )
        )
        move_number += 1
    # Simple puzzle generation – positions where delta >= 300 (missed tactic)
    puzzles = []
    # Not implemented in depth – placeholder list
    return GameAnalysis(
        game_id=req.game_id or "unknown",
        moves=moves_analysis,
        puzzles=puzzles,
    )

# Health check
@app.get("/health")
async def health():
    return {"status": "ok"}
