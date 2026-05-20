"""Key signals — the six core "pill metrics".

The product's value proposition is six concrete questions, each with a
single-number answer a CTO/VP can read in one glance:

  1. Ownership concentration  — how many services rest on one person?
  2. Single-engineer dependency — if the top contributor leaves, how
     many files orphan?
  3. Knowledge decay          — how many files has their owner drifted
     away from?
  4. Review depth             — how many files get approved without a
     substantive comment?
  5. Correction load          — how many files get a stream of bugfix
     commits after each feature lands?
  6. AI readiness             — how many services lack the operational
     docs a new contributor (human or AI) would load first?

Each KeySignal carries a headline (the number, in a phrase), an
optional A–F grade, and a one-line plain-English meaning. No formulas,
no jargon — that's the whole point.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from blindspot.report.context import ReportContext


@dataclass(frozen=True, slots=True)
class KeySignal:
    name: str
    headline: str          # "4 services rest on a single owner"
    grade: str | None      # "A".."F" or None
    meaning: str           # one-line plain English
    healthy: bool          # True ⇒ nothing to worry about here


def _ownership(ctx: "ReportContext") -> KeySignal:
    single = sum(
        1 for s in ctx.services
        if s.bus_factor == 1
        and not (s.service.startswith("(") and s.service.endswith(")"))
        and s.file_count >= 3
    )
    grade = ctx.resilience.ownership_grade if ctx.resilience else None
    if single == 0:
        return KeySignal(
            name="Ownership concentration",
            headline="No service rests on a single owner",
            grade=grade,
            meaning="Every service has at least two people who know it.",
            healthy=True,
        )
    return KeySignal(
        name="Ownership concentration",
        headline=(
            f"{single} service{'' if single == 1 else 's'} "
            f"rest{'s' if single == 1 else ''} on a single owner"
        ),
        grade=grade,
        meaning=(
            "If that person is unavailable, no one else can confidently "
            "change these areas."
        ),
        healthy=False,
    )


def _departure(ctx: "ReportContext") -> KeySignal:
    worst = max(
        (s.orphaned_files for s in ctx.departure_scenarios), default=0
    )
    if worst == 0:
        return KeySignal(
            name="Single-engineer dependency",
            headline="No contributor's departure orphans critical files",
            grade=None,
            meaning="Knowledge is spread widely enough to survive a departure.",
            healthy=True,
        )
    return KeySignal(
        name="Single-engineer dependency",
        headline=(
            f"{worst} file{'' if worst == 1 else 's'} "
            f"orphan{'s' if worst == 1 else ''} if the top contributor leaves"
        ),
        grade=None,
        meaning=(
            "These files would have no confident owner the day that "
            "person walks out."
        ),
        healthy=False,
    )


def _decay(ctx: "ReportContext") -> KeySignal:
    critical = sum(1 for d in ctx.decay_top if d.decay_score >= 0.75)
    grade = ctx.resilience.decay_grade if ctx.resilience else None
    if critical == 0:
        return KeySignal(
            name="Knowledge decay",
            headline="No file is critically decayed",
            grade=grade,
            meaning="Owners are still close to the code they own.",
            healthy=True,
        )
    return KeySignal(
        name="Knowledge decay",
        headline=(
            f"{critical} file{'' if critical == 1 else 's'} "
            f"{'is' if critical == 1 else 'are'} critically decayed"
        ),
        grade=grade,
        meaning=(
            "The owner stopped touching these while others kept changing "
            "them — the knowledge is going stale."
        ),
        healthy=False,
    )


def _review(ctx: "ReportContext") -> KeySignal:
    rubber = sum(
        1 for s in ctx.top_rubber_stamps if s.rubber_stamp_ratio >= 0.70
    )
    grade = ctx.resilience.review_grade if ctx.resilience else None
    if grade is None and not rubber:
        return KeySignal(
            name="Review depth",
            headline="No review data (local git only)",
            grade=None,
            meaning="Connect a GitHub/Bitbucket remote to measure review depth.",
            healthy=True,
        )
    if rubber == 0:
        return KeySignal(
            name="Review depth",
            headline="Reviews carry substantive comments",
            grade=grade,
            meaning="Approvals reflect real scrutiny, not rubber-stamping.",
            healthy=True,
        )
    return KeySignal(
        name="Review depth",
        headline=(
            f"{rubber} file{'' if rubber == 1 else 's'} "
            f"{'is' if rubber == 1 else 'are'} approved without scrutiny"
        ),
        grade=grade,
        meaning=(
            "Most approvals on these files land with no substantive "
            "comment — quality rests on the author alone."
        ),
        healthy=False,
    )


def _correction(ctx: "ReportContext") -> KeySignal:
    """The pill follows the repo-wide proportion (the letter grade), not
    an absolute file count. 36 hot files in a 10k-file repo is statistically
    normal — not a fragility signal. A risk pill must never carry an A:
    if the grade says correction load is fine, the pill stays green."""
    heavy = sum(
        1 for f in ctx.correction_load_files if f.correction_ratio >= 0.35
    )
    grade = (
        ctx.resilience.correction_load_grade if ctx.resilience else None
    )
    if heavy == 0:
        return KeySignal(
            name="Correction load",
            headline="Features land without a bugfix tail",
            grade=grade,
            meaning="Code ships and stays shipped — low rework pressure.",
            healthy=True,
        )
    if grade in ("A", "B"):
        return KeySignal(
            name="Correction load",
            headline="Correction load is low across the codebase",
            grade=grade,
            meaning=(
                f"A handful of files ({heavy}) run a high fix/revert ratio, "
                "but repo-wide rework pressure stays low."
            ),
            healthy=True,
        )
    return KeySignal(
        name="Correction load",
        headline=(
            f"{heavy} file{'' if heavy == 1 else 's'} "
            f"carr{'ies' if heavy == 1 else 'y'} a heavy bugfix tail"
        ),
        grade=grade,
        meaning=(
            "After each feature these files get a stream of fix/revert "
            "commits — see the Correction load table (--detailed) for the "
            "exact surfaces; the top ones also appear in the actions list."
        ),
        healthy=False,
    )


def _ai_readiness(ctx: "ReportContext") -> KeySignal:
    """Repo-level assessment, not per-service.

    Counting every sub-module as a service that "lacks" AI context
    produced alarmist numbers ("17 services lack…") — but expecting a
    separate CLAUDE.md per sub-module is unrealistic. What actually
    matters is the repo root: is there a CLAUDE.md, specs/, ADRs that a
    new contributor (human or AI) loads first? So we read the
    repo-level coverage row."""
    grade = ctx.resilience.ai_readiness_grade if ctx.resilience else None
    if ctx.ai_readiness is None:
        return KeySignal(
            name="AI-readable context",
            headline="Not assessed",
            grade=None,
            meaning="No file structure to measure AI-readable context.",
            healthy=True,
        )
    repo_cov = ctx.ai_readiness.repo
    n = repo_cov.coverage_count
    if n >= 2:
        return KeySignal(
            name="AI-readable context",
            headline=f"Repo carries AI-readable operational context ({n}/5)",
            grade=grade,
            meaning=(
                "A new contributor or AI agent has docs to load at the "
                "repo root before touching code."
            ),
            healthy=True,
        )
    missing = []
    if not repo_cov.agent_rules:
        missing.append("agent rules (CLAUDE.md)")
    if not repo_cov.specs:
        missing.append("specs")
    if not repo_cov.architecture:
        missing.append("architecture notes / ADRs")
    if not repo_cov.prompts:
        missing.append("prompts")
    if not repo_cov.skills:
        missing.append("skills")
    return KeySignal(
        name="AI-readable context",
        headline=f"Repo lacks AI-readable operational context ({n}/5)",
        grade=grade,
        meaning=(
            f"No {', '.join(missing[:3])} at the repo root — a new human "
            "or AI agent must reverse-engineer the codebase."
        ),
        healthy=False,
    )


def build_key_signals(ctx: "ReportContext") -> tuple[KeySignal, ...]:
    """Build the six core pill metrics, in fixed display order.

    A pill's grade must agree with its colour. The grade comes from the
    composite resilience sub-score, which measures a related but not
    identical thing — so two mismatches are possible and both are
    dropped:

      * a green "healthy" pill carrying an "F" — drop the grade;
      * a red "risk" pill carrying a reassuring "A"/"B" — drop the
        grade, since a good letter next to a red pill reads as a
        contradiction.

    The ✓/✗ and the headline already carry the message; a contradictory
    grade only erodes trust.
    """
    signals = (
        _ownership(ctx),
        _departure(ctx),
        _decay(ctx),
        _review(ctx),
        _correction(ctx),
        _ai_readiness(ctx),
    )

    def _present(s: KeySignal) -> KeySignal:
        if s.healthy or s.grade in ("A", "B"):
            return replace(s, grade=None)
        return s

    return tuple(_present(s) for s in signals)


__all__ = ["KeySignal", "build_key_signals"]
