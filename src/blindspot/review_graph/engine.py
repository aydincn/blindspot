from collections.abc import Iterable
from dataclasses import dataclass, field

from blindspot.collector.github.pr_models import PullRequest


# Review state weights — matches the originally agreed formula:
#   review_score(person, file) = review_count * 0.5 + comment_count * 1.0
REVIEW_WEIGHT = 0.5
COMMENT_WEIGHT = 1.0


@dataclass(frozen=True, slots=True)
class FileReviewStats:
    file: str
    unique_reviewers: int
    total_reviews: int
    total_comments: int
    rubber_stamp_ratio: float
    diversity_hhi: float
    median_approval_latency_seconds: float | None = None
    approval_sample_size: int = 0


@dataclass(frozen=True, slots=True)
class ReviewGraph:
    by_reviewer_file: dict[tuple[str, str], float] = field(default_factory=dict)
    file_stats: dict[str, FileReviewStats] = field(default_factory=dict)

    def score_for(self, reviewer_login: str, file: str) -> float:
        return self.by_reviewer_file.get((reviewer_login.lower(), file), 0.0)

    def stats_for(self, file: str) -> FileReviewStats | None:
        return self.file_stats.get(file)


@dataclass
class ReviewGraphBuilder:
    def build(self, prs: Iterable[PullRequest]) -> ReviewGraph:
        review_counts: dict[tuple[str, str], int] = {}
        comment_counts: dict[tuple[str, str], int] = {}
        approvals_no_comment: dict[str, int] = {}
        total_approvals: dict[str, int] = {}
        reviewers_per_file: dict[str, set[str]] = {}
        approval_latencies_per_file: dict[str, list[float]] = {}

        for pr in prs:
            pr_files = [f.path for f in pr.files]
            commenters_on_file: dict[str, set[str]] = {}
            for c in pr.review_comments:
                if not c.path:
                    continue
                key = (c.reviewer_login, c.path)
                comment_counts[key] = comment_counts.get(key, 0) + 1
                commenters_on_file.setdefault(c.path, set()).add(c.reviewer_login)

            first_approval_seconds = _first_approval_latency_seconds(pr)
            if first_approval_seconds is not None:
                for path in pr_files:
                    approval_latencies_per_file.setdefault(path, []).append(
                        first_approval_seconds
                    )

            for r in pr.reviews:
                if not r.reviewer_login:
                    continue
                for path in pr_files:
                    key = (r.reviewer_login, path)
                    review_counts[key] = review_counts.get(key, 0) + 1
                    reviewers_per_file.setdefault(path, set()).add(r.reviewer_login)

                    if r.state == "APPROVED":
                        total_approvals[path] = total_approvals.get(path, 0) + 1
                        if r.reviewer_login not in commenters_on_file.get(path, set()):
                            approvals_no_comment[path] = approvals_no_comment.get(path, 0) + 1

            for path in pr_files:
                for commenter in commenters_on_file.get(path, set()):
                    reviewers_per_file.setdefault(path, set()).add(commenter)

        by_reviewer_file: dict[tuple[str, str], float] = {}
        keys = set(review_counts) | set(comment_counts)
        for key in keys:
            score = (
                review_counts.get(key, 0) * REVIEW_WEIGHT
                + comment_counts.get(key, 0) * COMMENT_WEIGHT
            )
            by_reviewer_file[key] = score

        file_stats: dict[str, FileReviewStats] = {}
        for path, reviewers in reviewers_per_file.items():
            total_reviews_on_file = sum(
                review_counts.get((rv, path), 0) for rv in reviewers
            )
            total_comments_on_file = sum(
                comment_counts.get((rv, path), 0) for rv in reviewers
            )
            approvals = total_approvals.get(path, 0)
            stamp_ratio = (
                approvals_no_comment.get(path, 0) / approvals if approvals > 0 else 0.0
            )
            latencies = approval_latencies_per_file.get(path, [])
            median_latency = _median(latencies) if latencies else None
            file_stats[path] = FileReviewStats(
                file=path,
                unique_reviewers=len(reviewers),
                total_reviews=total_reviews_on_file,
                total_comments=total_comments_on_file,
                rubber_stamp_ratio=stamp_ratio,
                diversity_hhi=_diversity(reviewers, review_counts, path),
                median_approval_latency_seconds=median_latency,
                approval_sample_size=len(latencies),
            )

        return ReviewGraph(by_reviewer_file=by_reviewer_file, file_stats=file_stats)


def _first_approval_latency_seconds(pr: PullRequest) -> float | None:
    approvals = [r for r in pr.reviews if r.state == "APPROVED"]
    if not approvals:
        return None
    first = min(approvals, key=lambda r: r.submitted_at)
    delta = (first.submitted_at - pr.created_at).total_seconds()
    return max(0.0, delta)


def _median(values: list[float]) -> float:
    sorted_v = sorted(values)
    n = len(sorted_v)
    mid = n // 2
    if n % 2 == 0:
        return (sorted_v[mid - 1] + sorted_v[mid]) / 2
    return sorted_v[mid]


def _diversity(reviewers: set[str], review_counts: dict[tuple[str, str], int], path: str) -> float:
    counts = [review_counts.get((rv, path), 0) for rv in reviewers]
    total = sum(counts)
    if total == 0:
        return 0.0
    shares = [c / total for c in counts]
    hhi = sum(s * s for s in shares)
    # Normalize to "diversity" = 1 - HHI (1.0 = perfectly distributed, 0 = single reviewer)
    return max(0.0, 1.0 - hhi)


__all__ = [
    "COMMENT_WEIGHT",
    "FileReviewStats",
    "REVIEW_WEIGHT",
    "ReviewGraph",
    "ReviewGraphBuilder",
]
