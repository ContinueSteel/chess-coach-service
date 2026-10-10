from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

CoachLevel = Literal["beginner", "intermediate", "advanced"]
PlayerColor = Literal["white", "black", "unknown"]


class Thresholds(BaseModel):
    inaccuracy: int = Field(50, ge=1, le=1000)
    mistake: int = Field(100, ge=2, le=2000)
    blunder: int = Field(200, ge=3, le=5000)
    puzzle: int = Field(150, ge=1, le=5000)

    def __init__(self, inaccuracy=50, mistake=100, blunder=200, puzzle=150, **data):
        super().__init__(inaccuracy=inaccuracy, mistake=mistake, blunder=blunder, puzzle=puzzle, **data)

    @model_validator(mode="after")
    def ordered(self):
        if not self.inaccuracy < self.mistake < self.blunder:
            raise ValueError("thresholds must increase: inaccuracy < mistake < blunder")
        return self


class SettingsInput(BaseModel):
    chesscom_username: str = Field("", max_length=50, pattern=r"^[A-Za-z0-9_-]*$")
    analysis_depth: int = Field(12, ge=6, le=24)
    analysis_time_ms: int = Field(0, ge=0, le=10000)
    inaccuracy_threshold: int = Field(50, ge=1, le=1000)
    mistake_threshold: int = Field(100, ge=2, le=2000)
    blunder_threshold: int = Field(200, ge=3, le=5000)
    puzzle_threshold: int = Field(150, ge=1, le=5000)
    ai_provider: Literal["disabled", "local", "openai-compatible"] = "disabled"
    ai_base_url: str = Field("", max_length=500)
    ai_model: str = Field("", max_length=200)
    ai_api_key: str = Field("", max_length=500)
    coach_level: CoachLevel = "intermediate"
    board_theme: Literal["green", "brown", "blue", "purple"] = "green"
    piece_set: Literal["classic", "alpha", "merida"] = "classic"
    show_coordinates: bool = True
    orientation_mode: Literal["player", "white", "black"] = "player"
    move_sounds_enabled: bool = True
    sound_volume: float = Field(0.55, ge=0, le=1)

    @model_validator(mode="after")
    def validate_settings(self):
        Thresholds(inaccuracy=self.inaccuracy_threshold, mistake=self.mistake_threshold,
                   blunder=self.blunder_threshold, puzzle=self.puzzle_threshold)
        if self.ai_provider == "openai-compatible" and (not self.ai_base_url or not self.ai_model):
            raise ValueError("base URL and model are required for OpenAI-compatible AI")
        return self


class PgnInput(BaseModel):
    pgn: str = Field(min_length=1, max_length=2_000_000)


class ChessComImport(BaseModel):
    username: str = Field(min_length=1, max_length=50, pattern=r"^[A-Za-z0-9_-]+$")
    months: int = Field(1, ge=1, le=12)


class MoveInput(BaseModel):
    move: str = Field(min_length=2, max_length=12)


class PositionMove(BaseModel):
    fen: str = Field(min_length=1, max_length=200)
    move: str = Field(min_length=2, max_length=12)


class TrialInput(PositionMove):
    coach_level: CoachLevel = "intermediate"


class OrientationInput(BaseModel):
    player_color: PlayerColor


class ChatInput(BaseModel):
    ply: int = Field(ge=0, le=1000)
    question: str = Field(min_length=2, max_length=1000)

    @field_validator("question")
    @classmethod
    def strip_question(cls, value: str):
        value = value.strip()
        if len(value) < 2:
            raise ValueError("question is too short")
        return value


@dataclass
class ParsedGame:
    game: object
    pgn: str
    event: str
    site: str
    played_at: str
    white: str
    black: str
    result: str
    ply_count: int
