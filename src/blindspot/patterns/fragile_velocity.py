"""Fragile Velocity pattern detector.

The signature pattern of organizational survivability.

Definition (composite, from saha test cohort):

    high ownership concentration   +
    low reviewer diversity         +
    high correction load           +
    weak AI operational memory     =  Fragile Velocity

The repo *looks* healthy on the surface — features ship, commits flow.
But the operational sermaye is being spent: one person carries the
service, reviews are theatre, fixes pile up after each new feature,
and there is no AI-readable context for a new contributor to load.

This detector returns a single PatternHit (or empty) — it's a
repo-level signal. The per-target detail lives in the underlying
recommendations.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from blindspot.patterns.models import PatternHit, PatternSeverity

if TYPE_CHECKING:
    from blindspot.report.context import ReportContext


# Thresholds — picked to fire on the saha test cohort's clearest
# fragile-velocity examples (cline, n8n) and stay silent on healthy
# multi-org repos.
_CONCENTRATION_FILE_THRESHOLD = 5      # ≥ N critical single-owner files
_LOW_DIVERSITY_FILE_THRESHOLD = 2      # ≥ N rubber-stamp files
_CORRECTION_FILE_THRESHOLD = 3         # ≥ N high-correction-load files
_AI_GAP_SERVICES_THRESHOLD = 2         # ≥ N services without operational context
_MIN_SIGNALS_TO_FIRE = 3               # need at least 3 of 4 axes to call it


def _count_concentration(ctx: "ReportContext") -> int:
    return sum(
        1 for f in ctx.critical_files
        if f.top_owners and f.top_owners[0][1] >= 0.80
    )


def _count_low_diversity(ctx: "ReportContext") -> int:
    return sum(
        1 for s in ctx.top_rubber_stamps if s.rubber_stamp_ratio >= 0.70
    )


def _count_correction(ctx: "ReportContext") -> int:
    return sum(
        1 for f in ctx.correction_load_files if f.correction_ratio >= 0.35
    )


def _count_ai_gap(ctx: "ReportContext") -> int:
    if ctx.ai_readiness is None:
        return 0
    return sum(
        1 for c in ctx.ai_readiness.services if c.coverage_count < 2
    )


def detect_fragile_velocity(ctx: "ReportContext") -> PatternHit | None:
    axes: dict[str, int] = {
        "concentration": _count_concentration(ctx),
        "low_diversity": _count_low_diversity(ctx),
        "correction": _count_correction(ctx),
        "ai_gap": _count_ai_gap(ctx),
    }
    axis_thresholds = {
        "concentration": _CONCENTRATION_FILE_THRESHOLD,
        "low_diversity": _LOW_DIVERSITY_FILE_THRESHOLD,
        "correction": _CORRECTION_FILE_THRESHOLD,
        "ai_gap": _AI_GAP_SERVICES_THRESHOLD,
    }
    triggered = [
        k for k, v in axes.items() if v >= axis_thresholds[k]
    ]
    if len(triggered) < _MIN_SIGNALS_TO_FIRE:
        return None

    # Severity: 3 axes → MEDIUM, 4 axes → HIGH.
    severity = PatternSeverity.HIGH if len(triggered) == 4 else PatternSeverity.MEDIUM

    # Score: 0.0–1.0 share of axes fired.
    score = len(triggered) / 4.0

    parts: list[str] = []
    if "concentration" in triggered:
        parts.append(
            f"{axes['concentration']} files held by a single owner at ≥ 80% coverage"
        )
    if "low_diversity" in triggered:
        parts.append(
            f"{axes['low_diversity']} files reviewed with rubber-stamp patterns"
        )
    if "correction" in triggered:
        parts.append(
            f"{axes['correction']} files carry ≥ 35% fix/revert correction load"
        )
    if "ai_gap" in triggered:
        parts.append(
            f"{axes['ai_gap']} services without AI-readable operational context"
        )

    description = (
        "The repo looks healthy on the surface — commits ship, features land. "
        "But the operational capital is being spent: "
        + "; ".join(parts) + ". "
        "Address the underlying signals together; fixing one without the "
        "others leaves the pattern intact."
    )

    return PatternHit(
        key="fragile_velocity",
        name="Fragile Velocity",
        severity=severity,
        description=description,
        targets=(),
        score=score,
        evidence={k: str(v) for k, v in axes.items()},
    )


__all__ = ["detect_fragile_velocity"]
