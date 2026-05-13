import math
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime

from blindspot.collector.models import Commit
from blindspot.ownership.models import OwnershipMap
from blindspot.risk_models.bus_factor import top_level_dir


def decay_risk_level(score: float) -> str:
    if score > 0.75:
        return "critical"
    if score > 0.50:
        return "high"
    if score > 0.25:
        return "medium"
    return "low"


@dataclass(frozen=True, slots=True)
class FileDecay:
    file: str
    top_owner: str
    top_owner_coverage: float
    owner_last_touch: datetime
    days_since_owner_touch: float
    lines_changed_after: int
    volatility: float
    person_absence: float
    decay_score: float
    risk_level: str
    projections: dict[int, float]


@dataclass(frozen=True, slots=True)
class ServiceDecay:
    service: str
    file_count: int
    avg_decay_score: float
    max_decay_score: float
    risk_level: str
    critical_files: int


@dataclass
class KnowledgeDecayEngine:
    volatility_weight: float = 0.55
    absence_weight: float = 0.45
    absence_lambda: float = 0.015
    volatility_k: float = 0.007
    projection_days: tuple[int, ...] = (30, 60, 90)
    as_of: datetime | None = None
    _as_of: datetime = field(init=False)

    def __post_init__(self) -> None:
        self._as_of = (self.as_of or datetime.now(UTC)).astimezone(UTC)

    def for_files(self, commits: Iterable[Commit], ownership: OwnershipMap) -> list[FileDecay]:
        history = self._build_file_history(commits)
        top_owners = self._top_owners(ownership)

        results: list[FileDecay] = []
        for file, owner_records in top_owners.items():
            owner_email, owner_coverage = owner_records
            file_events = history.get(file, [])
            owner_events = [e for e in file_events if e[0] == owner_email]
            if not owner_events:
                continue
            owner_last = max(e[1] for e in owner_events)
            lines_after = sum(
                add + delete
                for (author, ts, add, delete) in file_events
                if author != owner_email and ts > owner_last
            )
            days_since = max(0.0, (self._as_of - owner_last).total_seconds() / 86400.0)

            volatility = 1.0 - math.exp(-self.volatility_k * lines_after)
            absence = 1.0 - math.exp(-self.absence_lambda * days_since)
            decay = volatility * self.volatility_weight + absence * self.absence_weight

            projections = {}
            for offset in self.projection_days:
                future_days = days_since + offset
                future_absence = 1.0 - math.exp(-self.absence_lambda * future_days)
                projections[offset] = (
                    volatility * self.volatility_weight + future_absence * self.absence_weight
                )

            results.append(
                FileDecay(
                    file=file,
                    top_owner=owner_email,
                    top_owner_coverage=owner_coverage,
                    owner_last_touch=owner_last,
                    days_since_owner_touch=days_since,
                    lines_changed_after=lines_after,
                    volatility=volatility,
                    person_absence=absence,
                    decay_score=decay,
                    risk_level=decay_risk_level(decay),
                    projections=projections,
                )
            )

        results.sort(key=lambda r: r.decay_score, reverse=True)
        return results

    def for_services(
        self,
        commits: Iterable[Commit],
        ownership: OwnershipMap,
        service_of: Callable[[str], str] = top_level_dir,
    ) -> list[ServiceDecay]:
        file_decays = self.for_files(commits, ownership)
        by_service: dict[str, list[FileDecay]] = {}
        for fd in file_decays:
            by_service.setdefault(service_of(fd.file), []).append(fd)

        results: list[ServiceDecay] = []
        for service, fds in by_service.items():
            scores = [fd.decay_score for fd in fds]
            avg = sum(scores) / len(scores)
            mx = max(scores)
            critical = sum(1 for fd in fds if fd.risk_level == "critical")
            results.append(
                ServiceDecay(
                    service=service,
                    file_count=len(fds),
                    avg_decay_score=avg,
                    max_decay_score=mx,
                    risk_level=decay_risk_level(avg),
                    critical_files=critical,
                )
            )
        results.sort(key=lambda r: r.avg_decay_score, reverse=True)
        return results

    @staticmethod
    def _build_file_history(
        commits: Iterable[Commit],
    ) -> dict[str, list[tuple[str, datetime, int, int]]]:
        index: dict[str, list[tuple[str, datetime, int, int]]] = {}
        for c in commits:
            for f in c.files:
                index.setdefault(f.path, []).append(
                    (c.author_email, c.authored_at, f.additions, f.deletions)
                )
        return index

    @staticmethod
    def _top_owners(ownership: OwnershipMap) -> dict[str, tuple[str, float]]:
        result: dict[str, tuple[str, float]] = {}
        for s in ownership.scores:
            current = result.get(s.file)
            if current is None or s.coverage > current[1]:
                result[s.file] = (s.author_email, s.coverage)
        return result


__all__ = ["FileDecay", "KnowledgeDecayEngine", "ServiceDecay", "decay_risk_level"]
