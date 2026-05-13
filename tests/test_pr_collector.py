import io
import json
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from blindspot.collector.github import GitHubClient, PRCollector


def _now_iso(days_ago: int = 0) -> str:
    return (datetime.now(UTC) - timedelta(days=days_ago)).isoformat().replace("+00:00", "Z")


def _resp(body, headers=None):
    headers = headers or {
        "X-RateLimit-Remaining": "50",
        "X-RateLimit-Limit": "60",
        "X-RateLimit-Reset": "1700000000",
    }
    resp = io.BytesIO(json.dumps(body).encode("utf-8"))
    resp.__enter__ = lambda self: self  # type: ignore[method-assign]
    resp.__exit__ = lambda *a: False  # type: ignore[method-assign]
    resp.headers = headers
    return resp


def _pr_summary(number: int, days_ago: int = 5, *, author: str = "alice") -> dict:
    return {
        "number": number,
        "title": f"PR #{number}",
        "user": {"login": author},
        "state": "closed",
        "merged_at": _now_iso(days_ago),
        "created_at": _now_iso(days_ago + 2),
        "updated_at": _now_iso(days_ago),
        "closed_at": _now_iso(days_ago),
        "body": "PR description body",
        "labels": [{"name": "enhancement"}],
        "milestone": {"title": "v1"},
        "requested_reviewers": [{"login": "bob"}],
    }


def _review_payload(reviewer: str, state: str = "APPROVED") -> dict:
    return {
        "user": {"login": reviewer},
        "state": state,
        "submitted_at": _now_iso(5),
        "body": "LGTM",
    }


def _comment_payload(reviewer: str, path: str = "src/main.py") -> dict:
    return {
        "user": {"login": reviewer},
        "body": "Could you handle the None case here?",
        "path": path,
        "line": 42,
        "created_at": _now_iso(5),
    }


def _file_payload(filename: str, additions: int = 10, deletions: int = 2) -> dict:
    return {
        "filename": filename,
        "status": "modified",
        "additions": additions,
        "deletions": deletions,
        "changes": additions + deletions,
    }


def test_collects_single_pr_with_full_enrichment():
    pr_list = [_pr_summary(101)]
    reviews = [_review_payload("bob"), _review_payload("carol", "COMMENTED")]
    comments = [_comment_payload("bob"), _comment_payload("carol", "src/util.py")]
    files = [_file_payload("src/main.py"), _file_payload("src/util.py")]

    responses = [_resp(pr_list), _resp(reviews), _resp(comments), _resp(files)]
    with patch("urllib.request.urlopen", side_effect=responses):
        prs, truncated = PRCollector(GitHubClient(), "owner", "repo", since_days=30).collect()

    assert not truncated
    assert len(prs) == 1
    pr = prs[0]
    assert pr.number == 101
    assert pr.author_login == "alice"
    assert pr.merged is True
    assert pr.labels == ("enhancement",)
    assert pr.milestone == "v1"
    assert pr.requested_reviewers == ("bob",)
    assert {r.reviewer_login for r in pr.reviews} == {"bob", "carol"}
    assert {c.path for c in pr.review_comments} == {"src/main.py", "src/util.py"}
    assert {f.path for f in pr.files} == {"src/main.py", "src/util.py"}
    assert pr.additions == 20
    assert pr.deletions == 4


def test_stops_at_since_window():
    pr_summaries = [_pr_summary(102, 5), _pr_summary(101, 400)]
    # Only PR 102 is in window → 1 enrichment burst (reviews/comments/files) before break.
    responses = [_resp(pr_summaries), _resp([]), _resp([]), _resp([])]
    with patch("urllib.request.urlopen", side_effect=responses):
        prs, truncated = PRCollector(GitHubClient(), "x", "y", since_days=30).collect()

    assert not truncated
    assert [pr.number for pr in prs] == [102]


def test_truncates_when_rate_limit_hits_during_enrichment():
    page1 = _resp([_pr_summary(101), _pr_summary(100)])
    low_headers = {
        "X-RateLimit-Remaining": "0",
        "X-RateLimit-Limit": "60",
        "X-RateLimit-Reset": "1700000000",
    }
    review_low = _resp([], headers=low_headers)
    responses = [page1, review_low]
    with patch("urllib.request.urlopen", side_effect=responses):
        prs, truncated = PRCollector(GitHubClient(), "x", "y", since_days=30).collect()
    assert truncated
