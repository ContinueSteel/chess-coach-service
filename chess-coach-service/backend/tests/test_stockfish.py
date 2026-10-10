import os
import shutil

import chess
import chess.engine
import pytest

from app.analysis import mover_score

ENGINE = os.getenv("STOCKFISH_PATH", "/usr/games/stockfish")


@pytest.mark.skipif(not os.path.exists(ENGINE) and not shutil.which(ENGINE), reason="Stockfish not installed")
def test_stockfish_known_mate_and_side_normalization():
    engine = chess.engine.SimpleEngine.popen_uci(ENGINE)
    try:
        board = chess.Board("7k/5Q2/6K1/8/8/8/8/8 w - - 0 1")
        info = engine.analyse(board, chess.engine.Limit(depth=10))
        assert mover_score(info["score"], board.turn) > 90000
        black = chess.Board("7K/5q2/6k1/8/8/8/8/8 b - - 0 1")
        info2 = engine.analyse(black, chess.engine.Limit(depth=10))
        assert mover_score(info2["score"], black.turn) > 90000
    finally:
        engine.quit()
