"""Pattern engine — runs every detector against the same ReportContext.

Detectors are registered explicitly here so adding a new pattern is
one line. Order is the detection order *and* the rendering order on
the report side.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from blindspot.patterns.fragile_velocity import detect_fragile_velocity
from blindspot.patterns.models import PatternHit

if TYPE_CHECKING:
    from blindspot.report.context import ReportContext


_DETECTORS = [
    detect_fragile_velocity,
    # Future:
    # detect_onboarding_trap,
    # detect_review_theatre,
    # detect_knowledge_cliff,
]


def detect_all_patterns(ctx: "ReportContext") -> tuple[PatternHit, ...]:
    hits: list[PatternHit] = []
    for detector in _DETECTORS:
        hit = detector(ctx)
        if hit is not None:
            hits.append(hit)
    # Order: highest severity first, then highest score
    severity_order = {"High": 0, "Medium": 1, "Low": 2}
    hits.sort(key=lambda h: (severity_order[h.severity.value], -h.score))
    return tuple(hits)


__all__ = ["detect_all_patterns"]
