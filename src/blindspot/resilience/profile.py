"""Repo typology detection — gives the resilience score a context label.

A score of 35/100 on a single-maintainer OSS library means something
very different than 35/100 on a 200-contributor enterprise codebase.
The profile produced here lets the narrator soften (or sharpen)
band-level framing based on the structural shape of the repo, instead
of treating every "Critical" the same way.

Heuristics are intentionally conservative — we mark the profile as
``"unknown"`` whenever the signals are mixed enough to make a confident
call risky.
"""

from __future__ import annotations

from collections.abc import Iterable


# Public profile labels — these match the keys the narrator uses for
# its profile-aware structural note.
PROFILE_DOC_ONLY = "doc-only"
PROFILE_SINGLE_MAINTAINER = "single-maintainer"
PROFILE_FOUNDER_LED = "founder-led"
PROFILE_TEAM = "team"
PROFILE_MULTI_ORG = "multi-org"
PROFILE_UNKNOWN = "unknown"


def _is_code_file(path: str) -> bool:
    """Quick "looks like code" filter — keeps this module standalone from
    the more involved diff classifier."""
    lower = path.lower()
    for ext in (
        ".py", ".js", ".jsx", ".ts", ".tsx",
        ".go", ".rs", ".java", ".kt", ".scala",
        ".rb", ".php", ".cs", ".swift", ".m", ".c", ".cc", ".cpp", ".h",
        ".hpp", ".ex", ".exs", ".erl", ".clj", ".cljs",
    ):
        if lower.endswith(ext):
            return True
    return False


def detect_profile(
    *,
    commit_count: int,
    author_count: int,
    files: Iterable[str],
    services_count: int,
    top_author_coverage: float | None,
) -> str:
    """Return one of the PROFILE_* labels.

    ``top_author_coverage`` is the dominant author's share of total
    aggregated coverage across files (0.0 to 1.0). ``None`` means the
    signal isn't available.
    """
    code_file_count = sum(1 for f in files if _is_code_file(f))

    # Doc-only / list-style repo
    if code_file_count < 10:
        return PROFILE_DOC_ONLY

    # Too few authors → solo/duo maintainer
    if author_count <= 2:
        return PROFILE_SINGLE_MAINTAINER

    # Founder-led: one author owns most of the surface, plus a small team
    # The 0.55 threshold catches projects where one person is decisively
    # dominant without requiring "essentially alone".
    if (
        top_author_coverage is not None
        and top_author_coverage >= 0.55
        and author_count <= 30
    ):
        return PROFILE_FOUNDER_LED

    # Multi-org / enterprise: many authors, many services, no single
    # dominant individual.
    if (
        author_count >= 50
        and services_count >= 8
        and (top_author_coverage is None or top_author_coverage < 0.30)
    ):
        return PROFILE_MULTI_ORG

    # Mid-range team — multiple maintainers, no single dominator, but
    # not large enough to be "enterprise multi-org".
    if author_count >= 4:
        return PROFILE_TEAM

    return PROFILE_UNKNOWN


__all__ = [
    "PROFILE_DOC_ONLY",
    "PROFILE_SINGLE_MAINTAINER",
    "PROFILE_FOUNDER_LED",
    "PROFILE_TEAM",
    "PROFILE_MULTI_ORG",
    "PROFILE_UNKNOWN",
    "detect_profile",
]
