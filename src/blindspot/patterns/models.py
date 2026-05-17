"""Shared dataclasses for the pattern detection layer."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class PatternSeverity(str, Enum):
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


@dataclass(frozen=True, slots=True)
class PatternHit:
    """A composite-signal recognition.

    ``key``: machine-readable slug (``fragile_velocity``,
    ``onboarding_trap`` …) — used by templates / tests / future hooks.
    ``name``: human title (``Fragile velocity``).
    ``severity``: pattern-level severity, independent of any single
    underlying signal's priority.
    ``targets``: services / files where the pattern fired (capped).
    ``score``: 0.0 – 1.0, internal strength of the pattern. Used by the
    sort order on the report side; *not* the same as severity.
    """
    key: str
    name: str
    severity: PatternSeverity
    description: str
    targets: tuple[str, ...] = ()
    score: float = 0.0
    evidence: dict[str, str] = field(default_factory=dict)


__all__ = ["PatternHit", "PatternSeverity"]
