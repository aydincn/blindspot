from datetime import UTC, datetime, timedelta

from blindspot.collector import GitCollector
from blindspot.ownership import OwnershipEngine

from tests.conftest import CommitSpec


def _engine(*, days_offset: int = 0) -> OwnershipEngine:
    as_of = datetime.now(UTC) - timedelta(days=days_offset)
    return OwnershipEngine(as_of=as_of)


def test_single_author_has_full_coverage(make_repo):
    repo = make_repo([CommitSpec("Alice", "alice@x.com", "a.py", "x\n", 5)])
    commits = list(GitCollector(repo, since_days=30).collect())
    om = _engine().compute(commits)

    scores = om.for_file("a.py")
    assert len(scores) == 1
    assert scores[0].author_email == "alice@x.com"
    assert scores[0].coverage == 1.0


def test_coverage_normalises_to_one_per_file(make_repo):
    repo = make_repo(
        [
            CommitSpec("Alice", "alice@x.com", "shared.py", "1\n", 5),
            CommitSpec("Bob", "bob@x.com", "shared.py", "1\n2\n", 4),
        ]
    )
    commits = list(GitCollector(repo, since_days=30).collect())
    om = _engine().compute(commits)

    total = sum(s.coverage for s in om.for_file("shared.py"))
    assert abs(total - 1.0) < 1e-9


def test_decay_favours_recent_contributor_when_activity_is_equal(make_repo):
    """Same commit count and similar volume — recency should tip the balance."""
    repo = make_repo(
        [
            CommitSpec("Old", "old@x.com", "shared.py", "1\n", 170),
            CommitSpec("New", "new@x.com", "shared.py", "1\n2\n", 2),
        ]
    )
    commits = list(GitCollector(repo, since_days=365).collect())
    om = _engine().compute(commits)

    new = next(s for s in om.for_file("shared.py") if s.author_email == "new@x.com")
    old = next(s for s in om.for_file("shared.py") if s.author_email == "old@x.com")
    assert new.coverage > old.coverage


def test_one_recent_commit_outranks_three_old_commits(make_repo):
    """With per-commit decay, a single recent commit should beat several ancient ones."""
    repo = make_repo(
        [
            CommitSpec("Old", "old@x.com", "shared.py", "1\n", 170),
            CommitSpec("Old", "old@x.com", "shared.py", "1\n2\n", 165),
            CommitSpec("Old", "old@x.com", "shared.py", "1\n2\n3\n", 160),
            CommitSpec("New", "new@x.com", "shared.py", "1\n2\n3\n4\n", 2),
        ]
    )
    commits = list(GitCollector(repo, since_days=365).collect())
    om = _engine().compute(commits)

    scores = om.for_file("shared.py")
    assert scores[0].author_email == "new@x.com"
    assert scores[0].coverage > scores[1].coverage


def test_more_commits_means_more_ownership(make_repo):
    repo = make_repo(
        [
            CommitSpec("Heavy", "heavy@x.com", "shared.py", "1\n", 10),
            CommitSpec("Heavy", "heavy@x.com", "shared.py", "1\n2\n", 9),
            CommitSpec("Heavy", "heavy@x.com", "shared.py", "1\n2\n3\n", 8),
            CommitSpec("Light", "light@x.com", "shared.py", "1\n2\n3\n4\n", 7),
        ]
    )
    commits = list(GitCollector(repo, since_days=30).collect())
    om = _engine().compute(commits)

    scores = om.for_file("shared.py")
    heavy = next(s for s in scores if s.author_email == "heavy@x.com")
    light = next(s for s in scores if s.author_email == "light@x.com")
    assert heavy.coverage > light.coverage
    assert heavy.commit_count == 3
    assert light.commit_count == 1


def test_top_concentration_surfaces_riskiest_files(make_repo):
    repo = make_repo(
        [
            CommitSpec("Solo", "solo@x.com", "risky.py", "1\n", 5),
            CommitSpec("A", "a@x.com", "shared.py", "1\n", 5),
            CommitSpec("B", "b@x.com", "shared.py", "1\n2\n", 4),
        ]
    )
    commits = list(GitCollector(repo, since_days=30).collect())
    om = _engine().compute(commits)

    top = om.top_concentration(limit=5)
    assert top[0].file == "risky.py"
    assert top[0].coverage == 1.0
