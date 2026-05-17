"""Business implication mapper tests — deterministic signal → CTO-language."""

from datetime import UTC, datetime
from dataclasses import replace

from blindspot import __version__
from blindspot.narrative.business_implication import business_implication
from blindspot.report.context import ReportContext
from blindspot.review_graph.engine import FileReviewStats
from blindspot.risk_models.ai_readiness import (
    AIReadinessCoverage,
    AIReadinessReport,
)
from blindspot.risk_models.bus_factor import ServiceBusFactor
from blindspot.risk_models.correction_load import FileCorrectionLoad
from blindspot.risk_models.departure import DepartureReport


def _ctx(**overrides) -> ReportContext:
    base = ReportContext(
        repo_path="/tmp/r",
        generated_at=datetime.now(UTC),
        since_days=180,
        blindspot_version=__version__,
        commit_count=100, author_count=5, file_count=100,
        additions=0, deletions=0,
        services=(), critical_files=(),
        decay_top=(), decay_services=(),
    )
    return replace(base, **overrides)


def _departure(orphans: int) -> DepartureReport:
    return DepartureReport(
        departing=("alice@x.com",), files=(), services=(),
        total_files=200, affected_files=orphans + 5,
        orphaned_files=orphans, avg_coverage_loss=0.4,
    )


def _service(name: str, files: int = 8) -> ServiceBusFactor:
    return ServiceBusFactor(
        service=name, file_count=files, bus_factor=1, threshold=0.8,
        risk_level="critical", top_owners=(("a@x.com", 0.9),),
    )


def test_returns_none_when_no_signal():
    assert business_implication(_ctx()) is None


def test_high_orphans_team_profile_yields_delivery_sentence():
    ctx = _ctx(
        departure_scenarios=(_departure(orphans=40),),
        repo_profile="team",
    )
    msg = business_implication(ctx)
    assert msg is not None
    assert "40" in msg
    assert "deliver" in msg.lower() or "delivery" in msg.lower()


def test_high_orphans_founder_led_uses_structural_language():
    ctx = _ctx(
        departure_scenarios=(_departure(orphans=40),),
        repo_profile="founder-led",
    )
    msg = business_implication(ctx)
    assert msg is not None
    assert "structural" in msg.lower() or "single-maintainer" in msg.lower()


def test_multiple_single_owner_services_yields_services_sentence():
    ctx = _ctx(
        services=(_service("a"), _service("b"), _service("c")),
        repo_profile="team",
    )
    msg = business_implication(ctx)
    assert msg is not None
    assert "services" in msg.lower()


def test_correction_load_drives_stability_message():
    files = tuple(
        FileCorrectionLoad(
            file=f"src/x{i}.py", total_commits=20, fix_commits=8,
            revert_commits=2, correction_ratio=0.5, risk_level="critical",
        )
        for i in range(6)
    )
    ctx = _ctx(correction_load_files=files, repo_profile="team")
    msg = business_implication(ctx)
    assert msg is not None
    assert "correction" in msg.lower() or "stability" in msg.lower() or "confidence" in msg.lower()


def test_rubber_stamp_drives_review_theatre_message():
    files = tuple(
        FileReviewStats(
            file=f"src/x{i}.py", unique_reviewers=2, total_reviews=10,
            total_comments=1, rubber_stamp_ratio=0.85, diversity_hhi=0.5,
        )
        for i in range(4)
    )
    ctx = _ctx(top_rubber_stamps=files, repo_profile="team")
    msg = business_implication(ctx)
    assert msg is not None
    assert "review" in msg.lower()


def test_doc_only_profile_always_yields_caveat():
    ctx = _ctx(repo_profile="doc-only")
    msg = business_implication(ctx)
    assert msg is not None
    assert "code surface" in msg.lower() or "informational" in msg.lower()


def test_ai_readiness_gap_when_nothing_louder():
    services = tuple(
        AIReadinessCoverage(target=f"svc{i}", agent_rules=False, specs=False,
                            prompts=False, architecture=False, skills=False)
        for i in range(4)
    )
    report = AIReadinessReport(
        repo=AIReadinessCoverage(target="(repo)", agent_rules=False, specs=False,
                                 prompts=False, architecture=False, skills=False),
        services=services,
    )
    ctx = _ctx(ai_readiness=report, repo_profile="team")
    msg = business_implication(ctx)
    assert msg is not None
    assert "ai" in msg.lower() or "onboarding" in msg.lower() or "context" in msg.lower()


def test_turkish_language_produces_turkish_sentence():
    ctx = _ctx(
        departure_scenarios=(_departure(orphans=40),),
        repo_profile="team",
    )
    msg = business_implication(ctx, language="tr")
    assert msg is not None
    assert "ayrılış" in msg.lower() or "feature" in msg.lower()
