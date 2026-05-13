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


@dataclass(frozen=True, slots=True)
class RecommendedAction:
    priority: ActionPriority
    category: ActionCategory
    title: str
    description: str
    target: str
    evidence: str


__all__ = [
    "ActionCategory",
    "ActionPriority",
    "PRIORITY_ORDER",
    "RecommendedAction",
]
