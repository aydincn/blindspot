"""Fragile Velocity pattern detector tests."""

from datetime import UTC, datetime
from dataclasses import replace

from blindspot import __version__
from blindspot.patterns.fragile_velocity import detect_fragile_velocity
from blindspot.patterns.models import PatternSeverity
from blindspot.report.context import ReportContext
from blindspot.review_graph.engine import FileReviewStats
from blindspot.risk_models.ai_readiness import (
    AIReadinessCoverage,
    AIReadinessReport,
)
from blindspot.risk_models.bus_factor import FileBusFactor
from blindspot.risk_models.correction_load import FileCorrectionLoad


def _ctx(**overrides):
    base = ReportContext(
        repo_path="/tmp/r",
        generated_at=datetime.now(UTC),
        since_days=180, blindspot_version=__version__,
        commit_count=0, author_count=0, file_count=0,
        additions=0, deletions=0,
        services=(), critical_files=(),
        decay_top=(), decay_services=(),
    )
    return replace(base, **overrides)


def _critical_files(n):
    return tuple(
        FileBusFactor(
            file=f"src/x{i}.py", bus_factor=1, threshold=0.8,
            risk_level="critical",
            top_owners=(("alice@x.com", 0.95),),
        )
        for i in range(n)
    )


def _rubber(n):
    return tuple(
        FileReviewStats(
            file=f"src/x{i}.py", unique_reviewers=1, total_reviews=10,
            total_comments=1, rubber_stamp_ratio=0.85, diversity_hhi=0.5,
        )
        for i in range(n)
    )


def _corr(n):
    return tuple(
        FileCorrectionLoad(
            file=f"src/x{i}.py", total_commits=20, fix_commits=8,
            revert_commits=2, correction_ratio=0.5, risk_level="critical",
        )
        for i in range(n)
    )


def _ai_gap(n):
    services = tuple(
        AIReadinessCoverage(target=f"svc{i}", agent_rules=False, specs=False,
                            prompts=False, architecture=False, skills=False)
        for i in range(n)
    )
    return AIReadinessReport(
        repo=AIReadinessCoverage(target="(repo)", agent_rules=False, specs=False,
                                 prompts=False, architecture=False, skills=False),
        services=services,
    )


def test_no_pattern_when_only_one_axis():
    ctx = _ctx(critical_files=_critical_files(10))
    assert detect_fragile_velocity(ctx) is None


def test_no_pattern_when_two_axes():
    ctx = _ctx(
        critical_files=_critical_files(10),
        top_rubber_stamps=_rubber(3),
    )
    assert detect_fragile_velocity(ctx) is None


def test_pattern_fires_at_three_axes_with_medium_severity():
    ctx = _ctx(
        critical_files=_critical_files(10),
        top_rubber_stamps=_rubber(3),
        correction_load_files=_corr(5),
    )
    hit = detect_fragile_velocity(ctx)
    assert hit is not None
    assert hit.key == "fragile_velocity"
    assert hit.severity == PatternSeverity.MEDIUM
    assert hit.score == 0.75


def test_pattern_fires_at_four_axes_with_high_severity():
    ctx = _ctx(
        critical_files=_critical_files(10),
        top_rubber_stamps=_rubber(3),
        correction_load_files=_corr(5),
        ai_readiness=_ai_gap(4),
    )
    hit = detect_fragile_velocity(ctx)
    assert hit is not None
    assert hit.severity == PatternSeverity.HIGH
    assert hit.score == 1.0


def test_description_names_each_triggering_axis():
    ctx = _ctx(
        critical_files=_critical_files(10),
        top_rubber_stamps=_rubber(3),
        correction_load_files=_corr(5),
        ai_readiness=_ai_gap(4),
    )
    hit = detect_fragile_velocity(ctx)
    assert "single owner" in hit.description.lower()
    assert "rubber-stamp" in hit.description.lower()
    assert "correction" in hit.description.lower()
    assert "ai-readable" in hit.description.lower() or "operational context" in hit.description.lower()


def test_evidence_dict_includes_all_axis_counts():
    ctx = _ctx(
        critical_files=_critical_files(10),
        top_rubber_stamps=_rubber(3),
        correction_load_files=_corr(5),
        ai_readiness=_ai_gap(4),
    )
    hit = detect_fragile_velocity(ctx)
    assert "concentration" in hit.evidence
    assert "low_diversity" in hit.evidence
    assert "correction" in hit.evidence
    assert "ai_gap" in hit.evidence
