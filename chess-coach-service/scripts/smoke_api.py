#!/usr/bin/env python3
import json
import os
import sys
import time
import urllib.error
import urllib.request

BASE = os.getenv("CHESS_COACH_URL", "http://127.0.0.1:8081") + "/api"
PGN = '''[Event "Smoke tactic"]
[Site "Local"]
[Date "2026.01.02"]
[Round "1"]
[White "Alice"]
[Black "Bob"]
[Result "1-0"]

1. e4 e5 2. Bc4 Nc6 3. Qh5 Nf6?? 4. Qxf7# 1-0
'''


def request(path, method="GET", body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method,
        headers={"Content-Type": "application/json"} if data else {})
    with urllib.request.urlopen(req, timeout=20) as response:
        return json.load(response)


def main(mode):
    if mode == "seed":
        settings = request("/settings")
        settings.update({"chesscom_username": "smoke-user", "analysis_depth": 8,
            "analysis_time_ms": 0, "inaccuracy_threshold": 40, "mistake_threshold": 80,
            "blunder_threshold": 120, "puzzle_threshold": 80, "ai_provider": "disabled",
            "ai_base_url": "", "ai_model": "", "ai_api_key": ""})
        saved = request("/settings", "PUT", settings)
        assert saved["chesscom_username"] == "smoke-user"
        imported = request("/games/import-pgn", "POST", {"pgn": PGN})
        assert imported["imported"] == 1
        game_id = imported["games"][0]["id"]
        request(f"/games/{game_id}/analysis", "POST")
        deadline = time.time() + 90
        while time.time() < deadline:
            game = request(f"/games/{game_id}")
            if game["analysis_status"] == "complete":
                break
            if game["analysis_status"] == "failed":
                raise AssertionError(game["analysis_error"])
            time.sleep(1)
        else:
            raise AssertionError("analysis timeout")
        assert game["analysis"] and game["puzzle_count"] >= 1
        puzzles = request("/puzzles")["items"]
        puzzle_id = puzzles[0]["id"]
        public = request(f"/puzzles/{puzzle_id}")
        assert "solution_uci" not in public
        assert request(f"/puzzles/{puzzle_id}/hint", "POST")["level"] == 1
        print(json.dumps({"game_id": game_id, "puzzle_id": puzzle_id, "moves": len(game["analysis"])}))
    elif mode == "verify":
        assert request("/settings")["chesscom_username"] == "smoke-user"
        games = request("/games")
        assert games["total"] >= 1
        game = request(f"/games/{games['items'][0]['id']}")
        assert game["analysis_status"] == "complete" and game["analysis"]
        assert request("/puzzles")["total"] >= 1
        print(json.dumps({"persisted_games": games["total"], "status": "pass"}))
    else:
        raise SystemExit("use seed or verify")


if __name__ == "__main__":
    main(sys.argv[1])
