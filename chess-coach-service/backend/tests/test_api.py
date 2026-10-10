import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import create_app

PGN = '''[Event "Scholar"]
[Site "Local"]
[Date "2026.01.02"]
[Round "1"]
[White "Alice"]
[Black "Bob"]
[Result "1-0"]

1. e4 e5 2. Bc4 Nc6 3. Qh5 Nf6?? 4. Qxf7# 1-0
'''


@pytest.fixture
def client(tmp_path: Path):
    app = create_app(str(tmp_path / "test.db"), run_jobs_inline=True, engine_factory=lambda: None)
    with TestClient(app) as c:
        yield c


def test_health_root_ready(client):
    assert client.get("/").status_code == 200
    assert client.get("/health").json()["status"] == "ok"
    assert client.get("/ready").json()["status"] == "ready"


def test_settings_round_trip_masks_secret(client):
    payload = {"chesscom_username": "Hikaru", "analysis_depth": 10, "analysis_time_ms": 100,
        "inaccuracy_threshold": 55, "mistake_threshold": 110, "blunder_threshold": 220,
        "puzzle_threshold": 170, "ai_provider": "openai-compatible", "ai_base_url": "https://example.com/v1",
        "ai_model": "model-x", "ai_api_key": "super-secret"}
    assert client.put("/settings", json=payload).status_code == 200
    got = client.get("/settings").json()
    assert got["chesscom_username"] == "Hikaru"
    assert got["ai_api_key"] == "********"
    assert got["ai_api_key_configured"] is True
    assert "super-secret" not in str(got)
    got["analysis_depth"] = 11
    assert client.put("/settings", json=got).status_code == 200
    assert client.app.state.db.get_settings(include_secret=True)["ai_api_key"] == "super-secret"
    got["ai_api_key"] = ""
    assert client.put("/settings", json=got).status_code == 200
    assert client.app.state.db.get_settings(include_secret=True)["ai_api_key"] == "super-secret"


def test_docs_use_proxy_prefixed_openapi_url(client):
    docs = client.get("/docs")
    assert docs.status_code == 200
    assert "'/api/openapi.json'" in docs.text or '"/api/openapi.json"' in docs.text


def test_interrupted_analysis_is_recoverable_after_restart(tmp_path: Path):
    path = str(tmp_path / "restart.db")
    first = create_app(path, run_jobs_inline=True, engine_factory=lambda: None)
    with TestClient(first) as c:
        game_id = c.post("/games/import-pgn", json={"pgn": PGN}).json()["games"][0]["id"]
        first.state.db.set_analysis_status(game_id, "running")
    second = create_app(path, run_jobs_inline=True, engine_factory=lambda: None)
    with TestClient(second) as c:
        assert c.get(f"/games/{game_id}").json()["analysis_status"] == "not_started"


def test_ingest_list_detail_and_invalid_input(client):
    created = client.post("/games/import-pgn", json={"pgn": PGN}).json()
    assert created["imported"] == 1
    game_id = created["games"][0]["id"]
    assert client.get("/games").json()["items"][0]["id"] == game_id
    assert client.get(f"/games/{game_id}").json()["white"] == "Alice"
    bad = client.post("/games/import-pgn", json={"pgn": "garbage"})
    assert bad.status_code == 422
    assert bad.json()["error"]["code"] == "invalid_pgn"


def test_upload_request_limit(client):
    response = client.post("/games/upload", files={"file": ("x.pgn", b"x" * 2_000_001, "application/x-chess-pgn")})
    assert response.status_code == 413


def test_invalid_fen_and_missing_game_are_structured(client):
    missing = client.get("/games/9999")
    assert missing.status_code == 404 and missing.json()["error"]["code"] == "not_found"
    bad = client.post("/positions/validate", json={"fen": "nope", "move": "e2e4"})
    assert bad.status_code == 422
