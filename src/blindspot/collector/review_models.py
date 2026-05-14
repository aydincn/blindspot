"""Provider-agnostic pull-request models.

Produced by every review-data provider (GitHub today, Bitbucket Cloud as
of 0.0.2) and consumed by the review-graph, diff-analysis, and AI-signal
layers. Keeping them provider-neutral is what lets `--with-reviews` work
the same way regardless of where the repo is hosted.

`author_login` / `reviewer_login` hold whatever stable identifier the
provider exposes — GitHub username, Bitbucket nickname — lowercased.
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class PullRequestFile:
    path: str
    status: str
    additions: int
    deletions: int
    changes: int


@dataclass(frozen=True, slots=True)
class Review:
    reviewer_login: str
    state: str
    submitted_at: datetime
    body: str


@dataclass(frozen=True, slots=True)
class ReviewComment:
    reviewer_login: str
    body: str
    path: str
    line: int | None
    submitted_at: datetime


@dataclass(frozen=True, slots=True)
class PullRequest:
    number: int
    title: str
    author_login: str
    state: str
    merged: bool
    created_at: datetime
    closed_at: datetime | None
    merged_at: datetime | None
    body: str
    labels: tuple[str, ...]
    milestone: str | None
    requested_reviewers: tuple[str, ...]
    files: tuple[PullRequestFile, ...]
    reviews: tuple[Review, ...]
    review_comments: tuple[ReviewComment, ...]
    additions: int
    deletions: int


__all__ = ["PullRequest", "PullRequestFile", "Review", "ReviewComment"]
