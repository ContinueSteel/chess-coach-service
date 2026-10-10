from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app


def test_puzzle_does_not_leak_answer_and_tracks_hints_attempts(tmp_path: Path):
    app = create_app(str(tmp_path / "p.db"), run_jobs_inline=True, engine_factory=lambda: None)
    with TestClient(app) as client:
        puzzle_id = app.state.db.create_puzzle(game_id=None, move_ply=1,
            fen="7k/6pp/8/8/8/8/6PP/6RK w - - 0 1", solution_uci="g1f1", solution_san="Rf1")
        puzzle = client.get(f"/puzzles/{puzzle_id}").json()
        assert "solution_uci" not in puzzle and "solution_san" not in puzzle
        h1 = client.post(f"/puzzles/{puzzle_id}/hint").json()
        h2 = client.post(f"/puzzles/{puzzle_id}/hint").json()
        assert h1["level"] == 1 and h2["level"] == 2
        illegal = client.post(f"/puzzles/{puzzle_id}/attempt", json={"move": "a1a8"})
        assert illegal.status_code == 422
        wrong = client.post(f"/puzzles/{puzzle_id}/attempt", json={"move": "g2g3"}).json()
        assert wrong["correct"] is False and "solution" not in wrong
        right = client.post(f"/puzzles/{puzzle_id}/attempt", json={"move": "g1f1"}).json()
        assert right == {"correct": True, "solution": "Rf1"}
        assert client.get(f"/puzzles/{puzzle_id}").json()["attempts"] == 2
