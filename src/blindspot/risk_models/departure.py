from collections.abc import Callable, Iterable
from dataclasses import dataclass

from blindspot.ownership.models import OwnershipMap
from blindspot.risk_models.bus_factor import top_level_dir


def departure_severity(coverage_loss: float, becomes_orphan: bool) -> str:
    if becomes_orphan:
        return "critical"
    if coverage_loss > 0.70:
        return "high"
    if coverage_loss > 0.40:
        return "medium"
    return "low"


@dataclass(frozen=True, slots=True)
class FileDepartureImpact:
    file: str
    coverage_loss: float
    remaining_top_owner: str | None
    remaining_top_coverage: float
    becomes_orphan: bool
    severity: str


@dataclass(frozen=True, slots=True)
class ServiceDepartureImpact:
    service: str
    file_count: int
    affected_files: int
    orphaned_files: int
    avg_coverage_loss: float
    max_coverage_loss: float
    severity: str


@dataclass(frozen=True, slots=True)
class DepartureReport:
    departing: tuple[str, ...]
    files: tuple[FileDepartureImpact, ...]
    services: tuple[ServiceDepartureImpact, ...]
    total_files: int
    affected_files: int
    orphaned_files: int
    avg_coverage_loss: float


@dataclass
class DepartureSimulation:
    orphan_threshold: float = 0.30
    impact_threshold: float = 0.40

    def simulate(
        self,
        ownership: OwnershipMap,
        departing: Iterable[str],
        service_of: Callable[[str], str] = top_level_dir,
    ) -> DepartureReport:
        departing_set = {e.lower() for e in departing}
        by_file: dict[str, list] = {}
        for s in ownership.scores:
            by_file.setdefault(s.file, []).append(s)

        file_impacts: list[FileDepartureImpact] = []
        for path, scores in by_file.items():
            loss = sum(s.coverage for s in scores if s.author_email in departing_set)
            remaining = [s for s in scores if s.author_email not in departing_set]
            remaining.sort(key=lambda s: s.coverage, reverse=True)
            if remaining:
                top = remaining[0]
                top_email = top.author_email
                top_cov = top.coverage
            else:
                top_email = None
                top_cov = 0.0
            becomes_orphan = top_cov < self.orphan_threshold
            file_impacts.append(
                FileDepartureImpact(
                    file=path,
                    coverage_loss=loss,
                    remaining_top_owner=top_email,
                    remaining_top_coverage=top_cov,
                    becomes_orphan=becomes_orphan,
                    severity=departure_severity(loss, becomes_orphan),
                )
            )

        file_impacts.sort(key=lambda f: (f.severity != "critical", -f.coverage_loss))

        by_service: dict[str, list[FileDepartureImpact]] = {}
        for fi in file_impacts:
            by_service.setdefault(service_of(fi.file), []).append(fi)

        service_impacts: list[ServiceDepartureImpact] = []
        for service, fis in by_service.items():
            losses = [fi.coverage_loss for fi in fis]
            affected = sum(1 for fi in fis if fi.coverage_loss > self.impact_threshold)
            orphaned = sum(1 for fi in fis if fi.becomes_orphan)
            avg = sum(losses) / len(losses) if losses else 0.0
            mx = max(losses) if losses else 0.0
            severity = "critical" if orphaned > 0 else departure_severity(mx, False)
            service_impacts.append(
                ServiceDepartureImpact(
                    service=service,
                    file_count=len(fis),
                    affected_files=affected,
                    orphaned_files=orphaned,
                    avg_coverage_loss=avg,
                    max_coverage_loss=mx,
                    severity=severity,
                )
            )

        service_impacts.sort(key=lambda s: (-s.orphaned_files, -s.avg_coverage_loss))

        total_files = len(file_impacts)
        affected = sum(1 for fi in file_impacts if fi.coverage_loss > self.impact_threshold)
        orphaned = sum(1 for fi in file_impacts if fi.becomes_orphan)
        avg = (
            sum(fi.coverage_loss for fi in file_impacts) / total_files if total_files > 0 else 0.0
        )

        return DepartureReport(
            departing=tuple(sorted(departing_set)),
            files=tuple(file_impacts),
            services=tuple(service_impacts),
            total_files=total_files,
            affected_files=affected,
            orphaned_files=orphaned,
            avg_coverage_loss=avg,
        )


__all__ = [
    "DepartureReport",
    "DepartureSimulation",
    "FileDepartureImpact",
    "ServiceDepartureImpact",
    "departure_severity",
]
