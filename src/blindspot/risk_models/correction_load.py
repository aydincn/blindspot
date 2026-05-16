"""Correction Load — per-author and per-file ratio of follow-up
fix/revert commits to total commits.

A high correction load is observable evidence of *stability debt*: code is
being shipped fast but follow-up corrections are paying for it. This is the
modern, observable replacement for the older speculative "AI velocity"
signal — it looks at what actually happened in the history, not at how
the author might be writing code.

The model never uses commit message text *content* for surveillance
purposes (we never report what the fix was about). It only counts
classified intents.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass

from blindspot.collector.models import Commit
from blindspot.diff_analysis.commit_intent import CommitIntent, classify_commit


def _risk_level(ratio: float, high: float, critical: float) -> str:
    if ratio >= critical:
        return "critical"
    if ratio >= high:
        return "high"
    if ratio >= high / 2:
        return "moderate"
    return "healthy"


@dataclass(frozen=True, slots=True)
class AuthorCorrectionLoad:
    author_email: str
    total_commits: int
    fix_commits: int
    revert_commits: int
    feature_commits: int
    correction_ratio: float
    risk_level: str


@dataclass(frozen=True, slots=True)
class FileCorrectionLoad:
    file: str
    total_commits: int
    fix_commits: int
    revert_commits: int
    correction_ratio: float
    risk_level: str


@dataclass(frozen=True, slots=True)
class CorrectionLoadReport:
    authors: tuple[AuthorCorrectionLoad, ...]
    files: tuple[FileCorrectionLoad, ...]


@dataclass
class CorrectionLoadEngine:
    """Compute correction load per author and per file.

    Defaults:
      - ``min_commits_for_signal``: ignore authors / files with too few
        commits — the ratio is noisy below this floor.
      - ``high_threshold`` / ``critical_threshold``: ratio cutoffs.
    """

    min_commits_for_signal: int = 5
    high_threshold: float = 0.35
    critical_threshold: float = 0.50

    def compute(self, commits: Iterable[Commit]) -> CorrectionLoadReport:
        commits = tuple(c for c in commits if not c.is_merge)
        if not commits:
            return CorrectionLoadReport(authors=(), files=())

        author_counts: dict[str, dict[str, int]] = defaultdict(
            lambda: {"total": 0, "fix": 0, "revert": 0, "feature": 0}
        )
        file_counts: dict[str, dict[str, int]] = defaultdict(
            lambda: {"total": 0, "fix": 0, "revert": 0}
        )

        for c in commits:
            intent = classify_commit(c.message)
            ac = author_counts[c.author_email]
            ac["total"] += 1
            if intent == CommitIntent.FIX:
                ac["fix"] += 1
            elif intent == CommitIntent.REVERT:
                ac["revert"] += 1
            elif intent == CommitIntent.FEATURE:
                ac["feature"] += 1

            for fc in c.files:
                fcount = file_counts[fc.path]
                fcount["total"] += 1
                if intent == CommitIntent.FIX:
                    fcount["fix"] += 1
                elif intent == CommitIntent.REVERT:
                    fcount["revert"] += 1

        authors: list[AuthorCorrectionLoad] = []
        for email, c in author_counts.items():
            if c["total"] < self.min_commits_for_signal:
                continue
            corrections = c["fix"] + c["revert"]
            ratio = corrections / c["total"]
            authors.append(
                AuthorCorrectionLoad(
                    author_email=email,
                    total_commits=c["total"],
                    fix_commits=c["fix"],
                    revert_commits=c["revert"],
                    feature_commits=c["feature"],
                    correction_ratio=ratio,
                    risk_level=_risk_level(
                        ratio, self.high_threshold, self.critical_threshold,
                    ),
                )
            )
        authors.sort(key=lambda a: -a.correction_ratio)

        files: list[FileCorrectionLoad] = []
        for path, c in file_counts.items():
            if c["total"] < self.min_commits_for_signal:
                continue
            corrections = c["fix"] + c["revert"]
            ratio = corrections / c["total"]
            files.append(
                FileCorrectionLoad(
                    file=path,
                    total_commits=c["total"],
                    fix_commits=c["fix"],
                    revert_commits=c["revert"],
                    correction_ratio=ratio,
                    risk_level=_risk_level(
                        ratio, self.high_threshold, self.critical_threshold,
                    ),
                )
            )
        files.sort(key=lambda f: -f.correction_ratio)

        return CorrectionLoadReport(
            authors=tuple(authors),
            files=tuple(files),
        )


__all__ = [
    "AuthorCorrectionLoad",
    "CorrectionLoadEngine",
    "CorrectionLoadReport",
    "FileCorrectionLoad",
]
