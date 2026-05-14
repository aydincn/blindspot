"""Collect pull-request + review data from Bitbucket Cloud.

Produces the same provider-agnostic `PullRequest` objects as the GitHub
collector, so everything downstream (review graph, diff analysis,
AI-signal quality) treats both providers identically.

Per PR we fetch three sub-resources:
  * `/activity`  → approval / changes-requested events → `Review`s
  * `/comments`  → inline + general comments → `ReviewComment`s
  * `/diffstat`  → per-file line churn → `PullRequestFile`s

Bitbucket has no clean `merged_at` on the PR summary, so for a MERGED /
DECLINED / SUPERSEDED PR we use `updated_on` as the close timestamp —
an approximation, but good enough for review-latency bucketing.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from blindspot.collector.bitbucket.client import BitbucketClient, BitbucketError
from blindspot.collector.review_models import (
    PullRequest,
    PullRequestFile,
    Review,
    ReviewComment,
)

_TERMINAL_STATES = {"MERGED", "DECLINED", "SUPERSEDED"}


@dataclass
class BitbucketPRCollector:
    client: BitbucketClient
    workspace: str
    repo: str
    since_days: int = 180
    max_prs: int = 200

    def collect(self) -> tuple[list[PullRequest], bool]:
        """Return (prs_collected, was_truncated).

        `was_truncated` is True only when we stopped at `max_prs` with
        more PRs still inside the window — mirrors the GitHub collector's
        signal so the report can warn about partial data.
        """
        cutoff = datetime.now(UTC) - timedelta(days=self.since_days)
        out: list[PullRequest] = []
        truncated = False
        base = f"/repositories/{self.workspace}/{self.repo}/pullrequests"

        try:
            for summary in self.client.paginate(
                base,
                params={
                    # `state` repeats — urlencode(doseq=True) expands the list.
                    "state": ["OPEN", "MERGED", "DECLINED", "SUPERSEDED"],
                    "sort": "-updated_on",
                },
            ):
                updated = _parse_iso(summary.get("updated_on"))
                if updated is not None and updated < cutoff:
                    # Sorted newest-first → everything after this is older.
                    break
                if len(out) >= self.max_prs:
                    truncated = True
                    break
                pr = self._enrich(summary)
                if pr is not None:
                    out.append(pr)
        except BitbucketError:
            # Partial data is better than none; surface what we have.
            truncated = True
        return out, truncated

    def _enrich(self, summary: dict[str, Any]) -> PullRequest | None:
        pr_id = summary.get("id")
        if pr_id is None:
            return None
        base = f"/repositories/{self.workspace}/{self.repo}/pullrequests/{pr_id}"
        activity = list(self.client.paginate(f"{base}/activity"))
        comments = list(self.client.paginate(f"{base}/comments"))
        diffstat = list(self.client.paginate(f"{base}/diffstat"))
        return _to_pr(summary, activity, comments, diffstat)


def _to_pr(
    summary: dict[str, Any],
    activity: list[dict[str, Any]],
    comments: list[dict[str, Any]],
    diffstat: list[dict[str, Any]],
) -> PullRequest:
    state = (summary.get("state") or "").upper()
    created_at = _parse_iso(summary.get("created_on")) or datetime.now(UTC)
    updated_at = _parse_iso(summary.get("updated_on"))

    merged = state == "MERGED"
    merged_at = updated_at if merged else None
    closed_at = updated_at if state in _TERMINAL_STATES else None

    reviews = tuple(
        r for r in (_activity_to_review(item) for item in activity) if r is not None
    )
    review_comments = tuple(
        c for c in (_to_comment(c) for c in comments) if c is not None
    )
    file_objs = tuple(_to_file(f) for f in diffstat)
    additions = sum(f.additions for f in file_objs)
    deletions = sum(f.deletions for f in file_objs)

    requested = tuple(
        _account_name(r)
        for r in (summary.get("reviewers") or [])
        if _account_name(r)
    )

    return PullRequest(
        number=int(summary["id"]),
        title=summary.get("title") or "",
        author_login=_account_name(summary.get("author") or {}),
        state=state.lower(),
        merged=merged,
        created_at=created_at,
        closed_at=closed_at,
        merged_at=merged_at,
        body=(summary.get("summary") or {}).get("raw") or "",
        labels=(),                   # Bitbucket Cloud PRs have no labels
        milestone=None,
        requested_reviewers=requested,
        files=file_objs,
        reviews=reviews,
        review_comments=review_comments,
        additions=additions,
        deletions=deletions,
    )


def _activity_to_review(item: dict[str, Any]) -> Review | None:
    """Map a Bitbucket activity entry to a Review, when it is one.

    Activity entries are tagged objects: `{approval: {...}}`,
    `{changes_requested: {...}}`, `{comment: {...}}`, `{update: {...}}`.
    Only the first two are reviews; comments come from `/comments` and
    updates are not reviews.
    """
    if "approval" in item:
        payload = item["approval"] or {}
        return Review(
            reviewer_login=_account_name(payload.get("user") or {}),
            state="APPROVED",
            submitted_at=_parse_iso(payload.get("date")) or datetime.now(UTC),
            body="",
        )
    if "changes_requested" in item:
        payload = item["changes_requested"] or {}
        return Review(
            reviewer_login=_account_name(payload.get("user") or {}),
            state="CHANGES_REQUESTED",
            submitted_at=_parse_iso(payload.get("date")) or datetime.now(UTC),
            body="",
        )
    return None


def _to_comment(payload: dict[str, Any]) -> ReviewComment | None:
    user = payload.get("user") or {}
    login = _account_name(user)
    if not login:
        return None
    inline = payload.get("inline") or {}
    return ReviewComment(
        reviewer_login=login,
        body=(payload.get("content") or {}).get("raw") or "",
        path=inline.get("path") or "",
        line=inline.get("to") if isinstance(inline.get("to"), int) else inline.get("from"),
        submitted_at=_parse_iso(payload.get("created_on")) or datetime.now(UTC),
    )


def _to_file(payload: dict[str, Any]) -> PullRequestFile:
    # diffstat status: added / modified / removed / renamed.
    new = payload.get("new") or {}
    old = payload.get("old") or {}
    path = new.get("path") or old.get("path") or ""
    additions = int(payload.get("lines_added") or 0)
    deletions = int(payload.get("lines_removed") or 0)
    return PullRequestFile(
        path=path,
        status=payload.get("status") or "",
        additions=additions,
        deletions=deletions,
        changes=additions + deletions,
    )


def _account_name(user: dict[str, Any]) -> str:
    """Pick the most stable human-readable identifier for a Bitbucket user.

    Bitbucket has no 'login'. `nickname` is the closest stable handle;
    fall back to `display_name`, then `account_id`/`uuid`. Lowercased to
    match how the GitHub collector normalises `login`.
    """
    for key in ("nickname", "display_name", "account_id", "uuid"):
        val = user.get(key)
        if val:
            return str(val).lower()
    return ""


def _parse_iso(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value.astimezone(UTC) if value.tzinfo else value.replace(tzinfo=UTC)
    if not isinstance(value, str):
        return None
    text = value.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    return dt.astimezone(UTC) if dt.tzinfo else dt.replace(tzinfo=UTC)


__all__ = ["BitbucketPRCollector"]
