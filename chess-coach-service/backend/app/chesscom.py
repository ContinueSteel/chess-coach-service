import re

import httpx


class ChessComClient:
    def __init__(self, http: httpx.AsyncClient):
        self.http = http
        self.headers = {"User-Agent": "ChessCoach/1.0 (single-user analysis app; contact: admin@example.invalid)"}

    async def fetch_recent(self, username: str, months: int) -> list[str]:
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,50}", username):
            raise ValueError("Invalid Chess.com username")
        url = f"https://api.chess.com/pub/player/{username}/games/archives"
        try:
            response = await self.http.get(url, headers=self.headers, timeout=15)
        except httpx.HTTPError as exc:
            raise ValueError(f"Chess.com request failed: {exc}") from exc
        if response.status_code == 404:
            raise ValueError(f"Chess.com player '{username}' was not found")
        if response.status_code != 200:
            raise ValueError(f"Chess.com returned HTTP {response.status_code}")
        try:
            body = response.json()
        except ValueError as exc:
            raise ValueError("Chess.com returned malformed archive data") from exc
        if not isinstance(body, dict) or not isinstance(body.get("archives"), list):
            raise ValueError("Chess.com returned malformed archive data")
        archives = [item for item in body["archives"] if isinstance(item, str) and item.startswith("https://api.chess.com/")][-months:]
        games: list[str] = []
        for archive in archives:
            try:
                month_response = await self.http.get(archive, headers=self.headers, timeout=20)
            except httpx.HTTPError as exc:
                raise ValueError(f"Chess.com archive request failed: {exc}") from exc
            if month_response.status_code != 200:
                raise ValueError(f"Chess.com archive returned HTTP {month_response.status_code}")
            try:
                month_body = month_response.json()
            except ValueError as exc:
                raise ValueError("Chess.com returned malformed game data") from exc
            records = month_body.get("games", []) if isinstance(month_body, dict) else []
            if not isinstance(records, list):
                raise ValueError("Chess.com returned malformed game data")
            for game in records:
                pgn = game.get("pgn") if isinstance(game, dict) else None
                if isinstance(pgn, str) and pgn.strip():
                    games.append(pgn)
        return games
