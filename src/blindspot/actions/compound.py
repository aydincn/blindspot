"""Compound-risk merging — post-process the recommendation list.

When the same file or service appears in two or more recommendations
(e.g. ``src/payment.py`` flagged by both knowledge decay AND high
correction load), the executive doesn't need two lines — they need
one *compound* line that names the combined risk.

This is a presentation-layer transform: the underlying rule outputs
are not changed. We collapse only when there are ≥ 2 actions sharing
the same target and the targets look like file/service identifiers
(not aggregate strings like "4 services").
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable

from blindspot.actions.models import (
    ActionCategory,
    ActionPriority,
    PRIORITY_ORDER,
    Confidence,
    FragilityPattern,
    RecommendedAction,
)


def _is_compoundable_target(target: str) -> bool:
    """Aggregate targets ("4 services", "(repo)") shouldn't merge —
    they already represent a roll-up."""
    if not target:
        return False
    if target.startswith("(") and target.endswith(")"):
        return False
    if " services" in target or " files" in target:
        return False
    return True


def _highest_priority(actions: list[RecommendedAction]) -> ActionPriority:
    return min(actions, key=lambda a: PRIORITY_ORDER[a.priority]).priority


def _highest_confidence(actions: list[RecommendedAction]) -> Confidence:
    order = {Confidence.HIGH: 0, Confidence.MEDIUM: 1, Confidence.LOW: 2}
    return min(actions, key=lambda a: order[a.confidence]).confidence


def _compound_description(actions: list[RecommendedAction]) -> str:
    """Build the merged description from the per-rule signals."""
    parts = []
    for a in actions:
        # Trim each contributing title to its semantic core.
        short = a.title.replace(f" for {a.target}", "")
        short = short.replace(f" of '{a.target}'", "")
        short = short.replace(f" on '{a.target}'", "")
        short = short.replace(f" on {a.target}", "")
        # First word lowercased, rest as-is.
        short = short[0].lower() + short[1:] if short else short
        parts.append(short)
    body = "; ".join(parts)
    return (
        f"Multiple signals on the same surface compound the risk: {body}. "
        "Address them together — fixing one without the others leaves the "
        "concentration intact."
    )


def _compound_evidence(actions: list[RecommendedAction]) -> str:
    return " | ".join(a.evidence for a in actions)


def merge_compound_risks(
    actions: Iterable[RecommendedAction],
) -> list[RecommendedAction]:
    """Group actions by target; collapse groups of size ≥ 2 into a single
    compound recommendation. Single-action targets pass through untouched.

    Resulting order: same as the input, with the first occurrence of each
    target carrying the compound (or the original if it stayed solo).
    """
    by_target: dict[str, list[RecommendedAction]] = defaultdict(list)
    order_seen: list[str] = []
    untouched: list[RecommendedAction] = []
    for a in actions:
        if not _is_compoundable_target(a.target):
            untouched.append(a)
            continue
        if a.target not in by_target:
            order_seen.append(a.target)
        by_target[a.target].append(a)

    out: list[RecommendedAction] = []
    for target in order_seen:
        group = by_target[target]
        if len(group) == 1:
            out.append(group[0])
            continue
        # ≥ 2 actions on the same target → compound
        priority = _highest_priority(group)
        confidence = _highest_confidence(group)
        out.append(
            RecommendedAction(
                priority=priority,
                category=ActionCategory.KNOWLEDGE_TRANSFER,
                title=f"Compound concentration on '{target}'",
                description=_compound_description(group),
                target=target,
                evidence=_compound_evidence(group),
                pattern=FragilityPattern.COMPOUND_CONCENTRATION,
                confidence=confidence,
            )
        )

    # Re-blend untouched (aggregate / "(repo)" target) actions at the end —
    # they shouldn't have been compounded but they deserve to stay in the
    # final list.
    out.extend(untouched)
    # Re-sort by priority so the table reads HIGH → LOW.
    out.sort(key=lambda a: (PRIORITY_ORDER[a.priority], a.category.value, a.target))
    return out


__all__ = ["merge_compound_risks"]
