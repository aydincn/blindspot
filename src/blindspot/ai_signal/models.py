from dataclasses import dataclass
from enum import Enum


class AIFlag(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class SignalStrength(str, Enum):
    STRONG = "Strong"
    MODERATE = "Moderate"
    LOW = "Low"


class AuthorProfileType(str, Enum):
    REAL_GROWTH = "Real Growth"
    AI_AMPLIFIED_HEALTHY = "AI Amplified Healthy"
    FAKE_VELOCITY = "Fake Velocity"
    BOT = "Bot"
    INSUFFICIENT_DATA = "Insufficient Data"


@dataclass(frozen=True, slots=True)
class AISignal:
    author_email: str
    flag: AIFlag
    score: float
    frequency_score: float
    volume_score: float
    message_score: float
    large_commit_score: float
    timing_score: float
    recent_commits: int
    baseline_commits: int


@dataclass(frozen=True, slots=True)
class QualitySignal:
    author_email: str
    risk_score: float
    churn_score: float
    bug_keyword_score: float
    revert_score: float
    review_rejection_score: float
    test_coverage_score: float
    pr_description_score: float
    recent_commits: int


@dataclass(frozen=True, slots=True)
class AuthorProfile:
    author_email: str
    author_name: str
    profile_type: AuthorProfileType
    signal_strength: SignalStrength
    evidence_weight: float
    ai_signal: AISignal | None
    quality_signal: QualitySignal | None
    explanation: str


__all__ = [
    "AIFlag",
    "AISignal",
    "AuthorProfile",
    "AuthorProfileType",
    "QualitySignal",
    "SignalStrength",
]
