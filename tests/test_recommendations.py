from datetime import UTC, datetime

from blindspot.actions import (
    ActionCategory,
    ActionPriority,
    FragilityPattern,
    RecommendationContext,
    RecommendationEngine,
)
from blindspot.ai_signal.models import (
    AIFlag,
    AISignal,
    AuthorProfile,
    AuthorProfileType,
    QualitySignal,
    SignalStrength,
)
from blindspot.review_graph.engine import FileReviewStats
from blindspot.risk_models.bus_factor import FileBusFactor, ServiceBusFactor
from blindspot.risk_models.knowledge_decay import FileDecay


def _service(name: str, files: int, owner: str, coverage: float) -> ServiceBusFactor:
    return ServiceBusFactor(
        service=name,
        file_count=files,
        bus_factor=1,
        threshold=0.8,
        risk_level="critical",
        top_owners=((owner, coverage), ("other@x.com", 1 - coverage)),
    )


def _decay(file: str, owner: str, days: float, score: float) -> FileDecay:
    return FileDecay(
        file=file,
        top_owner=owner,
        top_owner_coverage=0.8,
        owner_last_touch=datetime.now(UTC),
        days_since_owner_touch=days,
        lines_changed_after=300,
        volatility=0.5,
        person_absence=0.6,
        decay_score=score,
        risk_level="critical" if score >= 0.75 else "high",
        projections={30: score + 0.05, 60: score + 0.1, 90: score + 0.15},
    )


def test_recommends_diversification_for_single_owner_service():
    ctx = RecommendationContext(
        services=(_service("payment", 8, "alice@x.com", 0.85),),
    )
    actions = RecommendationEngine().recommend(ctx)
    assert any(a.category == ActionCategory.OWNERSHIP_DIVERSIFICATION for a in actions)
    a = next(a for a in actions if a.category == ActionCategory.OWNERSHIP_DIVERSIFICATION)
    assert a.priority == ActionPriority.HIGH
    assert "payment" in a.target


def test_small_service_gets_medium_priority():
    ctx = RecommendationContext(
        services=(_service("util", 2, "alice@x.com", 0.9),),
    )
    actions = RecommendationEngine().recommend(ctx)
    a = next(a for a in actions if a.category == ActionCategory.OWNERSHIP_DIVERSIFICATION)
    assert a.priority == ActionPriority.MEDIUM


def test_recommends_knowledge_transfer_for_critical_decay():
    ctx = RecommendationContext(
        decays=(_decay("src/legacy.py", "alice@x.com", days=200, score=0.82),),
    )
    actions = RecommendationEngine().recommend(ctx)
    a = next(a for a in actions if a.category == ActionCategory.KNOWLEDGE_TRANSFER)
    assert a.priority == ActionPriority.HIGH
    assert "src/legacy.py" in a.target


def test_high_decay_below_critical_yields_medium_priority():
    ctx = RecommendationContext(
        decays=(_decay("src/old.py", "alice@x.com", days=120, score=0.55),),
    )
    actions = RecommendationEngine().recommend(ctx)
    a = next(a for a in actions if a.category == ActionCategory.KNOWLEDGE_TRANSFER)
    assert a.priority == ActionPriority.MEDIUM


def test_recommends_review_template_for_rubber_stamp():
    stats = FileReviewStats(
        file="src/core.py",
        unique_reviewers=2,
        total_reviews=10,
        total_comments=1,
        rubber_stamp_ratio=0.9,
        diversity_hhi=0.5,
    )
    ctx = RecommendationContext(review_stats={"src/core.py": stats})
    actions = RecommendationEngine().recommend(ctx)
    a = next(a for a in actions if a.category == ActionCategory.REVIEW_HYGIENE and "depth" in a.title.lower())
    assert a.priority == ActionPriority.MEDIUM


def test_recommends_rotation_for_low_diversity():
    stats = FileReviewStats(
        file="src/core.py",
        unique_reviewers=1,
        total_reviews=10,
        total_comments=8,
        rubber_stamp_ratio=0.1,
        diversity_hhi=0.05,
    )
    ctx = RecommendationContext(review_stats={"src/core.py": stats})
    actions = RecommendationEngine().recommend(ctx)
    a = next(a for a in actions if "Rotate reviewers" in a.title)
    assert a.priority == ActionPriority.LOW


def test_recommends_slow_down_for_fast_approvals():
    stats = FileReviewStats(
        file="src/critical.py",
        unique_reviewers=2,
        total_reviews=5,
        total_comments=3,
        rubber_stamp_ratio=0.2,
        diversity_hhi=0.5,
        median_approval_latency_seconds=10 * 60,
        approval_sample_size=5,
    )
    ctx = RecommendationContext(review_stats={"src/critical.py": stats})
    actions = RecommendationEngine().recommend(ctx)
    a = next(a for a in actions if "Slow down fast" in a.title)
    assert a.priority == ActionPriority.MEDIUM
    assert a.target == "src/critical.py"


def test_does_not_recommend_slow_down_when_latency_unknown():
    stats = FileReviewStats(
        file="src/critical.py",
        unique_reviewers=2,
        total_reviews=5,
        total_comments=3,
        rubber_stamp_ratio=0.2,
        diversity_hhi=0.5,
        median_approval_latency_seconds=None,
        approval_sample_size=0,
    )
    ctx = RecommendationContext(review_stats={"src/critical.py": stats})
    actions = RecommendationEngine().recommend(ctx)
    assert not any("Slow down fast" in a.title for a in actions)


def test_recommends_deep_review_for_fake_velocity_author():
    ai = AISignal(
        author_email="risky@x.com",
        flag=AIFlag.HIGH,
        score=0.85,
        frequency_score=1.0, volume_score=1.0, message_score=0.6,
        large_commit_score=0.6, timing_score=0.4,
        recent_commits=30, baseline_commits=20,
    )
    quality = QualitySignal(
        author_email="risky@x.com",
        risk_score=0.75,
        churn_score=1.0, bug_keyword_score=1.0, revert_score=0.3,
        review_rejection_score=0.0, test_coverage_score=1.0,
        pr_description_score=0.0,
        recent_commits=30,
    )
    profile = AuthorProfile(
        author_email="risky@x.com",
        author_name="Risky Dev",
        profile_type=AuthorProfileType.FAKE_VELOCITY,
        signal_strength=SignalStrength.LOW,
        evidence_weight=0.60,
        ai_signal=ai,
        quality_signal=quality,
        explanation="…",
    )
    ctx = RecommendationContext(
        author_profiles={"risky@x.com": profile},
        ownership_names={"risky@x.com": "Risky Dev"},
    )
    actions = RecommendationEngine().recommend(ctx)
    a = next(a for a in actions if a.category == ActionCategory.QUALITY_GUARDRAIL)
    assert a.priority == ActionPriority.HIGH
    assert "Risky Dev" in a.title


def test_returns_no_actions_when_state_is_healthy():
    ctx = RecommendationContext()
    actions = RecommendationEngine().recommend(ctx)
    assert actions == []


def test_service_bus_factor_tagged_with_single_owner_concentration():
    ctx = RecommendationContext(
        services=(_service("payment", 8, "alice@x.com", 0.85),),
    )
    actions = RecommendationEngine().recommend(ctx)
    a = next(a for a in actions if a.category == ActionCategory.OWNERSHIP_DIVERSIFICATION)
    assert a.pattern == FragilityPattern.SINGLE_OWNER_CONCENTRATION


def test_rubber_stamp_tagged_with_review_without_scrutiny():
    stats = FileReviewStats(
        file="src/core.py",
        unique_reviewers=2,
        total_reviews=10,
        total_comments=1,
        rubber_stamp_ratio=0.9,
        diversity_hhi=0.5,
    )
    ctx = RecommendationContext(review_stats={"src/core.py": stats})
    actions = RecommendationEngine().recommend(ctx)
    a = next(a for a in actions if "depth" in a.title.lower())
    assert a.pattern == FragilityPattern.REVIEW_WITHOUT_SCRUTINY


def test_fast_approval_tagged_with_review_without_scrutiny():
    stats = FileReviewStats(
        file="src/critical.py",
        unique_reviewers=2,
        total_reviews=5,
        total_comments=5,
        rubber_stamp_ratio=0.0,
        diversity_hhi=0.5,
        median_approval_latency_seconds=60,
        approval_sample_size=5,
    )
    ctx = RecommendationContext(review_stats={"src/critical.py": stats})
    actions = RecommendationEngine().recommend(ctx)
    a = next(a for a in actions if "Slow down" in a.title)
    assert a.pattern == FragilityPattern.REVIEW_WITHOUT_SCRUTINY


def test_fake_velocity_tagged_with_velocity_without_review():
    ai = AISignal(
        author_email="risky@x.com",
        flag=AIFlag.HIGH,
        score=0.85,
        frequency_score=1.0, volume_score=1.0, message_score=0.6,
        large_commit_score=0.6, timing_score=0.4,
        recent_commits=30, baseline_commits=20,
    )
    quality = QualitySignal(
        author_email="risky@x.com",
        risk_score=0.75,
        churn_score=1.0, bug_keyword_score=1.0, revert_score=0.3,
        review_rejection_score=0.0, test_coverage_score=1.0,
        pr_description_score=0.0,
        recent_commits=30,
    )
    profile = AuthorProfile(
        author_email="risky@x.com",
        author_name="Risky Dev",
        profile_type=AuthorProfileType.FAKE_VELOCITY,
        signal_strength=SignalStrength.LOW,
        evidence_weight=0.60,
        ai_signal=ai,
        quality_signal=quality,
        explanation="…",
    )
    ctx = RecommendationContext(author_profiles={"risky@x.com": profile})
    actions = RecommendationEngine().recommend(ctx)
    a = next(a for a in actions if a.category == ActionCategory.QUALITY_GUARDRAIL)
    assert a.pattern == FragilityPattern.VELOCITY_WITHOUT_REVIEW


def test_decay_filtered_when_importance_below_threshold():
    ctx = RecommendationContext(
        decays=(_decay("src/legacy/bootstrap.js", "alice@x.com", days=200, score=0.82),),
        importance_map={"src/legacy/bootstrap.js": 0.001},  # below 0.005 threshold
    )
    actions = RecommendationEngine().recommend(ctx)
    assert not any(a.category == ActionCategory.KNOWLEDGE_TRANSFER for a in actions)


def test_decay_kept_when_importance_above_threshold():
    ctx = RecommendationContext(
        decays=(_decay("src/core/engine.py", "alice@x.com", days=200, score=0.82),),
        importance_map={"src/core/engine.py": 0.05},  # well above threshold
    )
    actions = RecommendationEngine().recommend(ctx)
    assert any(a.category == ActionCategory.KNOWLEDGE_TRANSFER for a in actions)


def test_importance_filter_skipped_when_map_empty():
    # Backward compatibility: no importance_map → behaviour unchanged
    ctx = RecommendationContext(
        decays=(_decay("src/core/engine.py", "alice@x.com", days=200, score=0.82),),
    )
    actions = RecommendationEngine().recommend(ctx)
    assert any(a.category == ActionCategory.KNOWLEDGE_TRANSFER for a in actions)


def test_actions_are_sorted_high_priority_first():
    ctx = RecommendationContext(
        services=(_service("payment", 10, "alice@x.com", 0.8),),
        review_stats={
            "tests/foo.py": FileReviewStats(
                file="tests/foo.py",
                unique_reviewers=1,
                total_reviews=10,
                total_comments=8,
                rubber_stamp_ratio=0.1,
                diversity_hhi=0.05,
            ),
        },
    )
    actions = RecommendationEngine().recommend(ctx)
    priorities = [a.priority for a in actions]
    assert priorities == sorted(priorities, key=lambda p: {"High": 0, "Medium": 1, "Low": 2}[p.value])
