"""Tests for the rule-based narrator (Tier 0, ships in code)."""

from datetime import UTC, datetime

from blindspot import __version__
from blindspot.actions.models import (
    ActionCategory,
    ActionPriority,
    FragilityPattern,
    RecommendedAction,
)
from blindspot.ai_signal.models import (
    AIFlag,
    AISignal,
    AuthorProfile,
    AuthorProfileType,
    SignalStrength,
)
from blindspot.narrative.rule_based import RuleBasedNarrator
from blindspot.report.context import ReportContext
from blindspot.resilience.score import ResilienceScore
from blindspot.review_graph.engine import FileReviewStats
from blindspot.risk_models.bus_factor import ServiceBusFactor
from blindspot.risk_models.knowledge_decay import FileDecay


def _empty_ctx(**overrides) -> ReportContext:
    base = ReportContext(
        repo_path="/tmp/r",
        generated_at=datetime.now(UTC),
        since_days=180,
        blindspot_version=__version__,
        commit_count=0,
        author_count=0,
        file_count=0,
        additions=0,
        deletions=0,
        services=(),
        critical_files=(),
        decay_top=(),
        decay_services=(),
    )
    from dataclasses import replace
    return replace(base, **overrides)


def test_rule_based_marks_model_as_rule_based():
    ctx = _empty_ctx()
    nr = RuleBasedNarrator(language="en").summarize(ctx)
    assert nr.model == "rule-based"


def test_healthy_fallback_when_no_critical_issues():
    ctx = _empty_ctx()
    nr = RuleBasedNarrator(language="en").summarize(ctx)
    assert "Maintain" in nr.headline_action or "maintain" in nr.headline_action


def test_headline_pair_for_single_owner_service():
    svc = ServiceBusFactor(
        service="payment",
        file_count=12,
        bus_factor=1,
        threshold=0.80,
        risk_level="critical",
        top_owners=(("alice@x.com", 0.92), ("bob@x.com", 0.08)),
    )
    ctx = _empty_ctx(services=(svc,), names={"alice@x.com": "Alice"})
    nr = RuleBasedNarrator(language="en").summarize(ctx)
    assert "payment" in nr.headline_action
    assert "Alice" in nr.headline_action  # uses the label, not email
    assert "12" in nr.headline_action  # file count


def test_headline_decay_when_no_concentrations():
    decay = FileDecay(
        file="src/legacy/core.py",
        top_owner="alice@x.com",
        top_owner_coverage=0.7,
        owner_last_touch=datetime.now(UTC),
        days_since_owner_touch=200.0,
        lines_changed_after=500,
        volatility=0.97,
        person_absence=0.95,
        decay_score=0.92,
        risk_level="critical",
        projections={30: 0.93, 60: 0.94, 90: 0.95},
    )
    ctx = _empty_ctx(decay_top=(decay,))
    nr = RuleBasedNarrator(language="en").summarize(ctx)
    assert "src/legacy/core.py" in nr.headline_action
    assert "92" in nr.headline_action  # decay percent
    assert "200" in nr.headline_action  # days


def test_headline_review_for_rubber_stamp():
    rs = FileReviewStats(
        file="src/critical.py",
        unique_reviewers=2,
        total_reviews=10,
        total_comments=1,
        rubber_stamp_ratio=0.85,
        diversity_hhi=0.5,
    )
    ctx = _empty_ctx(top_rubber_stamps=(rs,))
    nr = RuleBasedNarrator(language="en").summarize(ctx)
    assert "src/critical.py" in nr.headline_action
    assert "85" in nr.headline_action


def test_headline_velocity_for_fake_velocity_author():
    profile = AuthorProfile(
        author_email="risky@x.com",
        author_name="Risky Dev",
        profile_type=AuthorProfileType.FAKE_VELOCITY,
        signal_strength=SignalStrength.LOW,
        evidence_weight=0.6,
        ai_signal=AISignal(
            author_email="risky@x.com", flag=AIFlag.HIGH, score=0.85,
            frequency_score=1.0, volume_score=1.0, message_score=0.6,
            large_commit_score=0.6, timing_score=0.4,
            recent_commits=30, baseline_commits=20,
        ),
        quality_signal=None,
        explanation="…",
    )
    ctx = _empty_ctx(author_profiles=(profile,))
    nr = RuleBasedNarrator(language="en").summarize(ctx)
    assert "Risky Dev" in nr.headline_action


def test_executive_summary_includes_resilience_band():
    score = ResilienceScore(
        overall=42,
        ownership=30,
        decay=50,
        review=60,
        activity=None,
        band="Fragile",
        summary="…",
    )
    ctx = _empty_ctx(resilience=score)
    nr = RuleBasedNarrator(language="en").summarize(ctx)
    assert "Fragile" in nr.executive_summary
    assert "42" in nr.executive_summary
    # Weakest of ownership/decay/review is ownership (30)
    assert "ownership" in nr.executive_summary.lower()


def test_turkish_language_uses_tr_labels():
    score = ResilienceScore(
        overall=42, ownership=30, decay=50, review=60, activity=None,
        band="Fragile", summary="…",
    )
    ctx = _empty_ctx(resilience=score)
    nr = RuleBasedNarrator(language="tr").summarize(ctx)
    # Turkish band label
    assert "Kırılgan" in nr.executive_summary
    # Turkish dimension label appears (sahiplik yoğunlaşması)
    assert "sahiplik" in nr.executive_summary.lower()


def test_rationales_built_per_recommendation():
    action = RecommendedAction(
        priority=ActionPriority.HIGH,
        category=ActionCategory.OWNERSHIP_DIVERSIFICATION,
        title="Diversify",
        description="...",
        target="payment",
        evidence="bus_factor=1, top_owner_coverage=85%, files=8",
        pattern=FragilityPattern.SINGLE_OWNER_CONCENTRATION,
    )
    svc = ServiceBusFactor(
        service="payment", file_count=8, bus_factor=1, threshold=0.8,
        risk_level="critical",
        top_owners=(("alice@x.com", 0.85),),
    )
    ctx = _empty_ctx(
        services=(svc,), recommendations=(action,),
        names={"alice@x.com": "Alice"},
    )
    nr = RuleBasedNarrator(language="en").summarize(ctx)
    assert "payment" in nr.rationales
    assert "Alice" in nr.rationales["payment"]
    assert "85" in nr.rationales["payment"]
