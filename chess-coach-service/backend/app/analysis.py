import chess
import chess.engine

from .models import Thresholds

MATE_SCORE = 100_000


def mover_score(score: chess.engine.PovScore, mover: chess.Color) -> int:
    pov = score.pov(mover)
    if pov.is_mate():
        mate = pov.mate()
        return MATE_SCORE if mate is not None and mate > 0 else -MATE_SCORE
    value = pov.score()
    return int(value if value is not None else 0)


def score_after_move(score: chess.engine.PovScore, mover: chess.Color, board: chess.Board) -> int:
    """Return the post-move score from the mover's perspective.

    UCI reports a terminal checkmate as Mate(0) for the losing side to move.
    python-chess cannot infer that the requested POV delivered the mate, so
    handle the terminal board explicitly before normal POV conversion.
    """
    if board.is_checkmate():
        return MATE_SCORE if board.turn != mover else -MATE_SCORE
    return mover_score(score, mover)


def classify_loss(loss: int, thresholds: Thresholds) -> str:
    if loss <= 0:
        return "best"
    if loss < 20:
        return "great"
    if loss < thresholds.inaccuracy:
        return "good"
    if loss < thresholds.mistake:
        return "inaccuracy"
    if loss < thresholds.blunder:
        return "mistake"
    return "blunder"


def _pv_san(board: chess.Board, pv: list[chess.Move], maximum: int = 5) -> list[str]:
    copy = board.copy()
    san: list[str] = []
    for move in pv[:maximum]:
        if move not in copy.legal_moves:
            break
        san.append(copy.san(move))
        copy.push(move)
    return san


def _limit(depth: int, time_ms: int) -> chess.engine.Limit:
    if time_ms:
        return chess.engine.Limit(time=time_ms / 1000)
    return chess.engine.Limit(depth=depth)


def engine_coaching(label: str, san: str, best_san: str, loss: int) -> str:
    if label == "best":
        return f"{san} matches the engine's first choice. Keep following the resulting plan."
    if label == "great":
        return f"{san} is a strong practical choice, only {loss} centipawns from the engine line."
    if label == "good":
        return f"{san} is sound. The engine slightly prefers {best_san}."
    return f"{san} loses about {loss / 100:.1f} pawns. Consider {best_san} and compare the resulting threats."


def analyse_game(game, engine, depth: int, time_ms: int, thresholds: Thresholds):
    board = game.board()
    rows: list[dict] = []
    puzzles: list[dict] = []
    if engine is None:
        return rows, puzzles
    limit = _limit(depth, time_ms)
    for ply, move in enumerate(game.mainline_moves(), 1):
        pre_fen = board.fen()
        mover = board.turn
        before = engine.analyse(board, limit)
        pv = before.get("pv", [])
        best = pv[0] if pv else move
        best_san = board.san(best)
        played_san = board.san(move)
        best_score = mover_score(before["score"], mover)
        board.push(move)
        after = engine.analyse(board, limit)
        played_score = score_after_move(after["score"], mover, board)
        loss = max(0, best_score - played_score)
        label = classify_loss(loss, thresholds)
        row = {
            "ply": ply, "move_number": (ply + 1) // 2, "color": "white" if mover else "black",
            "san": played_san, "fen_before": pre_fen, "fen_after": board.fen(),
            "eval_cp": played_score, "loss_cp": loss, "classification": label,
            "best_move_uci": best.uci(), "best_move_san": best_san,
            "pv": _pv_san(chess.Board(pre_fen), pv),
            "coach": engine_coaching(label, played_san, best_san, loss),
        }
        rows.append(row)
        if loss >= thresholds.puzzle and move != best:
            puzzles.append({"move_ply": ply, "fen": pre_fen, "solution_uci": best.uci(), "solution_san": best_san})
    return rows, puzzles
