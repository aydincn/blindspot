"""Commit intent classifier — derives FIX / REVERT / FEATURE / OTHER from a
commit message.

Used by the Correction Load risk model: a high ratio of fix/revert commits
following a feature commit on the same surface is a "fragile velocity"
pattern — output is high but stability is paying for it.

Detection is intentionally tolerant of multilingual repos (Turkish + English
are first-class) and Conventional Commits prefixes.
"""

from __future__ import annotations

import re
from enum import Enum


class CommitIntent(str, Enum):
    FEATURE = "feature"
    FIX = "fix"
    REVERT = "revert"
    OTHER = "other"


# Conventional Commits-style prefix at the start of the subject line.
# Matches: "fix:", "fix(scope):", "feat:", "feat(scope):", "revert:" etc.
_CONV_RE = re.compile(
    r"^\s*(?P<type>[a-z]+)(?:\([^)]*\))?!?\s*:",
    re.IGNORECASE,
)

# Whole-word keyword detectors. We avoid substring matching because words like
# "infix" or "prefix" would otherwise match "fix".
_FIX_KEYWORDS_EN = (
    "fix", "fixes", "fixed", "fixing", "fixup",
    "bug", "bugs", "bugfix", "hotfix", "patch", "patches",
    "repair", "repairs", "repaired",
    "correct", "corrects", "correction",
    "defect", "broken", "regression",
    "typo", "typos",
    "oops",
)
_FIX_KEYWORDS_TR = (
    "hata", "hatalar", "hatası", "hatayı",
    "düzelt", "düzeltme", "düzeltir", "düzeltildi",
    "gider", "giderildi", "giderme",
    "kırık", "çökme", "çöktü",
    "sorun", "problem", "regresyon",
    "yazım",  # "yazım hatası" → "typo"
)
_REVERT_KEYWORDS_EN = ("revert", "reverts", "reverted", "reverting", "rollback")
_REVERT_KEYWORDS_TR = ("geri-al", "geri-dön", "geri alındı")

_FEATURE_KEYWORDS_EN = ("feat", "feature", "add", "adds", "added", "implement",
                        "introduce", "support")
_FEATURE_KEYWORDS_TR = ("ekle", "eklendi", "yeni", "geçiş", "destek")

_WORD_RE = re.compile(r"\b\w+\b", re.UNICODE)


def _first_line(message: str) -> str:
    return message.splitlines()[0].strip() if message else ""


def _words(text: str) -> set[str]:
    return {m.group(0).lower() for m in _WORD_RE.finditer(text)}


def classify_commit(message: str) -> CommitIntent:
    """Classify a commit message into an intent category.

    Order of precedence:
      1. Conventional Commits prefix (highest signal)
      2. Revert keywords (rarely ambiguous)
      3. Fix keywords
      4. Feature keywords
      5. OTHER
    """
    subject = _first_line(message)
    if not subject:
        return CommitIntent.OTHER

    # Conventional Commits prefix is the highest-confidence signal.
    m = _CONV_RE.match(subject)
    if m:
        t = m.group("type").lower()
        if t == "revert":
            return CommitIntent.REVERT
        if t in ("fix", "bugfix", "hotfix", "patch"):
            return CommitIntent.FIX
        if t in ("feat", "feature"):
            return CommitIntent.FEATURE
        # other conventional types (chore, docs, refactor, test, build, ci, perf, style)
        return CommitIntent.OTHER

    # Git auto-generated revert subjects: `Revert "..."`
    if subject.lower().startswith("revert "):
        return CommitIntent.REVERT

    words = _words(subject)
    if any(w in words for w in _REVERT_KEYWORDS_EN + _REVERT_KEYWORDS_TR):
        return CommitIntent.REVERT
    if any(w in words for w in _FIX_KEYWORDS_EN + _FIX_KEYWORDS_TR):
        return CommitIntent.FIX
    if any(w in words for w in _FEATURE_KEYWORDS_EN + _FEATURE_KEYWORDS_TR):
        return CommitIntent.FEATURE
    return CommitIntent.OTHER


__all__ = ["CommitIntent", "classify_commit"]
