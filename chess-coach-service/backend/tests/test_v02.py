import asyncio
import json
import sqlite3
import threading
from pathlib import Path

import chess
import chess.engine
import httpx
import pytest
from fastapi.testclient import TestClient

from app.ai import improve_commentary
from app.database import Database
from app.main import create_app
from app.models import SettingsInput
from app.pgn import parse_pgn_games

PGN = '''[Event "Training"]
[Site "Local"]
[Date "2026.01.02"]
[White "Alice"]
[Black "Bob"]
[Result "*"]

1. e4 e5 2. Nf3 Nc6 *
'''

class PredictableEngine:
    def analyse(self, board, limit):
        copy = board.copy()
        pv = []
        for _ in range(4):
            moves = list(copy.legal_moves)
            if not moves:
                break
            move = moves[0]
            pv.append(move)
            copy.push(move)
        return {"score": chess.engine.PovScore(chess.engine.Cp(40), board.turn), "pv": pv}
    def quit(self):
        pass


def test_ai_null_empty_and_malformed_content_falls_back(monkeypatch):
    row = {"coach": "fallback", "san": "e4", "classification": "good", "loss_cp": 10,
           "best_move_san": "e4", "pv": ["e4", "e5"]}
    settings = {"ai_provider": "openai-compatible", "ai_base_url": "https://model.test/v1",
                "ai_model": "coach", "ai_api_key": ""}

    async def run(body):
        transport = httpx.MockTransport(lambda request: httpx.Response(200, json=body))
        class Client(httpx.AsyncClient):
            def __init__(self, *args, **kwargs):
                super().__init__(transport=transport)
        monkeypatch.setattr("app.ai.httpx.AsyncClient", Client)
        return await improve_commentary(settings, row)

    for body in ({"choices": [{"message": {"content": None}}]},
                 {"choices": [{"message": {"content": "   "}}]},
                 {"choices": "wrong"}, {}):
        assert asyncio.run(run(body)) == "fallback"


def test_ai_invalid_base_url_falls_back_without_request():
    row = {"coach": "safe"}
    settings = {"ai_provider": "openai-compatible", "ai_base_url": "file:///secret",
                "ai_model": "x", "ai_api_key": ""}
    assert asyncio.run(improve_commentary(settings, row)) == "safe"


def test_v01_database_migrates_idempotently(tmp_path):
    path = tmp_path / "old.db"
    with sqlite3.connect(path) as db:
        db.executescript('''
          CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
          CREATE TABLE games (id INTEGER PRIMARY KEY, source TEXT NOT NULL, source_key TEXT,
            pgn TEXT NOT NULL, event TEXT, site TEXT, played_at TEXT, white TEXT, black TEXT,
            result TEXT, ply_count INTEGER NOT NULL, analysis_status TEXT NOT NULL DEFAULT 'not_started',
            analysis_error TEXT, created_at TEXT NOT NULL, UNIQUE(source, source_key));
          CREATE TABLE move_analysis (id INTEGER PRIMARY KEY, game_id INTEGER NOT NULL REFERENCES games(id) ON DELETE CASCADE,
            ply INTEGER NOT NULL, data TEXT NOT NULL, UNIQUE(game_id, ply));
          CREATE TABLE puzzles (id INTEGER PRIMARY KEY, game_id INTEGER REFERENCES games(id) ON DELETE CASCADE,
            move_ply INTEGER NOT NULL, fen TEXT NOT NULL, solution_uci TEXT NOT NULL, solution_san TEXT NOT NULL,
            hint_level INTEGER NOT NULL DEFAULT 0, attempts INTEGER NOT NULL DEFAULT 0, solved INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL);
          CREATE TABLE puzzle_attempts (id INTEGER PRIMARY KEY, puzzle_id INTEGER NOT NULL REFERENCES puzzles(id) ON DELETE CASCADE,
            move TEXT NOT NULL, correct INTEGER NOT NULL, created_at TEXT NOT NULL);
        ''')
    database = Database(str(path))
    database.init(); database.init()
    with database.connect() as db:
        columns = {row[1] for row in db.execute("PRAGMA table_info(games)")}
        assert "player_color" in columns
        assert db.execute("PRAGMA user_version").fetchone()[0] == 2
        assert db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='coach_messages'").fetchone()


def test_v02_settings_round_trip():
    settings = SettingsInput(coach_level="advanced", board_theme="blue", piece_set="alpha",
        show_coordinates=False, orientation_mode="black", move_sounds_enabled=False, sound_volume=0.25)
    data = settings.model_dump()
    assert data["coach_level"] == "advanced" and data["sound_volume"] == 0.25


def test_delete_cascades_and_late_worker_cannot_resurrect(tmp_path):
    app = create_app(str(tmp_path / "delete.db"), run_jobs_inline=True, engine_factory=PredictableEngine)
    with TestClient(app) as client:
        game_id = client.post("/games/import-pgn", json={"pgn": PGN}).json()["games"][0]["id"]
        parsed = parse_pgn_games(PGN)[0]
        app.state.db.save_analysis(game_id, [{"ply": 1, "x": 1}], [{"move_ply": 1, "fen": parsed.game.board().fen(), "solution_uci": "e2e4", "solution_san": "e4"}])
        assert client.delete(f"/games/{game_id}").status_code == 204
        assert client.get(f"/games/{game_id}").status_code == 404
        assert app.state.db.save_analysis(game_id, [{"ply": 1}], []) is False
        with app.state.db.connect() as db:
            assert db.execute("SELECT COUNT(*) FROM move_analysis WHERE game_id=?", (game_id,)).fetchone()[0] == 0
            assert db.execute("SELECT COUNT(*) FROM puzzles WHERE game_id=?", (game_id,)).fetchone()[0] == 0


def test_player_color_inference_and_manual_override(tmp_path):
    app = create_app(str(tmp_path / "color.db"), run_jobs_inline=True, engine_factory=PredictableEngine)
    app.state.db.init()
    parsed = parse_pgn_games(PGN)[0]
    gid = app.state.db.add_game(parsed, source="chess.com", source_key="alice:1", player_color="white")
    with TestClient(app) as client:
        assert client.get(f"/games/{gid}").json()["player_color"] == "white"
        changed = client.patch(f"/games/{gid}/orientation", json={"player_color": "black"})
        assert changed.json()["player_color"] == "black"
        assert client.patch(f"/games/{gid}/orientation", json={"player_color": "sideways"}).status_code == 422


def test_analysis_has_legal_explicit_engine_cues_and_fullmove_fields():
    parsed = parse_pgn_games(PGN)[0]
    from app.analysis import analyse_game
    from app.models import Thresholds
    rows, _ = analyse_game(parsed.game, PredictableEngine(), 8, 0, Thresholds())
    assert rows[0]["move_number"] == 1 and rows[0]["color"] == "white"
    assert rows[1]["move_number"] == 1 and rows[1]["color"] == "black"
    cues = rows[0]["cues"]
    assert [cue["kind"] for cue in cues] == ["best", "response", "continuation"]
    assert [cue["label"] for cue in cues] == ["Best", "Expected reply", "Continuation"]
    assert all("threat" not in cue["label"].lower() for cue in cues)
    board = chess.Board(rows[0]["fen_before"])
    for cue in cues:
        move = chess.Move.from_uci(cue["uci"])
        assert move in board.legal_moves
        board.push(move)


def test_trial_valid_invalid_and_nonmutating(tmp_path):
    app = create_app(str(tmp_path / "trial.db"), run_jobs_inline=True, engine_factory=PredictableEngine)
    with TestClient(app) as client:
        fen = chess.Board().fen()
        before = client.get("/games").json()["total"]
        response = client.post("/positions/evaluate-trial", json={"fen": fen, "move": "e2e4", "coach_level": "beginner"})
        assert response.status_code == 200
        body = response.json()
        assert body["move_uci"] == "e2e4" and body["classification"] in {"best", "great", "good", "inaccuracy", "mistake", "blunder"}
        assert body["feedback"].startswith(("Nice", "Good", "Let's", "That"))
        assert client.get("/games").json()["total"] == before
        assert client.post("/positions/evaluate-trial", json={"fen": fen, "move": "e2e5", "coach_level": "advanced"}).status_code == 422
        promotion_fen = "8/P7/8/8/8/8/7k/5K2 w - - 0 1"
        promoted = client.post("/positions/evaluate-trial", json={"fen": promotion_fen, "move": "a7a8q", "coach_level": "intermediate"})
        assert promoted.status_code == 200
        assert promoted.json()["move_uci"] == "a7a8q"


def test_chat_disabled_and_context_is_server_derived(tmp_path, monkeypatch):
    app = create_app(str(tmp_path / "chat.db"), run_jobs_inline=True, engine_factory=PredictableEngine)
    with TestClient(app) as client:
        gid = client.post("/games/import-pgn", json={"pgn": PGN}).json()["games"][0]["id"]
        disabled = client.post(f"/games/{gid}/chat", json={"ply": 0, "question": "What is the plan?"})
        assert disabled.status_code == 503 and disabled.json()["error"]["code"] == "chat_unavailable"
        assert client.post(f"/games/{gid}/chat", json={"ply": 0, "question": "x" * 1001}).status_code == 422


def test_hint_names_file_and_side_to_move(tmp_path):
    app = create_app(str(tmp_path / "hint.db"), run_jobs_inline=True, engine_factory=PredictableEngine)
    with TestClient(app) as client:
        pid = app.state.db.create_puzzle(None, 1, chess.Board().fen(), "g1f3", "Nf3")
        h1 = client.post(f"/puzzles/{pid}/hint").json()["hint"]
        h2 = client.post(f"/puzzles/{pid}/hint").json()["hint"]
        assert "White to move" in h1
        assert "f-file" in h2 and "7 file" not in h2


def test_full_analysis_completes_when_ai_returns_null(tmp_path, monkeypatch):
    app = create_app(str(tmp_path / "complete.db"), run_jobs_inline=True, engine_factory=PredictableEngine)
    with TestClient(app) as client:
        settings = client.get("/settings").json()
        settings.update({"ai_provider": "openai-compatible", "ai_base_url": "https://model.test/v1", "ai_model": "x"})
        client.put("/settings", json=settings)
        async def fallback(settings, row):
            return row["coach"]
        monkeypatch.setattr("app.main.improve_commentary", fallback)
        gid = client.post("/games/import-pgn", json={"pgn": PGN}).json()["games"][0]["id"]
        client.post(f"/games/{gid}/analysis")
        game = client.get(f"/games/{gid}").json()
        assert game["analysis_status"] == "complete", game.get("analysis_error")
        assert len(game["analysis"]) == 4
