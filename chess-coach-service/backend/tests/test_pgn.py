import pytest

from app.pgn import parse_pgn_games

VALID = '''[Event "Training"]
[Site "Local"]
[Date "2026.01.02"]
[Round "1"]
[White "Alice"]
[Black "Bob"]
[Result "1-0"]

1. e4 e5 2. Nf3 Nc6 3. Bb5 a6 1-0
'''


def test_parses_multiple_games_and_metadata():
    games = parse_pgn_games(VALID + "\n" + VALID.replace('Alice', 'Carol'))
    assert len(games) == 2
    assert games[0].white == "Alice"
    assert games[1].white == "Carol"
    assert games[0].ply_count == 6


@pytest.mark.parametrize("text", ["", "garbage", "[Event broken", "1. e4 e9 *"])
def test_rejects_empty_or_invalid_pgn(text):
    with pytest.raises(ValueError):
        parse_pgn_games(text)
