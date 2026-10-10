import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from .models import ParsedGame, SettingsInput

DEFAULT_SETTINGS = SettingsInput().model_dump()


class Database:
    def __init__(self, path: str):
        self.path = path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def init(self):
        with self.connect() as db:
            db.executescript("""
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS games (
              id INTEGER PRIMARY KEY, source TEXT NOT NULL, source_key TEXT,
              pgn TEXT NOT NULL, event TEXT, site TEXT, played_at TEXT, white TEXT, black TEXT,
              result TEXT, ply_count INTEGER NOT NULL, analysis_status TEXT NOT NULL DEFAULT 'not_started',
              analysis_error TEXT, created_at TEXT NOT NULL,
              UNIQUE(source, source_key)
            );
            CREATE TABLE IF NOT EXISTS move_analysis (
              id INTEGER PRIMARY KEY, game_id INTEGER NOT NULL REFERENCES games(id) ON DELETE CASCADE,
              ply INTEGER NOT NULL, data TEXT NOT NULL, UNIQUE(game_id, ply)
            );
            CREATE TABLE IF NOT EXISTS puzzles (
              id INTEGER PRIMARY KEY, game_id INTEGER REFERENCES games(id) ON DELETE CASCADE,
              move_ply INTEGER NOT NULL, fen TEXT NOT NULL, solution_uci TEXT NOT NULL, solution_san TEXT NOT NULL,
              hint_level INTEGER NOT NULL DEFAULT 0, attempts INTEGER NOT NULL DEFAULT 0,
              solved INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS puzzle_attempts (
              id INTEGER PRIMARY KEY, puzzle_id INTEGER NOT NULL REFERENCES puzzles(id) ON DELETE CASCADE,
              move TEXT NOT NULL, correct INTEGER NOT NULL, created_at TEXT NOT NULL
            );
            """)
            for key, value in DEFAULT_SETTINGS.items():
                db.execute("INSERT OR IGNORE INTO settings(key,value) VALUES (?,?)", (key, json.dumps(value)))

    def get_settings(self, include_secret=False):
        with self.connect() as db:
            values = {row["key"]: json.loads(row["value"]) for row in db.execute("SELECT key,value FROM settings")}
        settings = DEFAULT_SETTINGS | values
        secret = settings.get("ai_api_key", "")
        if not include_secret:
            settings["ai_api_key"] = "********" if secret else ""
            settings["ai_api_key_configured"] = bool(secret)
        return settings

    def save_settings(self, settings: SettingsInput):
        values = settings.model_dump()
        if values["ai_api_key"] == "********":
            values["ai_api_key"] = self.get_settings(include_secret=True).get("ai_api_key", "")
        with self.connect() as db:
            for key, value in values.items():
                db.execute("INSERT INTO settings(key,value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, json.dumps(value)))
        return self.get_settings()

    def add_game(self, game: ParsedGame, source="upload", source_key=None):
        now = datetime.now(timezone.utc).isoformat()
        with self.connect() as db:
            cur = db.execute("""INSERT OR IGNORE INTO games
              (source,source_key,pgn,event,site,played_at,white,black,result,ply_count,created_at)
              VALUES (?,?,?,?,?,?,?,?,?,?,?)""", (source, source_key, game.pgn, game.event, game.site, game.played_at,
                game.white, game.black, game.result, game.ply_count, now))
            if cur.lastrowid:
                return cur.lastrowid
            row = db.execute("SELECT id FROM games WHERE source=? AND source_key=?", (source, source_key)).fetchone()
            return row["id"] if row else None

    @staticmethod
    def _game(row):
        return dict(row) if row else None

    def list_games(self):
        with self.connect() as db:
            rows = db.execute("SELECT id,source,event,site,played_at,white,black,result,ply_count,analysis_status,created_at FROM games ORDER BY id DESC").fetchall()
        return [dict(row) for row in rows]

    def get_game(self, game_id):
        with self.connect() as db:
            row = db.execute("SELECT * FROM games WHERE id=?", (game_id,)).fetchone()
            if not row:
                return None
            game = dict(row)
            analyses = db.execute("SELECT data FROM move_analysis WHERE game_id=? ORDER BY ply", (game_id,)).fetchall()
            game["analysis"] = [json.loads(r["data"]) for r in analyses]
            game["puzzle_count"] = db.execute("SELECT COUNT(*) n FROM puzzles WHERE game_id=?", (game_id,)).fetchone()["n"]
        return game

    def set_analysis_status(self, game_id, status, error=None):
        with self.connect() as db:
            db.execute("UPDATE games SET analysis_status=?, analysis_error=? WHERE id=?", (status, error, game_id))

    def save_analysis(self, game_id, rows, puzzles):
        with self.connect() as db:
            db.execute("DELETE FROM move_analysis WHERE game_id=?", (game_id,))
            db.execute("DELETE FROM puzzles WHERE game_id=?", (game_id,))
            db.executemany("INSERT INTO move_analysis(game_id,ply,data) VALUES (?,?,?)",
                           [(game_id, row["ply"], json.dumps(row)) for row in rows])
            now = datetime.now(timezone.utc).isoformat()
            db.executemany("INSERT INTO puzzles(game_id,move_ply,fen,solution_uci,solution_san,created_at) VALUES (?,?,?,?,?,?)",
                           [(game_id, p["move_ply"], p["fen"], p["solution_uci"], p["solution_san"], now) for p in puzzles])
            db.execute("UPDATE games SET analysis_status='complete', analysis_error=NULL WHERE id=?", (game_id,))

    def create_puzzle(self, game_id, move_ply, fen, solution_uci, solution_san):
        with self.connect() as db:
            cur = db.execute("INSERT INTO puzzles(game_id,move_ply,fen,solution_uci,solution_san,created_at) VALUES (?,?,?,?,?,?)",
                (game_id, move_ply, fen, solution_uci, solution_san, datetime.now(timezone.utc).isoformat()))
            return cur.lastrowid

    def list_puzzles(self):
        with self.connect() as db:
            rows = db.execute("SELECT id,game_id,move_ply,fen,hint_level,attempts,solved,created_at FROM puzzles ORDER BY id DESC").fetchall()
        return [dict(row) for row in rows]

    def get_puzzle(self, puzzle_id, secret=False):
        if secret:
            query = "SELECT * FROM puzzles WHERE id=?"
        else:
            query = "SELECT id,game_id,move_ply,fen,hint_level,attempts,solved,created_at FROM puzzles WHERE id=?"
        with self.connect() as db:
            row = db.execute(query, (puzzle_id,)).fetchone()
        return dict(row) if row else None

    def increment_hint(self, puzzle_id):
        with self.connect() as db:
            db.execute("UPDATE puzzles SET hint_level=MIN(hint_level+1,3) WHERE id=?", (puzzle_id,))
        return self.get_puzzle(puzzle_id, secret=True)

    def record_attempt(self, puzzle_id, move, correct):
        with self.connect() as db:
            db.execute("INSERT INTO puzzle_attempts(puzzle_id,move,correct,created_at) VALUES (?,?,?,?)",
                (puzzle_id, move, int(correct), datetime.now(timezone.utc).isoformat()))
            db.execute("UPDATE puzzles SET attempts=attempts+1, solved=MAX(solved,?) WHERE id=?", (int(correct), puzzle_id))
