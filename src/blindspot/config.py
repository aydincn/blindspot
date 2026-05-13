from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class OwnershipWeights(BaseModel):
    commit: float = 0.30
    volume: float = 0.20
    recency: float = 0.35
    review: float = 0.15
    decay_lambda: float = 0.01


class DecayWeights(BaseModel):
    volatility: float = 0.55
    absence: float = 0.45
    absence_score: float = 0.50
    review_absence: float = 0.30
    attention_shift: float = 0.20
    critical_threshold: float = 0.75
    high_threshold: float = 0.50
    medium_threshold: float = 0.25
    prediction_days: list[int] = Field(default_factory=lambda: [30, 60, 90])


class ScoringConfig(BaseModel):
    ownership: OwnershipWeights = Field(default_factory=OwnershipWeights)
    decay: DecayWeights = Field(default_factory=DecayWeights)


class AnalysisConfig(BaseModel):
    since_days: int = 180
    baseline_months: int = 12


class Config(BaseModel):
    scoring: ScoringConfig = Field(default_factory=ScoringConfig)
    analysis: AnalysisConfig = Field(default_factory=AnalysisConfig)


def load(path: Path | None = None) -> Config:
    if path is None or not path.exists():
        return Config()
    data = yaml.safe_load(path.read_text()) or {}
    return Config(**data)
