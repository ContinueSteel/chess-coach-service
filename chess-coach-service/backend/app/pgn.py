import io

import chess.pgn
import chess

from .models import ParsedGame


def parse_pgn_games(text: str) -> list[ParsedGame]:
    if not text or not text.strip():
        raise ValueError("PGN is empty")
    stream = io.StringIO(text)
    parsed: list[ParsedGame] = []
    while True:
        before = stream.tell()
        game = chess.pgn.read_game(stream)
        if game is None:
            break
        if game.errors:
            raise ValueError(f"Invalid PGN: {game.errors[0]}")
        moves = list(game.mainline_moves())
        if not moves:
            raise ValueError("Invalid PGN: game has no moves")
        consumed = text[before:stream.tell()]
        tokens = consumed.replace("\n", " ").split()
        malformed_squares = [token for token in tokens if len(token) >= 2 and token[-2].isalpha() and token[-1].isdigit()
                             and (token[-2].lower() not in "abcdefgh" or token[-1] not in "12345678")]
        if malformed_squares:
            raise ValueError("Invalid PGN: malformed move token")
        board = game.board()
        for move in moves:
            if move not in board.legal_moves:
                raise ValueError("Invalid PGN: illegal move")
            board.push(move)
        exporter = chess.pgn.StringExporter(headers=True, variations=False, comments=True)
        headers = game.headers
        parsed.append(ParsedGame(
            game=game,
            pgn=game.accept(exporter),
            event=headers.get("Event", "Unknown event"),
            site=headers.get("Site", "Unknown"),
            played_at=headers.get("Date", "????.??.??"),
            white=headers.get("White", "White"),
            black=headers.get("Black", "Black"),
            result=headers.get("Result", "*"),
            ply_count=len(moves),
        ))
    if not parsed:
        raise ValueError("Invalid PGN: no games found")
    trailing = stream.read().strip()
    if trailing:
        raise ValueError("Invalid trailing PGN data")
    return parsed
