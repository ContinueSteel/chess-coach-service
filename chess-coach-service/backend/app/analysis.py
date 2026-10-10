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


def pv_cues(board: chess.Board, pv: list[chess.Move]) -> list[dict]:
    copy = board.copy()
    meanings = [("best", "Best"), ("response", "Expected reply"), ("continuation", "Continuation")]
    cues = []
    for move, (kind, label) in zip(pv[:3], meanings):
        if move not in copy.legal_moves:
            break
        cues.append({"kind": kind, "label": label, "uci": move.uci(), "san": copy.san(move), "fen": copy.fen()})
        copy.push(move)
    return cues


def _limit(depth: int, time_ms: int) -> chess.engine.Limit:
    return chess.engine.Limit(time=time_ms / 1000) if time_ms else chess.engine.Limit(depth=depth)


def engine_coaching(label: str, san: str, best_san: str, loss: int, level="intermediate") -> str:
    if label == "best":
        base = f"Nice work — {san} matches the engine's first choice."
    elif label in ("great", "good"):
        base = f"Good practical choice with {san}. The engine slightly prefers {best_san}."
    else:
        base = f"Let's slow this position down: {san} gives up about {loss / 100:.1f} pawns. {best_san} was stronger."
    if level == "beginner":
        return base + " Check your opponent's threats before choosing your next move."
    if level == "advanced":
        return base + " Compare forcing candidates and calculate the principal variation to a stable endpoint."
    return base + " Compare the plans and the most forcing reply in the engine line."


def evaluate_trial(board: chess.Board, move: chess.Move, engine, depth: int, time_ms: int,
                   thresholds: Thresholds, coach_level: str) -> dict:
    if move not in board.legal_moves:
        raise ValueError("Move is not legal in this position")
    limit = _limit(min(depth, 16), min(time_ms, 1500))
    mover = board.turn
    before = engine.analyse(board, limit)
    pv = before.get("pv") or []
    best = pv[0] if pv and pv[0] in board.legal_moves else move
    best_san = board.san(best)
    move_san = board.san(move)
    before_score = mover_score(before["score"], mover)
    trial_board = board.copy(); trial_board.push(move)
    after = engine.analyse(trial_board, limit)
    after_score = score_after_move(after["score"], mover, trial_board)
    loss = max(0, before_score - after_score)
    label = classify_loss(loss, thresholds)
    return {"fen_before": board.fen(), "fen_after": trial_board.fen(), "move_uci": move.uci(),
            "move_san": move_san, "before_score_cp": before_score, "after_score_cp": after_score,
            "loss_cp": loss, "classification": label, "best_move_uci": best.uci(),
            "best_move_san": best_san, "pv": _pv_san(board, pv), "cues": pv_cues(board, pv),
            "feedback": engine_coaching(label, move_san, best_san, loss, coach_level)}


def analyse_game(game, engine, depth: int, time_ms: int, thresholds: Thresholds, coach_level="intermediate"):
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
        pv = before.get("pv") or []
        best = pv[0] if pv and pv[0] in board.legal_moves else move
        best_san = board.san(best)
        played_san = board.san(move)
        best_score = mover_score(before["score"], mover)
        cues = pv_cues(board, pv)
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
            "pv": _pv_san(chess.Board(pre_fen), pv), "cues": cues,
            "coach": engine_coaching(label, played_san, best_san, loss, coach_level),
        }
        rows.append(row)
        if loss >= thresholds.puzzle and move != best:
            puzzles.append({"move_ply": ply, "fen": pre_fen, "solution_uci": best.uci(), "solution_san": best_san})
    return rows, puzzles
