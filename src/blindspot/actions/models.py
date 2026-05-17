from dataclasses import dataclass
from enum import Enum


class ActionPriority(str, Enum):
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


PRIORITY_ORDER = {
    ActionPriority.HIGH: 0,
    ActionPriority.MEDIUM: 1,
    ActionPriority.LOW: 2,
}


class ActionCategory(str, Enum):
    OWNERSHIP_DIVERSIFICATION = "Ownership Diversification"
    KNOWLEDGE_TRANSFER = "Knowledge Transfer"
    REVIEW_HYGIENE = "Review Hygiene"
    QUALITY_GUARDRAIL = "Quality Guardrail"
    CODEOWNERS_UPDATE = "Codeowners Update"


class FragilityPattern(str, Enum):
    """Named patterns for AI-era engineering fragility.

    Slugs stay machine-readable; the human label lives on the enum value.
    Recommendations are tagged with at most one pattern so the report
    surface can group them and so the README can document each one.
    """
    REVIEW_WITHOUT_SCRUTINY = "Review without scrutiny"
    SINGLE_OWNER_CONCENTRATION = "Single-owner concentration"
    FRAGILE_VELOCITY = "Fragile velocity"
    COMPOUND_CONCENTRATION = "Compound concentration"


class Confidence(str, Enum):
    """How much weight to give a recommendation.

    Driven by signal density (commits/PRs in the window), recency, and
    repo profile (doc-only repos always get LOW; high-volume mature
    teams default to HIGH).
    """
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


@dataclass(frozen=True, slots=True)
class RecommendedAction:
    priority: ActionPriority
    category: ActionCategory
    title: str
    description: str
    target: str
    evidence: str
    pattern: FragilityPattern | None = None
    confidence: Confidence = Confidence.MEDIUM


__all__ = [
    "ActionCategory",
    "ActionPriority",
    "Confidence",
    "FragilityPattern",
    "PRIORITY_ORDER",
    "RecommendedAction",
]
