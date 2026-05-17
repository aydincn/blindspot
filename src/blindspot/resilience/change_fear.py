"""Change Fear Index — files nobody dares to touch.

A "fear zone" file is one where three things compound:
* it sits high in the dependency graph (PageRank centrality) — breaking
  it ripples,
* very few people have edited it — knowledge is thin,
* and nobody has touched it in a long time — the muscle memory is gone.

A senior contributor leaves and the remaining team avoids editing this
surface because they don't fully understand the consequences. That
avoidance is the *real* risk: the code keeps shipping around it, until
the day someone has to.

This file complements (does not replace) the bus-factor and decay
signals. The decay engine answers "does the owner still know it?"; the
fear index answers "does *anyone* want to touch it?".
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime

from blindspot.collector.models import Commit


@dataclass(frozen=True, slots=True)
class ChangeFearScore:
    file: str
    importance: float
    contributor_count: int
    days_since_touch: float
    fear_score: float
    risk_level: str  # "critical" | "high" | "moderate"


@dataclass(frozen=True, slots=True)
class ChangeFearReport:
    files: tuple[ChangeFearScore, ...]


def _risk_level(score: float) -> str:
    if score >= 0.02:
        return "critical"
    if score >= 0.01:
        return "high"
    return "moderate"


def compute_change_fear(
    commits: Iterable[Commit],
    importance_map: dict[str, float],
    *,
    top_n: int = 10,
    min_importance: float = 0.005,
    min_days_since_touch: float = 30.0,
) -> ChangeFearReport:
    """Return the top-N "fear zone" files: structurally central, touched
    by few people, and recently neglected.

    Files below ``min_importance`` or touched within
    ``min_days_since_touch`` days are excluded — the fear signal only
    kicks in once avoidance becomes visible.
    """
    per_file_contributors: dict[str, set[str]] = {}
    per_file_last_touch: dict[str, datetime] = {}
    for c in commits:
        if c.is_merge:
            continue
        for fc in c.files:
            per_file_contributors.setdefault(fc.path, set()).add(c.author_email)
            existing = per_file_last_touch.get(fc.path)
            if existing is None or c.authored_at > existing:
                per_file_last_touch[fc.path] = c.authored_at

    now = datetime.now(UTC)
    out: list[ChangeFearScore] = []
    for file, importance in importance_map.items():
        if importance < min_importance:
            continue
        last_touch = per_file_last_touch.get(file)
        if last_touch is None:
            days_since = 9999.0  # never touched in this window
        else:
            days_since = (now - last_touch).total_seconds() / 86400.0
        if days_since < min_days_since_touch:
            continue
        contributors = per_file_contributors.get(file, set())
        contributor_count = len(contributors)
        if contributor_count == 0:
            contributor_count = 1  # avoid division by zero
        # Cap the time multiplier at 1.0 (≥ 90 days = full weight)
        time_weight = min(days_since / 90.0, 1.0)
        fear_score = importance * (1.0 / contributor_count) * time_weight
        out.append(
            ChangeFearScore(
                file=file,
                importance=importance,
                contributor_count=contributor_count,
                days_since_touch=days_since,
                fear_score=fear_score,
                risk_level=_risk_level(fear_score),
            )
        )
    out.sort(key=lambda c: -c.fear_score)
    return ChangeFearReport(files=tuple(out[:top_n]))


__all__ = ["ChangeFearReport", "ChangeFearScore", "compute_change_fear"]
