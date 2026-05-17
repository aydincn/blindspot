"""Confidence scoring for recommendations.

A recommendation against 30 commits in 90 days is structurally weaker
than the same recommendation against 5,000 commits in 30 days — yet
the priority field doesn't carry that distinction. Confidence does.

Inputs are coarse on purpose: signal density (commits + window),
repo profile (doc-only repos can never reach HIGH), and rule-specific
sample size (e.g. review-hygiene actions get downgraded when there
are very few reviews to draw from).
"""

from __future__ import annotations

from blindspot.actions.models import ActionCategory, Confidence, RecommendedAction


_LOW_COMMITS = 50          # below this, the whole report is low-volume
_HIGH_COMMITS = 300        # above this, structural claims are sound
_LOW_DAYS = 7              # very short window — any score is shaky
_REVIEW_MIN_SAMPLES = 5    # review-hygiene needs at least N reviews


def scan_confidence(
    *,
    commit_count: int,
    window_days: int,
    repo_profile: str | None,
) -> Confidence:
    """Repo-level baseline confidence — the ceiling for any action in
    this scan. Doc-only / low-volume / very-short-window repos can
    never produce HIGH-confidence advice."""
    if repo_profile == "doc-only":
        return Confidence.LOW
    if window_days < _LOW_DAYS or commit_count < _LOW_COMMITS:
        return Confidence.LOW
    if commit_count >= _HIGH_COMMITS:
        return Confidence.HIGH
    return Confidence.MEDIUM


def _downgrade(c: Confidence) -> Confidence:
    if c == Confidence.HIGH:
        return Confidence.MEDIUM
    if c == Confidence.MEDIUM:
        return Confidence.LOW
    return Confidence.LOW


def confidence_for(
    action: RecommendedAction,
    *,
    scan_ceiling: Confidence,
    review_sample_size: int = 0,
) -> Confidence:
    """Per-action confidence, capped by the scan ceiling.

    Review-hygiene actions are additionally downgraded when the
    sample of reviews is small (rubber-stamp / fast-approval claims
    based on a handful of approvals are noisy).
    """
    out = scan_ceiling
    if (
        action.category == ActionCategory.REVIEW_HYGIENE
        and review_sample_size > 0
        and review_sample_size < _REVIEW_MIN_SAMPLES
    ):
        out = _downgrade(out)
    return out


__all__ = ["confidence_for", "scan_confidence"]
