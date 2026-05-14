"""BitbucketPRCollector tests with a fake client.

The fake client dispatches `paginate` calls on the path so each
sub-resource (`/activity`, `/comments`, `/diffstat`) gets canned data.
"""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

from blindspot.collector.bitbucket.pr_collector import BitbucketPRCollector


def _iso(days_ago: int = 0) -> str:
    return (datetime.now(UTC) - timedelta(days=days_ago)).isoformat()


def _pr_summary(pr_id: int, days_ago: int = 5, *, author: str = "alice") -> dict:
    return {
        "id": pr_id,
        "title": f"PR #{pr_id}",
        "state": "MERGED",
        "author": {"nickname": author, "display_name": author.title()},
        "created_on": _iso(days_ago + 2),
        "updated_on": _iso(days_ago),
        "summary": {"raw": "PR description body"},
        "reviewers": [{"nickname": "bob"}],
    }


class _FakeClient:
    """Dispatches paginate() on the path. PR list is `params`-driven;
    sub-resources keyed by the trailing path segment."""

    def __init__(
        self,
        pr_list: list[dict],
        activity: dict[int, list[dict]] | None = None,
        comments: dict[int, list[dict]] | None = None,
        diffstat: dict[int, list[dict]] | None = None,
    ) -> None:
        self.pr_list = pr_list
        self.activity = activity or {}
        self.comments = comments or {}
        self.diffstat = diffstat or {}
        self.calls: list[str] = []

    def paginate(
        self, path: str, params: dict[str, Any] | None = None, **_: Any
    ) -> Iterator[Any]:
        self.calls.append(path)
        if path.endswith("/pullrequests"):
            yield from self.pr_list
            return
        # path looks like /repositories/ws/repo/pullrequests/{id}/{sub}
        parts = path.rstrip("/").split("/")
        sub = parts[-1]
        pr_id = int(parts[-2])
        if sub == "activity":
            yield from self.activity.get(pr_id, [])
        elif sub == "comments":
            yield from self.comments.get(pr_id, [])
        elif sub == "diffstat":
            yield from self.diffstat.get(pr_id, [])


def test_collect_maps_basic_pr_fields():
    client = _FakeClient(pr_list=[_pr_summary(1, days_ago=3)])
    collector = BitbucketPRCollector(client, "myteam", "myrepo", since_days=30)
    prs, truncated = collector.collect()

    assert truncated is False
    assert len(prs) == 1
    pr = prs[0]
    assert pr.number == 1
    assert pr.title == "PR #1"
    assert pr.author_login == "alice"
    assert pr.state == "merged"
    assert pr.merged is True
    assert pr.merged_at is not None
    assert pr.body == "PR description body"
    assert pr.requested_reviewers == ("bob",)


def test_collect_maps_approval_activity_to_reviews():
    activity = {
        1: [
            {"approval": {"user": {"nickname": "bob"}, "date": _iso(2)}},
            {"changes_requested": {"user": {"nickname": "carol"}, "date": _iso(3)}},
            {"update": {"date": _iso(4)}},  # not a review
        ]
    }
    client = _FakeClient(pr_list=[_pr_summary(1)], activity=activity)
    collector = BitbucketPRCollector(client, "myteam", "myrepo", since_days=30)
    prs, _ = collector.collect()

    states = {r.reviewer_login: r.state for r in prs[0].reviews}
    assert states == {"bob": "APPROVED", "carol": "CHANGES_REQUESTED"}


def test_collect_maps_comments_and_diffstat():
    comments = {
        1: [
            {
                "user": {"nickname": "bob"},
                "content": {"raw": "Handle the None case?"},
                "inline": {"path": "src/main.py", "to": 42},
                "created_on": _iso(2),
            }
        ]
    }
    diffstat = {
        1: [
            {
                "status": "modified",
                "lines_added": 10,
                "lines_removed": 3,
                "new": {"path": "src/main.py"},
            },
            {
                "status": "added",
                "lines_added": 20,
                "lines_removed": 0,
                "new": {"path": "src/new.py"},
            },
        ]
    }
    client = _FakeClient(
        pr_list=[_pr_summary(1)], comments=comments, diffstat=diffstat
    )
    collector = BitbucketPRCollector(client, "myteam", "myrepo", since_days=30)
    prs, _ = collector.collect()
    pr = prs[0]

    assert len(pr.review_comments) == 1
    rc = pr.review_comments[0]
    assert rc.reviewer_login == "bob"
    assert rc.path == "src/main.py"
    assert rc.line == 42

    assert len(pr.files) == 2
    assert pr.additions == 30
    assert pr.deletions == 3
    assert {f.path for f in pr.files} == {"src/main.py", "src/new.py"}


def test_collect_stops_at_window_cutoff():
    # Newest-first: PR 2 is inside the window, PR 1 is outside → stop at PR 1.
    client = _FakeClient(
        pr_list=[_pr_summary(2, days_ago=5), _pr_summary(1, days_ago=400)]
    )
    collector = BitbucketPRCollector(client, "myteam", "myrepo", since_days=180)
    prs, truncated = collector.collect()
    assert [p.number for p in prs] == [2]
    assert truncated is False


def test_collect_truncates_at_max_prs():
    client = _FakeClient(
        pr_list=[_pr_summary(i, days_ago=1) for i in range(10)]
    )
    collector = BitbucketPRCollector(
        client, "myteam", "myrepo", since_days=30, max_prs=3
    )
    prs, truncated = collector.collect()
    assert len(prs) == 3
    assert truncated is True


def test_collect_handles_display_name_fallback():
    # User with no nickname → fall back to display_name, lowercased.
    summary = _pr_summary(1)
    summary["author"] = {"display_name": "Alice Cooper"}
    client = _FakeClient(pr_list=[summary])
    collector = BitbucketPRCollector(client, "myteam", "myrepo", since_days=30)
    prs, _ = collector.collect()
    assert prs[0].author_login == "alice cooper"
