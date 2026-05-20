from datetime import UTC, datetime

from blindspot.actions import (
    ActionCategory,
    ActionPriority,
    FragilityPattern,
    RecommendationContext,
    RecommendationEngine,
)
from blindspot.review_graph.engine import FileReviewStats
from blindspot.risk_models.bus_factor import FileBusFactor, ServiceBusFactor
from blindspot.risk_models.correction_load import FileCorrectionLoad
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
    # 3 files: above the min_service_files_for_action threshold but below
    # the HIGH priority threshold (5).
    ctx = RecommendationContext(
        services=(_service("util", 3, "alice@x.com", 0.9),),
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


def test_correction_load_emits_fragile_velocity_recommendation():
    f = FileCorrectionLoad(
        file="src/hot.py",
        total_commits=20,
        fix_commits=8,
        revert_commits=2,
        correction_ratio=0.50,
        risk_level="critical",
    )
    ctx = RecommendationContext(correction_load_files=(f,))
    actions = RecommendationEngine().recommend(ctx)
    a = next(a for a in actions if a.category == ActionCategory.QUALITY_GUARDRAIL)
    assert a.pattern == FragilityPattern.FRAGILE_VELOCITY
    assert "src/hot.py" in a.target
    # Targets a file (work surface), not a person.
    assert "@" not in a.target


def test_correction_load_below_threshold_emits_nothing():
    f = FileCorrectionLoad(
        file="src/calm.py",
        total_commits=20,
        fix_commits=3,
        revert_commits=0,
        correction_ratio=0.15,
        risk_level="healthy",
    )
    ctx = RecommendationContext(correction_load_files=(f,))
    actions = RecommendationEngine().recommend(ctx)
    assert not any(a.pattern == FragilityPattern.FRAGILE_VELOCITY for a in actions)


# ---------------------------------------------------------------------------
# Service-bus-factor enrichment with service_top_files (0.0.5c)

def test_service_bus_factor_includes_start_with_when_top_file_provided():
    svc = _service("payment", 8, "alice@x.com", 0.85)
    ctx = RecommendationContext(
        services=(svc,),
        service_top_files={"payment": ("src/payment/checkout.py",)},
    )
    actions = RecommendationEngine().recommend(ctx)
    a = next(a for a in actions if a.category == ActionCategory.OWNERSHIP_DIVERSIFICATION)
    assert "Start with: src/payment/checkout.py" in a.description
    assert "top_files=src/payment/checkout.py" in a.evidence


def test_service_bus_factor_omits_start_with_when_no_top_file():
    svc = _service("payment", 8, "alice@x.com", 0.85)
    ctx = RecommendationContext(services=(svc,))  # no service_top_files
    actions = RecommendationEngine().recommend(ctx)
    a = next(a for a in actions if a.category == ActionCategory.OWNERSHIP_DIVERSIFICATION)
    assert "Start with:" not in a.description
    assert "top_files=" not in a.evidence


# ---------------------------------------------------------------------------
# Support-service exclusion (0.0.5d) — .github / docs / tests etc. should
# not generate "diversify ownership" or "add AI context" recommendations.

def test_support_services_skip_diversification_rule():
    # All four are in SUPPORT_SERVICES; none should produce an action.
    services = (
        _service(".github", 5, "alice@x.com", 0.95),
        _service("docs", 30, "alice@x.com", 0.95),
        _service("tests", 80, "alice@x.com", 0.95),
        _service("scripts", 4, "alice@x.com", 0.95),
    )
    ctx = RecommendationContext(services=services)
    actions = RecommendationEngine().recommend(ctx)
    assert not any(
        a.category == ActionCategory.OWNERSHIP_DIVERSIFICATION
        for a in actions
    )


def test_product_service_still_fires_diversification_rule():
    svc = _service("payment", 8, "alice@x.com", 0.85)
    ctx = RecommendationContext(services=(svc,))
    actions = RecommendationEngine().recommend(ctx)
    assert any(
        a.category == ActionCategory.OWNERSHIP_DIVERSIFICATION
        and "payment" in a.target
        for a in actions
    )


def test_tiny_services_skip_diversification_rule():
    # 1- and 2-file services don't warrant a "diversify ownership" action.
    services = (
        _service("solo", 1, "alice@x.com", 0.95),
        _service("tiny", 2, "alice@x.com", 0.95),
    )
    ctx = RecommendationContext(services=services)
    actions = RecommendationEngine().recommend(ctx)
    assert not any(
        a.category == ActionCategory.OWNERSHIP_DIVERSIFICATION for a in actions
    )


def test_service_bus_factor_lists_top_3_files_and_adds_cadence_for_large_service():
    """0.0.5e — turn '1589 files' into a concrete list + cadence."""
    svc = _service("payment", 60, "alice@x.com", 0.85)
    ctx = RecommendationContext(
        services=(svc,),
        service_top_files={"payment": (
            "src/payment/checkout.py",
            "src/payment/cart.py",
            "src/payment/refund.py",
        )},
    )
    actions = RecommendationEngine().recommend(ctx)
    a = next(a for a in actions if a.category == ActionCategory.OWNERSHIP_DIVERSIFICATION)
    assert "Start with these 3 files" in a.description
    assert "src/payment/checkout.py" in a.description
    assert "src/payment/refund.py" in a.description
    # Large service → sprint cadence hint
    assert "one file per sprint" in a.description.lower()


def test_service_bus_factor_quarterly_cadence_for_medium_service():
    svc = _service("api", 20, "alice@x.com", 0.85)
    ctx = RecommendationContext(
        services=(svc,),
        service_top_files={"api": ("src/api/auth.py", "src/api/users.py")},
    )
    actions = RecommendationEngine().recommend(ctx)
    a = next(a for a in actions if a.category == ActionCategory.OWNERSHIP_DIVERSIFICATION)
    assert "this quarter" in a.description.lower()


def test_service_bus_factor_no_cadence_for_small_service():
    svc = _service("util", 5, "alice@x.com", 0.85)
    ctx = RecommendationContext(
        services=(svc,),
        service_top_files={"util": ("src/util/helpers.py",)},
    )
    actions = RecommendationEngine().recommend(ctx)
    a = next(a for a in actions if a.category == ActionCategory.OWNERSHIP_DIVERSIFICATION)
    assert "sprint" not in a.description.lower()
    assert "quarter" not in a.description.lower()
