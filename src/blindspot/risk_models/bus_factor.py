from collections.abc import Callable
from dataclasses import dataclass

from blindspot.ownership.models import OwnershipMap

# Dotfile dirs that almost never contain product logic — IDE/agent/tooling
# config. Group them under (config) so service-level bus-factor doesn't
# light up "critical" for a 1-file `.codex/` directory.
CONFIG_DOTFILE_PREFIXES = (
    ".husky",
    ".codex",
    ".do",
    ".agents",
    ".devcontainer",
    ".idea",
    ".vscode",
    ".vs",
    ".cursor",
    ".cody",
    ".aider",
    ".windsurf",
    ".tmuxinator",
    ".bundle",
    ".claude",
    ".config",
    ".cache",
)


def top_level_dir(path: str) -> str:
    cleaned = path.strip().strip('"').strip("'")
    # Paths leaking from rename/diff output sometimes look like
    # `path=<actual>` or contain `=` / whitespace from quoting.
    if not cleaned or "=" in cleaned.split("/", 1)[0] or " " in cleaned.split("/", 1)[0]:
        return "(other)"
    parts = cleaned.split("/", 1)
    if len(parts) <= 1:
        return "(root)"
    head = parts[0]
    if head in CONFIG_DOTFILE_PREFIXES:
        return "(config)"
    return head


def risk_level(bus_factor: int) -> str:
    if bus_factor <= 1:
        return "critical"
    if bus_factor == 2:
        return "high"
    if bus_factor == 3:
        return "medium"
    return "healthy"


@dataclass(frozen=True, slots=True)
class FileBusFactor:
    file: str
    bus_factor: int
    threshold: float
    risk_level: str
    top_owners: tuple[tuple[str, float], ...]


@dataclass(frozen=True, slots=True)
class ServiceBusFactor:
    service: str
    file_count: int
    bus_factor: int
    threshold: float
    risk_level: str
    top_owners: tuple[tuple[str, float], ...]


def _bus_factor_from_coverages(
    coverages: list[tuple[str, float]], threshold: float
) -> tuple[int, tuple[tuple[str, float], ...]]:
    ranked = sorted(coverages, key=lambda x: x[1], reverse=True)
    cumulative = 0.0
    count = 0
    for _, cov in ranked:
        if cov <= 0:
            continue
        cumulative += cov
        count += 1
        if cumulative >= threshold:
            break
    return max(count, 1), tuple(ranked)


@dataclass
class BusFactorEngine:
    threshold: float = 0.80

    def for_files(self, om: OwnershipMap) -> list[FileBusFactor]:
        by_file: dict[str, list[tuple[str, float]]] = {}
        for s in om.scores:
            by_file.setdefault(s.file, []).append((s.author_email, s.coverage))

        results: list[FileBusFactor] = []
        for path, coverages in by_file.items():
            bf, ranked = _bus_factor_from_coverages(coverages, self.threshold)
            results.append(
                FileBusFactor(
                    file=path,
                    bus_factor=bf,
                    threshold=self.threshold,
                    risk_level=risk_level(bf),
                    top_owners=ranked,
                )
            )
        results.sort(key=lambda r: (r.bus_factor, -r.top_owners[0][1] if r.top_owners else 0))
        return results

    def for_services(
        self,
        om: OwnershipMap,
        service_of: Callable[[str], str] = top_level_dir,
    ) -> list[ServiceBusFactor]:
        files_per_service: dict[str, set[str]] = {}
        sum_coverage: dict[tuple[str, str], float] = {}

        for s in om.scores:
            service = service_of(s.file)
            files_per_service.setdefault(service, set()).add(s.file)
            key = (service, s.author_email)
            sum_coverage[key] = sum_coverage.get(key, 0.0) + s.coverage

        results: list[ServiceBusFactor] = []
        for service, files in files_per_service.items():
            file_count = len(files)
            person_coverages: list[tuple[str, float]] = [
                (email, total / file_count)
                for (svc, email), total in sum_coverage.items()
                if svc == service
            ]
            bf, ranked = _bus_factor_from_coverages(person_coverages, self.threshold)
            results.append(
                ServiceBusFactor(
                    service=service,
                    file_count=file_count,
                    bus_factor=bf,
                    threshold=self.threshold,
                    risk_level=risk_level(bf),
                    top_owners=ranked,
                )
            )
        results.sort(key=lambda r: (r.bus_factor, -r.file_count))
        return results
