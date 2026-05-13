from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from blindspot.collector.github.client import GitHubClient, RateLimitExhausted
from blindspot.collector.github.pr_models import (
    PullRequest,
    PullRequestFile,
    Review,
    ReviewComment,
)


@dataclass
class PRCollector:
    client: GitHubClient
    owner: str
    repo: str
    since_days: int = 180
    state: str = "all"
    max_prs: int = 200

    def collect(self) -> tuple[list[PullRequest], bool]:
        """Return (prs_collected, was_truncated_by_rate_limit)."""
        cutoff = datetime.now(UTC) - timedelta(days=self.since_days)
        out: list[PullRequest] = []
        truncated = False
        try:
            for summary in self.client.paginate(
                f"/repos/{self.owner}/{self.repo}/pulls",
                params={"state": self.state, "sort": "updated", "direction": "desc"},
            ):
                if len(out) >= self.max_prs:
                    break
                updated = _parse_iso(summary.get("updated_at"))
                if updated is None or updated < cutoff:
                    break
                pr = self._enrich(summary)
                if pr is not None:
                    out.append(pr)
        except RateLimitExhausted:
            truncated = True
        return out, truncated

    def _enrich(self, summary: dict[str, Any]) -> PullRequest | None:
        number = summary["number"]
        base = f"/repos/{self.owner}/{self.repo}/pulls/{number}"
        try:
            reviews_raw = list(self.client.paginate(f"{base}/reviews"))
            comments_raw = list(self.client.paginate(f"{base}/comments"))
            files_raw = list(self.client.paginate(f"{base}/files"))
        except RateLimitExhausted:
            raise
        return _to_pr(summary, reviews_raw, comments_raw, files_raw)


def _to_pr(
    summary: dict[str, Any],
    reviews: Iterable[dict[str, Any]],
    comments: Iterable[dict[str, Any]],
    files: Iterable[dict[str, Any]],
) -> PullRequest:
    requested = tuple(
        (r.get("login") or "").lower()
        for r in (summary.get("requested_reviewers") or [])
        if r.get("login")
    )
    labels = tuple(
        (lbl.get("name") or "")
        for lbl in (summary.get("labels") or [])
        if lbl.get("name")
    )
    milestone = (summary.get("milestone") or {}).get("title")
    review_objs = tuple(_to_review(r) for r in reviews if r.get("user"))
    comment_objs = tuple(_to_comment(c) for c in comments if c.get("user"))
    file_objs = tuple(_to_file(f) for f in files)

    additions = sum(f.additions for f in file_objs)
    deletions = sum(f.deletions for f in file_objs)

    return PullRequest(
        number=int(summary["number"]),
        title=summary.get("title") or "",
        author_login=((summary.get("user") or {}).get("login") or "").lower(),
        state=summary.get("state") or "",
        merged=bool(summary.get("merged_at")),
        created_at=_parse_iso(summary.get("created_at")) or datetime.now(UTC),
        closed_at=_parse_iso(summary.get("closed_at")),
        merged_at=_parse_iso(summary.get("merged_at")),
        body=summary.get("body") or "",
        labels=labels,
        milestone=milestone,
        requested_reviewers=requested,
        files=file_objs,
        reviews=review_objs,
        review_comments=comment_objs,
        additions=additions,
        deletions=deletions,
    )


def _to_review(payload: dict[str, Any]) -> Review:
    return Review(
        reviewer_login=((payload.get("user") or {}).get("login") or "").lower(),
        state=(payload.get("state") or "").upper(),
        submitted_at=_parse_iso(payload.get("submitted_at")) or datetime.now(UTC),
        body=payload.get("body") or "",
    )


def _to_comment(payload: dict[str, Any]) -> ReviewComment:
    return ReviewComment(
        reviewer_login=((payload.get("user") or {}).get("login") or "").lower(),
        body=payload.get("body") or "",
        path=payload.get("path") or "",
        line=payload.get("line"),
        submitted_at=_parse_iso(payload.get("created_at")) or datetime.now(UTC),
    )


def _to_file(payload: dict[str, Any]) -> PullRequestFile:
    return PullRequestFile(
        path=payload.get("filename") or "",
        status=payload.get("status") or "",
        additions=int(payload.get("additions") or 0),
        deletions=int(payload.get("deletions") or 0),
        changes=int(payload.get("changes") or 0),
    )


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


__all__ = ["PRCollector"]
