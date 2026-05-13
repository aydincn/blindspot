from datetime import UTC, datetime, timedelta

from blindspot.collector.github.pr_models import (
    PullRequest,
    PullRequestFile,
    Review,
    ReviewComment,
)
from blindspot.review_graph import ReviewGraphBuilder


def _pr(
    number: int,
    *,
    files: tuple[str, ...] = (),
    reviews: tuple[tuple[str, str], ...] = (),
    comments: tuple[tuple[str, str], ...] = (),
) -> PullRequest:
    now = datetime.now(UTC)
    return PullRequest(
        number=number,
        title=f"PR #{number}",
        author_login="alice",
        state="closed",
        merged=True,
        created_at=now,
        closed_at=now,
        merged_at=now,
        body="",
        labels=(),
        milestone=None,
        requested_reviewers=(),
        files=tuple(
            PullRequestFile(path=p, status="modified", additions=10, deletions=2, changes=12)
            for p in files
        ),
        reviews=tuple(
            Review(reviewer_login=login, state=state, submitted_at=now, body="")
            for login, state in reviews
        ),
        review_comments=tuple(
            ReviewComment(reviewer_login=login, body="", path=path, line=1, submitted_at=now)
            for login, path in comments
        ),
        additions=10 * len(files),
        deletions=2 * len(files),
    )


def test_review_increments_per_file_in_pr():
    prs = [
        _pr(
            1,
            files=("a.py", "b.py"),
            reviews=(("bob", "APPROVED"),),
        )
    ]
    graph = ReviewGraphBuilder().build(prs)
    # Each file in the PR gets a review by Bob → 1 review * 0.5 = 0.5
    assert graph.score_for("bob", "a.py") == 0.5
    assert graph.score_for("bob", "b.py") == 0.5


def test_comments_add_to_score_per_file():
    prs = [
        _pr(
            1,
            files=("a.py",),
            reviews=(("bob", "APPROVED"),),
            comments=(("bob", "a.py"), ("bob", "a.py")),
        )
    ]
    graph = ReviewGraphBuilder().build(prs)
    # 1 review (0.5) + 2 comments (2.0) = 2.5
    assert graph.score_for("bob", "a.py") == 2.5


def test_rubber_stamp_ratio_high_when_approval_without_comments():
    prs = [
        _pr(
            1,
            files=("a.py",),
            reviews=(("bob", "APPROVED"),),
        ),
        _pr(
            2,
            files=("a.py",),
            reviews=(("carol", "APPROVED"),),
            comments=(("carol", "a.py"),),
        ),
    ]
    graph = ReviewGraphBuilder().build(prs)
    stats = graph.stats_for("a.py")
    assert stats is not None
    assert stats.unique_reviewers == 2
    # Bob's approval is rubber-stamp (no comments), carol's is not → 0.5
    assert stats.rubber_stamp_ratio == 0.5


def test_diversity_is_higher_when_multiple_reviewers_share_load():
    prs_solo = [
        _pr(i, files=("a.py",), reviews=(("bob", "APPROVED"),)) for i in range(5)
    ]
    prs_shared = [
        _pr(1, files=("a.py",), reviews=(("bob", "APPROVED"),)),
        _pr(2, files=("a.py",), reviews=(("carol", "APPROVED"),)),
        _pr(3, files=("a.py",), reviews=(("dave", "APPROVED"),)),
    ]
    solo_graph = ReviewGraphBuilder().build(prs_solo)
    shared_graph = ReviewGraphBuilder().build(prs_shared)
    assert solo_graph.stats_for("a.py").diversity_hhi < shared_graph.stats_for("a.py").diversity_hhi


def test_records_median_approval_latency():
    base = datetime.now(UTC)
    pr_a = PullRequest(
        number=1, title="t", author_login="alice", state="closed", merged=True,
        created_at=base, closed_at=base, merged_at=base, body="", labels=(),
        milestone=None, requested_reviewers=(),
        files=(PullRequestFile(path="src/a.py", status="modified", additions=10, deletions=2, changes=12),),
        reviews=(Review(reviewer_login="bob", state="APPROVED", submitted_at=base + timedelta(minutes=5), body=""),),
        review_comments=(),
        additions=10, deletions=2,
    )
    pr_b = PullRequest(
        number=2, title="t", author_login="alice", state="closed", merged=True,
        created_at=base, closed_at=base, merged_at=base, body="", labels=(),
        milestone=None, requested_reviewers=(),
        files=(PullRequestFile(path="src/a.py", status="modified", additions=10, deletions=2, changes=12),),
        reviews=(Review(reviewer_login="bob", state="APPROVED", submitted_at=base + timedelta(minutes=15), body=""),),
        review_comments=(),
        additions=10, deletions=2,
    )
    graph = ReviewGraphBuilder().build([pr_a, pr_b])
    stats = graph.stats_for("src/a.py")
    assert stats is not None
    # Median of 5 and 15 minutes = 10 minutes = 600 seconds
    assert stats.median_approval_latency_seconds == 600
    assert stats.approval_sample_size == 2


def test_ownership_engine_integrates_review_score(make_repo):
    from blindspot.collector import GitCollector
    from blindspot.ownership import OwnershipEngine
    from tests.conftest import CommitSpec

    repo = make_repo(
        [
            CommitSpec("Alice", "111+alice@users.noreply.github.com", "a.py", "1\n", 5),
            CommitSpec("Alice", "111+alice@users.noreply.github.com", "a.py", "1\n2\n", 4),
        ]
    )
    commits = list(GitCollector(repo, since_days=30).collect())
    graph = ReviewGraphBuilder().build(
        [_pr(1, files=("a.py",), reviews=(("alice", "APPROVED"),), comments=(("alice", "a.py"),))]
    )

    om_with_reviews = OwnershipEngine().compute(commits, review_graph=graph)
    om_without_reviews = OwnershipEngine().compute(commits)

    fo_with = om_with_reviews.for_file("a.py")[0]
    fo_without = om_without_reviews.for_file("a.py")[0]
    assert fo_with.raw_score > fo_without.raw_score
