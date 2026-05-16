from datetime import UTC, datetime

from blindspot.collector.models import Commit, FileChange
from blindspot.risk_models.correction_load import CorrectionLoadEngine


def _c(sha: str, email: str, message: str, files: tuple[str, ...] = ()) -> Commit:
    return Commit(
        sha=sha,
        author_email=email,
        author_name="A",
        authored_at=datetime.now(UTC),
        message=message,
        is_merge=False,
        files=tuple(FileChange(path=p, additions=10, deletions=2) for p in files),
    )


def test_correction_ratio_per_author():
    commits = [
        _c("1", "alice@x.com", "feat: add export", ("src/a.py",)),
        _c("2", "alice@x.com", "feat: add import", ("src/b.py",)),
        _c("3", "alice@x.com", "fix: import bug", ("src/b.py",)),
        _c("4", "alice@x.com", "fix: edge case", ("src/b.py",)),
        _c("5", "alice@x.com", "chore: tidy", ("src/c.py",)),
    ]
    report = CorrectionLoadEngine().compute(commits)
    assert len(report.authors) == 1
    a = report.authors[0]
    assert a.author_email == "alice@x.com"
    assert a.total_commits == 5
    assert a.fix_commits == 2
    assert a.feature_commits == 2
    assert a.correction_ratio == 0.4


def test_min_commits_filter_drops_low_volume_authors():
    commits = [
        _c("1", "alice@x.com", "fix: x", ("src/a.py",)),
        _c("2", "alice@x.com", "fix: y", ("src/a.py",)),
        # 2 commits — under min_commits_for_signal=5
    ]
    report = CorrectionLoadEngine().compute(commits)
    assert report.authors == ()


def test_risk_levels_use_thresholds():
    base = "alice@x.com"
    # 6 of 10 are corrections → 0.6 → critical (>= 0.50)
    commits = (
        [_c(str(i), base, "fix: x", ("src/a.py",)) for i in range(6)]
        + [_c(str(i + 6), base, "feat: y", ("src/a.py",)) for i in range(4)]
    )
    report = CorrectionLoadEngine().compute(commits)
    assert report.authors[0].risk_level == "critical"
    assert report.files[0].risk_level == "critical"


def test_per_file_correction_ratio():
    commits = [
        _c("1", "a@x.com", "feat: add", ("src/hot.py",)),
        _c("2", "a@x.com", "fix: bug", ("src/hot.py",)),
        _c("3", "a@x.com", "fix: regression", ("src/hot.py",)),
        _c("4", "a@x.com", "revert: rollback", ("src/hot.py",)),
        _c("5", "a@x.com", "chore: tidy", ("src/hot.py",)),
    ]
    report = CorrectionLoadEngine().compute(commits)
    f = report.files[0]
    assert f.file == "src/hot.py"
    assert f.total_commits == 5
    assert f.fix_commits == 2
    assert f.revert_commits == 1
    assert f.correction_ratio == 0.6


def test_merge_commits_are_excluded():
    commits = [
        Commit(
            sha="m1",
            author_email="a@x.com",
            author_name="A",
            authored_at=datetime.now(UTC),
            message="Merge branch 'main'",
            is_merge=True,
            files=(),
        ),
        _c("1", "a@x.com", "fix: a", ("src/a.py",)),
        _c("2", "a@x.com", "fix: b", ("src/a.py",)),
        _c("3", "a@x.com", "feat: c", ("src/a.py",)),
        _c("4", "a@x.com", "feat: d", ("src/a.py",)),
        _c("5", "a@x.com", "chore: e", ("src/a.py",)),
    ]
    report = CorrectionLoadEngine().compute(commits)
    assert report.authors[0].total_commits == 5  # merge excluded


def test_empty_commits_produces_empty_report():
    report = CorrectionLoadEngine().compute([])
    assert report.authors == ()
    assert report.files == ()
