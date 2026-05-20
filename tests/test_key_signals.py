"""Key signals — the six core pill metrics."""

from dataclasses import replace
from datetime import UTC, datetime

from blindspot import __version__
from blindspot.narrative.key_signals import build_key_signals
from blindspot.report.context import ReportContext
from blindspot.review_graph.engine import FileReviewStats
from blindspot.risk_models.ai_readiness import (
    AIReadinessCoverage,
    AIReadinessReport,
)
from blindspot.risk_models.bus_factor import ServiceBusFactor
from blindspot.risk_models.correction_load import FileCorrectionLoad
from blindspot.risk_models.departure import DepartureReport
from blindspot.resilience.score import ResilienceScore


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


def _service(name: str) -> ServiceBusFactor:
    return ServiceBusFactor(
        service=name, file_count=8, bus_factor=1, threshold=0.8,
        risk_level="critical", top_owners=(("a@x.com", 0.9),),
    )


def _readiness(repo_count: int, service_count: int = 0) -> AIReadinessReport:
    def _cov(target, n):
        flags = [True] * n + [False] * (5 - n)
        return AIReadinessCoverage(
            target=target, agent_rules=flags[0], specs=flags[1],
            prompts=flags[2], architecture=flags[3], skills=flags[4],
        )
    return AIReadinessReport(
        repo=_cov("(repo)", repo_count),
        services=tuple(_cov(f"svc{i}", 0) for i in range(service_count)),
    )


def test_six_signals_always_returned():
    sigs = build_key_signals(_ctx())
    assert len(sigs) == 6
    names = [s.name for s in sigs]
    assert names == [
        "Ownership concentration",
        "Single-engineer dependency",
        "Knowledge decay",
        "Review depth",
        "Correction load",
        "AI-readable context",
    ]


def test_healthy_signal_drops_grade():
    """A green ✓ pill must not carry an F — grades only on risk signals."""
    sigs = build_key_signals(_ctx())
    for s in sigs:
        if s.healthy:
            assert s.grade is None, f"{s.name} healthy but has grade {s.grade}"


def test_ownership_signal_counts_single_owner_services():
    ctx = _ctx(services=(_service("a"), _service("b"), _service("c")))
    own = build_key_signals(ctx)[0]
    assert not own.healthy
    assert "3 service" in own.headline


def test_ownership_healthy_when_no_single_owner():
    healthy_svc = ServiceBusFactor(
        service="a", file_count=8, bus_factor=3, threshold=0.8,
        risk_level="healthy", top_owners=(("a@x.com", 0.4),),
    )
    own = build_key_signals(_ctx(services=(healthy_svc,)))[0]
    assert own.healthy


def test_ai_readiness_is_repo_level_not_per_service():
    """The alarmist 'N services lack…' is gone — assessment is repo-root."""
    # 20 sub-services all bare, but repo root has 3/5 coverage.
    ctx = _ctx(ai_readiness=_readiness(repo_count=3, service_count=20))
    ai = build_key_signals(ctx)[5]
    assert ai.healthy is True
    assert "3/5" in ai.headline
    # must NOT mention a per-service count
    assert "20 service" not in ai.headline


def test_ai_readiness_risk_when_repo_root_bare():
    ctx = _ctx(ai_readiness=_readiness(repo_count=0, service_count=5))
    ai = build_key_signals(ctx)[5]
    assert ai.healthy is False
    assert "0/5" in ai.headline
    assert "CLAUDE.md" in ai.meaning


def test_correction_load_signal_counts_heavy_files():
    files = tuple(
        FileCorrectionLoad(
            file=f"f{i}.py", total_commits=20, fix_commits=10,
            revert_commits=2, correction_ratio=0.6, risk_level="critical",
        )
        for i in range(4)
    )
    sig = build_key_signals(_ctx(correction_load_files=files))[4]
    assert not sig.healthy
    assert "4 files" in sig.headline


def _resilience(correction: int) -> ResilienceScore:
    return ResilienceScore(
        overall=80, ownership=None, decay=None, review=None,
        correction_load=correction, ai_readiness=None,
        band="Strong", summary="",
    )


def test_correction_load_grade_a_keeps_pill_healthy():
    """A risk pill must never carry an A: 36 hot files in a big repo with a
    repo-wide A grade is statistically normal, not a fragility signal."""
    files = tuple(
        FileCorrectionLoad(
            file=f"f{i}.py", total_commits=20, fix_commits=10,
            revert_commits=2, correction_ratio=0.6, risk_level="critical",
        )
        for i in range(36)
    )
    ctx = _ctx(correction_load_files=files, resilience=_resilience(95))
    sig = build_key_signals(ctx)[4]
    assert sig.healthy is True
    assert sig.grade is None  # healthy pills drop the grade
    assert "heavy bugfix tail" not in sig.headline


def test_correction_load_low_grade_is_a_risk():
    files = tuple(
        FileCorrectionLoad(
            file=f"f{i}.py", total_commits=20, fix_commits=10,
            revert_commits=2, correction_ratio=0.6, risk_level="critical",
        )
        for i in range(4)
    )
    ctx = _ctx(correction_load_files=files, resilience=_resilience(45))
    sig = build_key_signals(ctx)[4]
    assert sig.healthy is False
    assert "4 files" in sig.headline


def test_departure_signal_uses_worst_scenario():
    dep = DepartureReport(
        departing=("a@x.com",), files=(), services=(),
        total_files=200, affected_files=60, orphaned_files=55,
        avg_coverage_loss=0.4,
    )
    sig = build_key_signals(_ctx(departure_scenarios=(dep,)))[1]
    assert not sig.healthy
    assert "55 files" in sig.headline


def test_review_signal_no_data_path():
    sig = build_key_signals(_ctx())[3]
    assert sig.healthy
    assert "No review data" in sig.headline
