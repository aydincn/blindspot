from blindspot.actions.models import (
    ActionCategory,
    ActionPriority,
    FragilityPattern,
    RecommendedAction,
)
from blindspot.narrative.exec_risks import select_top_risks


def _action(title, target, priority=ActionPriority.HIGH, pattern=None,
            category=ActionCategory.OWNERSHIP_DIVERSIFICATION):
    return RecommendedAction(
        priority=priority, category=category, title=title,
        description=".", target=target, evidence=".", pattern=pattern,
    )


def test_returns_empty_when_no_recommendations():
    assert select_top_risks([]) == ()


def test_picks_at_most_three():
    actions = [
        _action(f"Action {i}", f"svc_{i}", priority=ActionPriority.HIGH)
        for i in range(10)
    ]
    out = select_top_risks(actions)
    assert len(out) == 3


def test_pattern_weighting_beats_raw_priority():
    """A MEDIUM single-owner-concentration should outrank a HIGH plain rec."""
    actions = [
        _action("Plain HIGH", "thing-a", priority=ActionPriority.HIGH),
        _action(
            "Tagged MEDIUM", "thing-b",
            priority=ActionPriority.MEDIUM,
            pattern=FragilityPattern.SINGLE_OWNER_CONCENTRATION,
        ),
    ]
    out = select_top_risks(actions, limit=2)
    assert out[0].target == "thing-b"


def test_deduplicates_by_target():
    actions = [
        _action("Diversify payment", "payment", priority=ActionPriority.HIGH,
                pattern=FragilityPattern.SINGLE_OWNER_CONCENTRATION),
        _action("Knowledge transfer payment/foo.py", "payment",
                priority=ActionPriority.HIGH),
        _action("Diversify auth", "auth", priority=ActionPriority.HIGH,
                pattern=FragilityPattern.SINGLE_OWNER_CONCENTRATION),
    ]
    out = select_top_risks(actions)
    targets = [r.target for r in out]
    assert targets.count("payment") == 1
    assert "auth" in targets


def test_priority_falls_back_after_pattern_tie():
    """When pattern weight ties, priority decides."""
    actions = [
        _action("Tagged LOW", "thing-a", priority=ActionPriority.LOW,
                pattern=FragilityPattern.SINGLE_OWNER_CONCENTRATION),
        _action("Tagged HIGH", "thing-b", priority=ActionPriority.HIGH,
                pattern=FragilityPattern.SINGLE_OWNER_CONCENTRATION),
    ]
    out = select_top_risks(actions, limit=2)
    assert out[0].target == "thing-b"
