from blindspot.actions.compound import merge_compound_risks
from blindspot.actions.models import (
    ActionCategory,
    ActionPriority,
    Confidence,
    FragilityPattern,
    RecommendedAction,
)


def _act(target, title, priority=ActionPriority.HIGH,
         category=ActionCategory.OWNERSHIP_DIVERSIFICATION,
         pattern=None, confidence=Confidence.MEDIUM):
    return RecommendedAction(
        priority=priority, category=category, title=title,
        description=".", target=target, evidence=".",
        pattern=pattern, confidence=confidence,
    )


def test_single_action_passes_through_untouched():
    a = _act("payment", "Diversify payment")
    out = merge_compound_risks([a])
    assert out == [a]


def test_two_actions_same_target_become_one_compound():
    a = _act("src/payment.py", "Diversify payment",
             pattern=FragilityPattern.SINGLE_OWNER_CONCENTRATION)
    b = _act("src/payment.py", "Knowledge transfer for payment",
             category=ActionCategory.KNOWLEDGE_TRANSFER,
             priority=ActionPriority.MEDIUM)
    out = merge_compound_risks([a, b])
    assert len(out) == 1
    assert out[0].pattern == FragilityPattern.COMPOUND_CONCENTRATION
    assert out[0].priority == ActionPriority.HIGH  # highest of the two
    assert "src/payment.py" in out[0].title


def test_aggregate_targets_skip_compounding():
    """Targets like '4 services' or '(repo)' should not collapse."""
    a = _act("4 services", "AI gap aggregate")
    b = _act("(repo)", "Something repo-wide")
    out = merge_compound_risks([a, b])
    assert len(out) == 2  # both pass through untouched


def test_unrelated_targets_keep_separate_lines():
    a = _act("payment", "Diversify payment")
    b = _act("auth", "Diversify auth")
    out = merge_compound_risks([a, b])
    assert len(out) == 2


def test_compound_takes_highest_confidence_of_group():
    a = _act("src/x.py", "rule A", confidence=Confidence.LOW)
    b = _act("src/x.py", "rule B", confidence=Confidence.HIGH)
    out = merge_compound_risks([a, b])
    assert out[0].confidence == Confidence.HIGH


def test_three_actions_collapse_into_one():
    a = _act("payment", "Diversify payment")
    b = _act("payment", "Decay payment")
    c = _act("payment", "Correction payment")
    out = merge_compound_risks([a, b, c])
    assert len(out) == 1
    assert "payment" in out[0].title
