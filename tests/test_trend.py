from datetime import UTC, datetime, timedelta

from blindspot.collector.git import Commit, FileChange
from blindspot.trend import TrendEngine


def _commit(email: str, files: tuple[str, ...], days_ago: int) -> Commit:
    now = datetime.now(UTC)
    return Commit(
        sha=f"{email}-{days_ago}-{'-'.join(files)}",
        author_name=email.split("@")[0],
        author_email=email,
        authored_at=now - timedelta(days=days_ago),
        message="msg",
        files=tuple(
            FileChange(path=f, additions=10, deletions=2) for f in files
        ),
        is_merge=False,
    )


def test_trend_produces_snapshot_per_offset_with_data():
    commits = [
        _commit("alice@x.com", ("svc1/a.py",), days_ago=100),
        _commit("alice@x.com", ("svc1/a.py",), days_ago=70),
        _commit("bob@x.com", ("svc1/b.py",), days_ago=40),
        _commit("carol@x.com", ("svc1/c.py",), days_ago=10),
    ]
    trend = TrendEngine().compute(commits)
    # Snapshots ordered oldest → newest. With 90/60/30/0 offsets all should yield data.
    days = [s.days_ago for s in trend.snapshots]
    assert days == [90, 60, 30, 0]
    # Latest snapshot has most data — should not be None.
    assert trend.latest is not None
    assert trend.latest.score.overall > 0


def test_trend_skips_offsets_with_no_data():
    # All commits within last 20 days. The 90/60/30 offsets have nothing yet.
    commits = [
        _commit("alice@x.com", ("a.py",), days_ago=15),
        _commit("bob@x.com", ("b.py",), days_ago=10),
    ]
    trend = TrendEngine().compute(commits)
    days = [s.days_ago for s in trend.snapshots]
    assert days == [0]  # only "now" snapshot has data


def test_trend_delta_reflects_score_change():
    # Concentrated single-owner past, then diversified recent → ownership improves.
    commits = [
        _commit("alice@x.com", ("svc1/a.py",), days_ago=120),
        _commit("alice@x.com", ("svc1/b.py",), days_ago=120),
        _commit("alice@x.com", ("svc1/c.py",), days_ago=120),
        # Recent diversification
        _commit("bob@x.com", ("svc1/a.py",), days_ago=10),
        _commit("carol@x.com", ("svc1/b.py",), days_ago=5),
    ]
    trend = TrendEngine().compute(commits)
    assert len(trend.snapshots) >= 2
    # delta_overall is latest - oldest; non-None when ≥2 snapshots.
    assert trend.delta_overall is not None


def test_trend_empty_commits_returns_no_snapshots():
    trend = TrendEngine().compute([])
    assert trend.snapshots == ()
    assert trend.latest is None
    assert trend.delta_overall is None
