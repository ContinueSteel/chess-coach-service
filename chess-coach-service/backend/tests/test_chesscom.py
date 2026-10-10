import httpx
import pytest

from app.chesscom import ChessComClient
from app.main import create_app


@pytest.mark.asyncio
async def test_archive_import_uses_recent_bounded_months_and_user_agent():
    seen = []
    def handler(request):
        seen.append(request)
        if request.url.path.endswith('/archives'):
            return httpx.Response(200, json={"archives": [
                "https://api.chess.com/pub/player/test/games/2025/01",
                "https://api.chess.com/pub/player/test/games/2025/02"]})
        return httpx.Response(200, json={"games": [{"pgn": '[Event "T"]\n[Result "*"]\n\n1. e4 *'}]})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        games = await ChessComClient(http).fetch_recent("test", months=1)
    assert len(games) == 1
    assert seen[-1].url.path.endswith('/2025/02')
    assert "ChessCoach" in seen[0].headers["user-agent"]


@pytest.mark.asyncio
async def test_archive_errors_are_useful():
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(404))) as http:
        with pytest.raises(ValueError, match="not found"):
            await ChessComClient(http).fetch_recent("missing", months=1)


def test_chesscom_source_key_is_stable_when_archive_range_expands(tmp_path):
    app = create_app(str(tmp_path / "dedupe.db"), run_jobs_inline=True, engine_factory=lambda: None)
    app.state.db.init()
    from app.pgn import parse_pgn_games
    parsed = parse_pgn_games('[Event "Recent"]\n[Result "*"]\n\n1. e4 *')[0]
    import hashlib
    digest = hashlib.sha256(parsed.pgn.encode()).hexdigest()
    first = app.state.db.add_game(parsed, source="chess.com", source_key=f"player:{digest}")
    second = app.state.db.add_game(parsed, source="chess.com", source_key=f"player:{digest}")
    assert first == second
    assert len(app.state.db.list_games()) == 1
