import chess
import pytest

from app.analysis import classify_loss, mover_score, analyse_game
from app.models import Thresholds
from app.pgn import parse_pgn_games


T = Thresholds(inaccuracy=50, mistake=100, blunder=200, puzzle=150)


@pytest.mark.parametrize(("loss", "label"), [(0, "best"), (10, "great"), (49, "good"), (50, "inaccuracy"), (100, "mistake"), (200, "blunder")])
def test_classification_thresholds(loss, label):
    assert classify_loss(loss, T) == label


def test_mover_score_normalizes_black_and_mate():
    assert mover_score(chess.engine.PovScore(chess.engine.Cp(120), chess.WHITE), chess.WHITE) == 120
    assert mover_score(chess.engine.PovScore(chess.engine.Cp(120), chess.WHITE), chess.BLACK) == -120
    assert mover_score(chess.engine.PovScore(chess.engine.Mate(2), chess.WHITE), chess.WHITE) == 100000
    assert mover_score(chess.engine.PovScore(chess.engine.Mate(2), chess.WHITE), chess.BLACK) == -100000


class FakeEngine:
    def analyse(self, board, limit):
        legal = list(board.legal_moves)
        score = 100 if board.turn == chess.WHITE else -100
        return {"score": chess.engine.PovScore(chess.engine.Cp(score), chess.WHITE), "pv": legal[:3]}


def test_analysis_keeps_pre_mistake_fen_for_puzzles():
    parsed = parse_pgn_games('''[Event "T"]\n[Result "*"]\n\n1. e4 e5 2. Nf3 *''')[0]
    rows, puzzles = analyse_game(parsed.game, FakeEngine(), depth=8, time_ms=0, thresholds=Thresholds(1, 2, 3, 1))
    assert rows
    assert puzzles
    board = parsed.game.board()
    assert puzzles[0]["fen"] == board.fen()
    assert "solution_uci" in puzzles[0]


def test_real_stockfish_start_position_and_mate_when_available():
    import os
    path = os.getenv("STOCKFISH_PATH", "/usr/games/stockfish")
    if not os.path.exists(path):
        pytest.skip("Stockfish not installed")
    engine = chess.engine.SimpleEngine.popen_uci(path)
    try:
        info = engine.analyse(chess.Board(), chess.engine.Limit(depth=8))
        assert info["pv"][0] in chess.Board().legal_moves
        mate = chess.Board("7k/5Q2/6K1/8/8/8/8/8 w - - 0 1")
        assert mover_score(engine.analyse(mate, chess.engine.Limit(depth=8))["score"], mate.turn) > 90000
    finally:
        engine.quit()
