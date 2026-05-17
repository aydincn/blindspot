from datetime import UTC, datetime, timedelta

from blindspot.collector.models import Commit, FileChange
from blindspot.resilience.change_fear import compute_change_fear


def _c(sha, email, files, days_ago):
    return Commit(
        sha=sha, author_email=email, author_name="A",
        authored_at=datetime.now(UTC) - timedelta(days=days_ago),
        message="x", is_merge=False,
        files=tuple(FileChange(path=p, additions=1, deletions=0) for p in files),
    )


def test_flags_high_importance_low_contributor_long_neglect():
    commits = [
        _c("1", "alice@x.com", ["core/engine.py"], days_ago=200),
        _c("2", "alice@x.com", ["core/engine.py"], days_ago=180),
    ]
    importance = {"core/engine.py": 0.05}
    report = compute_change_fear(commits, importance)
    assert len(report.files) == 1
    f = report.files[0]
    assert f.file == "core/engine.py"
    assert f.contributor_count == 1
    assert f.fear_score > 0
    assert f.risk_level in ("critical", "high")


def test_skips_recently_touched_files():
    # 5 days ago — well below min_days_since_touch
    commits = [_c("1", "alice@x.com", ["core/engine.py"], days_ago=5)]
    importance = {"core/engine.py": 0.05}
    report = compute_change_fear(commits, importance)
    assert report.files == ()


def test_skips_low_importance_files():
    commits = [_c("1", "alice@x.com", ["scripts/oneshot.py"], days_ago=200)]
    importance = {"scripts/oneshot.py": 0.001}  # below 0.005
    report = compute_change_fear(commits, importance)
    assert report.files == ()


def test_more_contributors_lower_fear_score():
    base_importance = {"core/engine.py": 0.05}
    # Same file, 200 days neglect — vary contributor count
    single = compute_change_fear(
        [_c("1", "alice@x.com", ["core/engine.py"], days_ago=200)],
        base_importance,
    )
    plural = compute_change_fear(
        [
            _c("1", "alice@x.com", ["core/engine.py"], days_ago=200),
            _c("2", "bob@x.com", ["core/engine.py"], days_ago=210),
            _c("3", "carol@x.com", ["core/engine.py"], days_ago=220),
        ],
        base_importance,
    )
    assert single.files[0].fear_score > plural.files[0].fear_score
