"""Backward-compatible re-export of the shared review models.

The PR/review models moved to `blindspot.collector.review_models` in
0.0.2 so the Bitbucket provider can produce the same shapes. Existing
imports from `blindspot.collector.github.pr_models` keep working via
this shim.
"""

from blindspot.collector.review_models import (
    PullRequest,
    PullRequestFile,
    Review,
    ReviewComment,
)

__all__ = ["PullRequest", "PullRequestFile", "Review", "ReviewComment"]
