from datetime import UTC, datetime, timedelta

from blindspot.ai_signal import (
    AIAmplificationDetector,
    AIFlag,
    AuthorProfiler,
    AuthorProfileType,
    QualitySignalEngine,
    SignalStrength,
)
from blindspot.collector.models import Commit, FileChange


def _commit(
    *,
    email: str,
    days_ago: int,
    additions: int = 10,
    deletions: int = 2,
    message: str = "update",
    files: tuple[FileChange, ...] | None = None,
    author_name: str = "Test User",
    hour: int = 12,
) -> Commit:
    now = datetime.now(UTC).replace(hour=hour, minute=0, second=0, microsecond=0)
    ts = now - timedelta(days=days_ago)
    if files is None:
        files = (FileChange(path="src/main.py", additions=additions, deletions=deletions),)
    return Commit(
        sha=f"sha{days_ago}",
        author_email=email,
        author_name=author_name,
        authored_at=ts,
        message=message,
        is_merge=False,
        files=files,
    )


# ---------- detector ----------

def test_detector_returns_low_when_no_change():
    commits = [
        _commit(email="alice@x.com", days_ago=d, additions=10, message="small change", hour=10)
        for d in (400, 380, 360, 340, 320, 300, 60, 40, 20)
    ]
    signals = AIAmplificationDetector().detect(commits)
    assert signals["alice@x.com"].flag == AIFlag.LOW


def test_detector_flags_high_when_recent_activity_jumps():
    baseline = [
        _commit(email="bob@x.com", days_ago=d, additions=15, message="tweak", hour=10)
        for d in (400, 380, 350, 320, 300, 280, 260, 240, 220, 200)
    ]
    recent = [
        _commit(
            email="bob@x.com",
            days_ago=d,
            additions=500,
            message="Add comprehensive validation with error handling and rollback safety net",
            hour=22,
        )
        for d in (5, 4, 3, 3, 2, 2, 2, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1)
    ]
    signals = AIAmplificationDetector().detect(baseline + recent)
    s = signals["bob@x.com"]
    assert s.flag == AIFlag.HIGH
    assert s.frequency_score > 0


def test_detector_ignores_authors_with_no_recent_activity():
    commits = [
        _commit(email="absent@x.com", days_ago=d, additions=20, message="m")
        for d in (400, 380, 360)
    ]
    signals = AIAmplificationDetector().detect(commits)
    assert "absent@x.com" not in signals


def test_detector_handles_insufficient_baseline():
    commits = [
        _commit(email="newhire@x.com", days_ago=d, additions=20, message="m")
        for d in (10, 8, 5, 2)
    ]
    signals = AIAmplificationDetector().detect(commits)
    s = signals["newhire@x.com"]
    assert s.flag == AIFlag.LOW
    assert s.score == 0.0


# ---------- quality ----------

def test_quality_engine_detects_bug_fix_pattern():
    commits = []
    for i in range(10):
        commits.append(
            _commit(email="bf@x.com", days_ago=i + 2, message="fix payment bug")
        )
    quality = QualitySignalEngine().assess(commits)
    assert quality["bf@x.com"].bug_keyword_score > 0.5


def test_quality_engine_low_test_coverage_when_only_code():
    commits = [
        _commit(
            email="prod@x.com",
            days_ago=i + 1,
            additions=200,
            files=(FileChange(path="src/payment.py", additions=200, deletions=0),),
            message="add feature",
        )
        for i in range(5)
    ]
    quality = QualitySignalEngine().assess(commits)
    assert quality["prod@x.com"].test_coverage_score > 0.5


def test_quality_engine_balanced_tests_dont_raise_flag():
    commits = []
    for i in range(5):
        commits.append(
            _commit(
                email="careful@x.com",
                days_ago=i + 1,
                files=(
                    FileChange(path="src/payment.py", additions=50, deletions=10),
                    FileChange(path="tests/test_payment.py", additions=40, deletions=0),
                ),
                message="add feature with tests",
            )
        )
    quality = QualitySignalEngine().assess(commits)
    assert quality["careful@x.com"].test_coverage_score == 0.0


# ---------- profile combination ----------

def test_profiler_classifies_real_growth_for_steady_activity():
    commits = [
        _commit(email="steady@x.com", days_ago=d, additions=20, message="t")
        for d in range(2, 400, 20)
    ]
    ai = AIAmplificationDetector().detect(commits)
    quality = QualitySignalEngine().assess(commits)
    profiles = AuthorProfiler().profile(commits, ai, quality)
    p = profiles["steady@x.com"]
    assert p.profile_type == AuthorProfileType.REAL_GROWTH
    assert p.evidence_weight == 1.0


def test_profiler_flags_fake_velocity_when_ai_high_and_quality_bad():
    baseline = [
        _commit(email="risky@x.com", days_ago=d, additions=10, message="tweak", hour=10)
        for d in range(220, 400, 15)
    ]
    recent = []
    for d in range(1, 40):
        recent.append(
            _commit(
                email="risky@x.com",
                days_ago=d,
                additions=400,
                deletions=20,
                files=(FileChange(path="src/core.py", additions=400, deletions=20),),
                message="Add comprehensive feature with error handling fix bug hotfix",
                hour=23,
            )
        )
    commits = baseline + recent
    ai = AIAmplificationDetector().detect(commits)
    quality = QualitySignalEngine().assess(commits)
    profiles = AuthorProfiler().profile(commits, ai, quality)
    p = profiles["risky@x.com"]
    assert p.ai_signal.flag == AIFlag.HIGH
    assert p.quality_signal.risk_score > 0.5
    assert p.profile_type == AuthorProfileType.FAKE_VELOCITY
    assert p.signal_strength == SignalStrength.LOW
    assert p.evidence_weight < 0.8


def test_profiler_classifies_bots_separately():
    commits = [
        _commit(
            email="dependabot[bot]@users.noreply.github.com",
            days_ago=d,
            author_name="dependabot[bot]",
            additions=5,
            message="bump foo from 1.0 to 1.1",
        )
        for d in range(2, 400, 10)
    ]
    ai = AIAmplificationDetector().detect(commits)
    quality = QualitySignalEngine().assess(commits)
    profiles = AuthorProfiler().profile(commits, ai, quality)
    p = profiles["dependabot[bot]@users.noreply.github.com"]
    assert p.profile_type == AuthorProfileType.BOT
    assert p.ai_signal is None
    assert p.quality_signal is None


def test_profiler_includes_author_name():
    commits = [
        _commit(
            email="named@x.com",
            days_ago=d,
            author_name="Named User",
        )
        for d in range(2, 400, 20)
    ]
    ai = AIAmplificationDetector().detect(commits)
    quality = QualitySignalEngine().assess(commits)
    profiles = AuthorProfiler().profile(commits, ai, quality)
    assert profiles["named@x.com"].author_name == "Named User"
