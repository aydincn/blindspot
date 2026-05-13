import math
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from blindspot.ai_signal.models import AIFlag, AISignal
from blindspot.collector.models import Commit


@dataclass
class AIAmplificationDetector:
    """Heuristic detector for unusual recent activity that may indicate AI amplification.

    Five signals compared to a per-author baseline:
      1. commit frequency spike
      2. average change-size spike
      3. commit message length spike
      4. share of unusually large single commits
      5. share of off-hours commits
    """

    measurement_days: int = 90
    baseline_days: int = 365
    high_threshold: float = 0.70
    medium_threshold: float = 0.40
    weights: tuple[float, float, float, float, float] = (0.30, 0.25, 0.20, 0.15, 0.10)
    min_baseline_commits: int = 5
    as_of: datetime | None = None
    _as_of: datetime = field(init=False)

    def __post_init__(self) -> None:
        self._as_of = (self.as_of or datetime.now(UTC)).astimezone(UTC)

    def detect(self, commits: Iterable[Commit]) -> dict[str, AISignal]:
        recent_cutoff = self._as_of - timedelta(days=self.measurement_days)
        baseline_cutoff = recent_cutoff - timedelta(days=self.baseline_days)

        recent: dict[str, list[Commit]] = {}
        baseline: dict[str, list[Commit]] = {}
        for c in commits:
            if c.authored_at >= recent_cutoff:
                recent.setdefault(c.author_email, []).append(c)
            elif c.authored_at >= baseline_cutoff:
                baseline.setdefault(c.author_email, []).append(c)

        results: dict[str, AISignal] = {}
        for email in set(recent) | set(baseline):
            r = recent.get(email, [])
            b = baseline.get(email, [])
            if not r:
                continue

            if len(b) < self.min_baseline_commits:
                signal = self._insufficient_baseline_signal(email, r, b)
            else:
                freq = self._frequency_score(r, b)
                vol = self._volume_score(r, b)
                msg = self._message_score(r, b)
                large = self._large_commit_score(r, b)
                timing = self._timing_score(r, b)

                w = self.weights
                score = (
                    freq * w[0] + vol * w[1] + msg * w[2] + large * w[3] + timing * w[4]
                )
                flag = self._flag_from_score(score)

                signal = AISignal(
                    author_email=email,
                    flag=flag,
                    score=score,
                    frequency_score=freq,
                    volume_score=vol,
                    message_score=msg,
                    large_commit_score=large,
                    timing_score=timing,
                    recent_commits=len(r),
                    baseline_commits=len(b),
                )
            results[email] = signal
        return results

    def _flag_from_score(self, score: float) -> AIFlag:
        if score >= self.high_threshold:
            return AIFlag.HIGH
        if score >= self.medium_threshold:
            return AIFlag.MEDIUM
        return AIFlag.LOW

    def _insufficient_baseline_signal(
        self, email: str, r: list[Commit], b: list[Commit]
    ) -> AISignal:
        return AISignal(
            author_email=email,
            flag=AIFlag.LOW,
            score=0.0,
            frequency_score=0.0,
            volume_score=0.0,
            message_score=0.0,
            large_commit_score=0.0,
            timing_score=0.0,
            recent_commits=len(r),
            baseline_commits=len(b),
        )

    def _frequency_score(self, r: list[Commit], b: list[Commit]) -> float:
        recent_rate = len(r) / self.measurement_days
        baseline_rate = len(b) / self.baseline_days
        if baseline_rate == 0:
            return 0.0
        ratio = recent_rate / baseline_rate
        return _bucketed_score(ratio, [(3.0, 1.0), (2.0, 0.7), (1.5, 0.4)])

    def _volume_score(self, r: list[Commit], b: list[Commit]) -> float:
        r_avg = _avg_change_size(r)
        b_avg = _avg_change_size(b)
        if b_avg == 0:
            return 0.0
        ratio = r_avg / b_avg
        return _bucketed_score(ratio, [(4.0, 1.0), (2.5, 0.7), (1.5, 0.4)])

    def _message_score(self, r: list[Commit], b: list[Commit]) -> float:
        r_avg = _avg(len(c.message) for c in r)
        b_avg = _avg(len(c.message) for c in b)
        if b_avg == 0:
            return 0.0
        ratio = r_avg / b_avg
        return _bucketed_score(ratio, [(2.5, 1.0), (1.8, 0.6), (1.3, 0.3)])

    def _large_commit_score(self, r: list[Commit], b: list[Commit]) -> float:
        b_avg = _avg_change_size(b)
        if b_avg == 0:
            return 0.0
        threshold = b_avg * 3.0
        large = sum(1 for c in r if _change_size(c) > threshold)
        if not r:
            return 0.0
        ratio = large / len(r)
        return _bucketed_score(ratio, [(0.5, 1.0), (0.3, 0.6), (0.15, 0.3)])

    def _timing_score(self, r: list[Commit], b: list[Commit]) -> float:
        # Off-hours = UTC hours outside the busiest 8-hour window in baseline.
        # If baseline gives no working-hours signal, fall back to a generous default
        # (treat 22:00–08:00 UTC as off-hours).
        baseline_hours = [c.authored_at.hour for c in b]
        if len(baseline_hours) >= self.min_baseline_commits:
            work_start, work_end = _busy_window(baseline_hours)
        else:
            work_start, work_end = 8, 22

        recent_off = sum(1 for c in r if not _within(c.authored_at.hour, work_start, work_end))
        baseline_off = sum(1 for c in b if not _within(c.authored_at.hour, work_start, work_end))
        if len(r) == 0 or len(b) == 0:
            return 0.0
        recent_ratio = recent_off / len(r)
        baseline_ratio = baseline_off / len(b)
        if baseline_ratio == 0:
            ratio = float("inf") if recent_ratio > 0 else 0.0
        else:
            ratio = recent_ratio / baseline_ratio
        return _bucketed_score(ratio, [(2.0, 0.8), (1.5, 0.4)])


def _change_size(c: Commit) -> int:
    return sum(f.additions + f.deletions for f in c.files)


def _avg_change_size(commits: list[Commit]) -> float:
    if not commits:
        return 0.0
    return sum(_change_size(c) for c in commits) / len(commits)


def _avg(values: Iterable[float]) -> float:
    values = list(values)
    if not values:
        return 0.0
    return sum(values) / len(values)


def _bucketed_score(ratio: float, buckets: list[tuple[float, float]]) -> float:
    """buckets sorted desc by threshold; return first matching score, else 0."""
    if math.isinf(ratio) or math.isnan(ratio):
        return buckets[0][1] if buckets else 0.0
    for threshold, score in buckets:
        if ratio > threshold:
            return score
    return 0.0


def _busy_window(hours: list[int]) -> tuple[int, int]:
    """Find the 8-hour window with the most commits.

    Returns (start_hour_inclusive, end_hour_exclusive) in UTC. Works on a circular
    hour clock so a window of (20, 4) means 20:00 → 04:00 UTC.
    """
    counts = [0] * 24
    for h in hours:
        if 0 <= h < 24:
            counts[h] += 1
    best_total = -1
    best_start = 8
    for start in range(24):
        total = sum(counts[(start + i) % 24] for i in range(8))
        if total > best_total:
            best_total = total
            best_start = start
    return best_start, (best_start + 8) % 24


def _within(hour: int, start: int, end: int) -> bool:
    if start <= end:
        return start <= hour < end
    return hour >= start or hour < end


__all__ = ["AIAmplificationDetector"]
