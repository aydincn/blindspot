import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from blindspot.ai_signal.models import QualitySignal
from blindspot.collector.github.pr_models import PullRequest
from blindspot.collector.models import Commit

BUG_KEYWORDS = (
    "fix", "bug", "hotfix", "patch", "broken", "repair", "issue", "crash",
    "error", "regression",
)
REVERT_KEYWORDS = ("revert",)

TEST_PATH_HINTS = ("test", "tests", "__tests__", "spec", "specs", "e2e")


@dataclass
class QualitySignalEngine:
    measurement_days: int = 90
    min_recent_commits: int = 3
    as_of: datetime | None = None
    # weights: churn, bug, revert, review_rejection, test_cov, pr_description
    weights: tuple[float, float, float, float, float, float] = (
        0.20, 0.20, 0.15, 0.15, 0.10, 0.20,
    )
    min_pr_body_chars: int = 50
    _as_of: datetime = field(init=False)

    def __post_init__(self) -> None:
        self._as_of = (self.as_of or datetime.now(UTC)).astimezone(UTC)

    def assess(
        self,
        commits: Iterable[Commit],
        prs: Iterable[PullRequest] | None = None,
    ) -> dict[str, QualitySignal]:
        cutoff = self._as_of - timedelta(days=self.measurement_days)
        by_author: dict[str, list[Commit]] = {}
        for c in commits:
            if c.authored_at >= cutoff:
                by_author.setdefault(c.author_email, []).append(c)

        prs_by_login: dict[str, list[PullRequest]] = {}
        if prs is not None:
            for pr in prs:
                if pr.author_login:
                    prs_by_login.setdefault(pr.author_login.lower(), []).append(pr)

        results: dict[str, QualitySignal] = {}
        for email, author_commits in by_author.items():
            if len(author_commits) < self.min_recent_commits:
                continue
            churn = self._churn_score(author_commits)
            bug = self._bug_keyword_score(author_commits)
            revert = self._revert_score(author_commits)
            test_cov = self._test_coverage_score(author_commits)

            author_prs = self._prs_for_email(email, prs_by_login)
            review_rejection = self._review_rejection_score(author_prs)
            pr_desc = self._pr_description_score(author_prs)

            w = self.weights
            if author_prs:
                risk = (
                    churn * w[0]
                    + bug * w[1]
                    + revert * w[2]
                    + review_rejection * w[3]
                    + test_cov * w[4]
                    + pr_desc * w[5]
                )
            else:
                # No PR data for this author — renormalize over git-only signals so
                # missing PR weights don't artificially deflate the score.
                git_weight_sum = w[0] + w[1] + w[2] + w[4]
                if git_weight_sum > 0:
                    risk = (
                        churn * w[0]
                        + bug * w[1]
                        + revert * w[2]
                        + test_cov * w[4]
                    ) / git_weight_sum
                else:
                    risk = 0.0
            results[email] = QualitySignal(
                author_email=email,
                risk_score=risk,
                churn_score=churn,
                bug_keyword_score=bug,
                revert_score=revert,
                review_rejection_score=review_rejection,
                test_coverage_score=test_cov,
                pr_description_score=pr_desc,
                recent_commits=len(author_commits),
            )
        return results

    def _prs_for_email(
        self, email: str, prs_by_login: dict[str, list[PullRequest]]
    ) -> list[PullRequest]:
        if email.endswith("@github"):
            login = email[: -len("@github")]
            return prs_by_login.get(login, [])
        return []

    def _review_rejection_score(self, prs: list[PullRequest]) -> float:
        """Share of authored PRs that received CHANGES_REQUESTED reviews."""
        if not prs:
            return 0.0
        rejected = 0
        for pr in prs:
            if any(r.state == "CHANGES_REQUESTED" for r in pr.reviews):
                rejected += 1
        ratio = rejected / len(prs)
        return min(ratio / 0.4, 1.0)

    def _pr_description_score(self, prs: list[PullRequest]) -> float:
        """Higher score = lower PR description quality (risk signal)."""
        if not prs:
            return 0.0
        misses = 0
        for pr in prs:
            short = len((pr.body or "").strip()) < self.min_pr_body_chars
            no_link = not _ISSUE_REF.search(pr.body or "")
            no_label = not pr.labels
            indicators = sum([short, no_link, no_label])
            if indicators >= 2:
                misses += 1
        ratio = misses / len(prs)
        return min(ratio / 0.5, 1.0)

    def _churn_score(self, commits: list[Commit]) -> float:
        """Files this author re-touched within the window — rough proxy for rework."""
        touches: dict[str, int] = {}
        for c in commits:
            for f in c.files:
                touches[f.path] = touches.get(f.path, 0) + 1
        if not touches:
            return 0.0
        reworked = sum(1 for n in touches.values() if n >= 2)
        ratio = reworked / len(touches)
        return min(ratio / 0.4, 1.0)

    def _bug_keyword_score(self, commits: list[Commit]) -> float:
        if not commits:
            return 0.0
        hits = 0
        for c in commits:
            msg = c.message.lower()
            if any(kw in msg for kw in BUG_KEYWORDS):
                hits += 1
        ratio = hits / len(commits)
        return min(ratio / 0.4, 1.0)

    def _revert_score(self, commits: list[Commit]) -> float:
        if not commits:
            return 0.0
        reverts = sum(1 for c in commits if any(kw in c.message.lower() for kw in REVERT_KEYWORDS))
        return min(reverts / 3.0, 1.0)

    def _test_coverage_score(self, commits: list[Commit]) -> float:
        code_lines = 0
        test_lines = 0
        for c in commits:
            for f in c.files:
                if _looks_like_test(f.path):
                    test_lines += f.additions
                else:
                    code_lines += f.additions
        if code_lines == 0:
            return 0.0
        if test_lines >= code_lines * 0.5:
            return 0.0
        if test_lines >= code_lines * 0.2:
            return 0.4
        if test_lines == 0 and code_lines >= 100:
            return 1.0
        return 0.8


def _looks_like_test(path: str) -> bool:
    parts = [p.lower() for p in path.split("/")]
    if any(p in TEST_PATH_HINTS for p in parts):
        return True
    basename = parts[-1] if parts else ""
    if basename.startswith("test_") or basename.endswith("_test.py"):
        return True
    if ".test." in basename or ".spec." in basename:
        return True
    return False


_ISSUE_REF = re.compile(r"(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s+#\d+", re.IGNORECASE)


__all__ = ["BUG_KEYWORDS", "QualitySignalEngine", "REVERT_KEYWORDS"]
