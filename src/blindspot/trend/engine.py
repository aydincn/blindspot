"""Time-trend analysis for resilience scores.

Computes historical resilience snapshots by re-running ownership + decay
engines at multiple as_of dates. Review and activity sub-scores require
present-only data (review graph, AI baselines), so historical snapshots only
include ownership + decay — the most material signals for long-term trend.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Iterable

from blindspot.collector.git import Commit
from blindspot.ownership import OwnershipEngine
from blindspot.resilience import ResilienceScore, ResilienceScoreEngine
from blindspot.risk_models import BusFactorEngine, KnowledgeDecayEngine


@dataclass(frozen=True, slots=True)
class TrendSnapshot:
    as_of: datetime
    days_ago: int
    score: ResilienceScore


@dataclass(frozen=True, slots=True)
class ResilienceTrend:
    snapshots: tuple[TrendSnapshot, ...]

    @property
    def latest(self) -> TrendSnapshot | None:
        return self.snapshots[-1] if self.snapshots else None

    @property
    def delta_overall(self) -> int | None:
        # Change from oldest historical snapshot to latest.
        if len(self.snapshots) < 2:
            return None
        return self.snapshots[-1].score.overall - self.snapshots[0].score.overall


DEFAULT_OFFSETS_DAYS = (90, 60, 30, 0)


@dataclass
class TrendEngine:
    offsets_days: tuple[int, ...] = DEFAULT_OFFSETS_DAYS

    def compute(
        self,
        commits: Iterable[Commit],
        now: datetime | None = None,
    ) -> ResilienceTrend:
        commits = tuple(commits)
        now = (now or datetime.now(UTC)).astimezone(UTC)

        snapshots: list[TrendSnapshot] = []
        for days in sorted(self.offsets_days, reverse=True):  # oldest first
            as_of = now - timedelta(days=days)
            sliced = tuple(c for c in commits if c.authored_at <= as_of)
            if not sliced:
                continue
            ownership = OwnershipEngine(as_of=as_of).compute(sliced)
            services = BusFactorEngine().for_services(ownership)
            decays = KnowledgeDecayEngine(as_of=as_of).for_files(sliced, ownership)
            score = ResilienceScoreEngine().compute(services, decays)
            snapshots.append(TrendSnapshot(as_of=as_of, days_ago=days, score=score))

        return ResilienceTrend(snapshots=tuple(snapshots))


__all__ = ["DEFAULT_OFFSETS_DAYS", "ResilienceTrend", "TrendEngine", "TrendSnapshot"]
