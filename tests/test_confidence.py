from blindspot.actions.confidence import confidence_for, scan_confidence
from blindspot.actions.models import (
    ActionCategory,
    ActionPriority,
    Confidence,
    RecommendedAction,
)


def _action(category=ActionCategory.OWNERSHIP_DIVERSIFICATION):
    return RecommendedAction(
        priority=ActionPriority.HIGH, category=category,
        title=".", description=".", target="x", evidence=".",
    )


def test_doc_only_profile_always_low():
    assert scan_confidence(
        commit_count=10_000, window_days=180, repo_profile="doc-only",
    ) == Confidence.LOW


def test_low_volume_scan_is_low():
    assert scan_confidence(
        commit_count=20, window_days=180, repo_profile="team",
    ) == Confidence.LOW


def test_short_window_scan_is_low():
    assert scan_confidence(
        commit_count=500, window_days=3, repo_profile="team",
    ) == Confidence.LOW


def test_high_volume_scan_is_high():
    assert scan_confidence(
        commit_count=5000, window_days=180, repo_profile="team",
    ) == Confidence.HIGH


def test_mid_volume_scan_is_medium():
    assert scan_confidence(
        commit_count=150, window_days=180, repo_profile="team",
    ) == Confidence.MEDIUM


def test_action_inherits_scan_ceiling():
    a = _action()
    out = confidence_for(a, scan_ceiling=Confidence.MEDIUM)
    assert out == Confidence.MEDIUM


def test_review_action_downgraded_when_sample_thin():
    a = _action(category=ActionCategory.REVIEW_HYGIENE)
    out = confidence_for(
        a, scan_ceiling=Confidence.HIGH, review_sample_size=2,
    )
    assert out == Confidence.MEDIUM


def test_review_action_not_downgraded_when_sample_sound():
    a = _action(category=ActionCategory.REVIEW_HYGIENE)
    out = confidence_for(
        a, scan_ceiling=Confidence.HIGH, review_sample_size=20,
    )
    assert out == Confidence.HIGH
