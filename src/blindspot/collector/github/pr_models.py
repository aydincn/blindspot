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
