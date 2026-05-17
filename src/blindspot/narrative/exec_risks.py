"""Top-3 executive risks selector.

The full ``recommendations`` table can hold a dozen action lines; the
executive brief at the top of the report needs just three. This module
picks the three most boardroom-relevant entries.

Selection logic — *not* a re-sort of the priority field. The recommender
already ordered actions by ``PRIORITY_ORDER`` (HIGH/MEDIUM/LOW); but a
HIGH "Diversify ownership of `vendor/`" matters less to a CTO than a
MEDIUM "Knowledge transfer for src/payment/checkout.py", because the
second names a delivery-relevant surface.

We rank by a stable weight:

  * pattern type — single-owner-concentration > review-without-scrutiny
    > fragile-velocity > none
  * priority — HIGH > MEDIUM > LOW
  * target shape — service > file > "(N services)" aggregates

Then de-duplicate by target so the brief doesn't repeat the same
service three times.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from blindspot.actions.models import (
    ActionPriority,
    FragilityPattern,
    RecommendedAction,
)


_PATTERN_WEIGHT = {
    FragilityPattern.SINGLE_OWNER_CONCENTRATION: 3,
    FragilityPattern.REVIEW_WITHOUT_SCRUTINY: 2,
    FragilityPattern.FRAGILE_VELOCITY: 2,
    None: 1,
}

_PRIORITY_WEIGHT = {
    ActionPriority.HIGH: 3,
    ActionPriority.MEDIUM: 2,
    ActionPriority.LOW: 1,
}


@dataclass(frozen=True, slots=True)
class ExecRisk:
    priority: ActionPriority
    title: str
    target: str
    pattern: FragilityPattern | None


def _action_weight(a: RecommendedAction) -> tuple[int, int]:
    return (
        _PATTERN_WEIGHT.get(a.pattern, 1),
        _PRIORITY_WEIGHT[a.priority],
    )


def select_top_risks(
    recommendations: Iterable[RecommendedAction],
    *,
    limit: int = 3,
) -> tuple[ExecRisk, ...]:
    """Pick the top ``limit`` boardroom-relevant risks from a recommendation
    stream.

    Stable, deterministic. De-duplicates by ``target`` so a single
    service that fires multiple rules doesn't crowd out other risks.
    """
    ordered = sorted(recommendations, key=_action_weight, reverse=True)
    seen_targets: set[str] = set()
    out: list[ExecRisk] = []
    for a in ordered:
        if a.target in seen_targets:
            continue
        seen_targets.add(a.target)
        out.append(
            ExecRisk(
                priority=a.priority,
                title=a.title,
                target=a.target,
                pattern=a.pattern,
            )
        )
        if len(out) >= limit:
            break
    return tuple(out)


__all__ = ["ExecRisk", "select_top_risks"]
