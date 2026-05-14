from dataclasses import dataclass, field
from datetime import datetime

from blindspot.actions import RecommendedAction
from blindspot.ai_signal.models import AuthorProfile
from blindspot.codeowners import CodeOwnersReport
from blindspot.dependency_graph import CentralFile, CentralModel, ModuleGraph
from blindspot.diff_analysis import DiffChurnSummary
from blindspot.narrative import DepartureNarrative, NarrativeReport
from blindspot.resilience import ResilienceScore
from blindspot.review_graph.engine import FileReviewStats
from blindspot.risk_models.bus_factor import FileBusFactor, ServiceBusFactor
from blindspot.risk_models.departure import DepartureReport
from blindspot.risk_models.knowledge_decay import FileDecay, ServiceDecay
from blindspot.trend import ResilienceTrend


@dataclass(frozen=True, slots=True)
class ReportContext:
    repo_path: str
    generated_at: datetime
    since_days: int
    blindspot_version: str

    commit_count: int
    author_count: int
    file_count: int
    additions: int
    deletions: int

    services: tuple[ServiceBusFactor, ...]
    critical_files: tuple[FileBusFactor, ...]
    decay_top: tuple[FileDecay, ...]
    decay_services: tuple[ServiceDecay, ...]
    names: dict[str, str] = field(default_factory=dict)

    reviews_enabled: bool = False
    pr_count: int = 0
    pr_truncated: bool = False
    top_rubber_stamps: tuple[FileReviewStats, ...] = ()
    low_diversity_files: tuple[FileReviewStats, ...] = ()
    diff_summary: DiffChurnSummary | None = None
    ai_signal_enabled: bool = False
    author_profiles: tuple[AuthorProfile, ...] = ()
    recommendations: tuple[RecommendedAction, ...] = ()
    resilience: ResilienceScore | None = None
    trend: ResilienceTrend | None = None
    codeowners: CodeOwnersReport | None = None
    narrative: NarrativeReport | None = None
    top_central_files: tuple[CentralFile, ...] = ()
    module_graph: ModuleGraph | None = None
    top_central_models: tuple[CentralModel, ...] = ()
    departure_scenarios: tuple[DepartureReport, ...] = ()

    def label(self, email: str) -> str:
        name = self.names.get(email)
        if name and name != email:
            return f"{name} ({email})"
        return email


@dataclass(frozen=True, slots=True)
class RemainingOwnerGap:
    """A person who could absorb files orphaned by a departure.

    `picked_up_files` counts the orphan-becoming files where this person
    would become the new top owner. Used to surface concrete successor
    candidates in the departure report.
    """
    email: str
    picked_up_files: int
    avg_coverage_on_picked_up: float


def compute_remaining_gaps(
    report: "DepartureReport", limit: int = 10
) -> tuple[RemainingOwnerGap, ...]:
    """Rank potential successors for the orphan-becoming files.

    For each file that loses its primary expert (severity=critical), the
    `remaining_top_owner` is the strongest remaining contributor — they
    are weak (<30% coverage by definition of orphan) but still our best
    inheritor candidate. Aggregating across orphan files gives a
    concrete short-list of people to pair with before departure.
    """
    by_email: dict[str, list[float]] = {}
    for f in report.files:
        if f.becomes_orphan and f.remaining_top_owner:
            by_email.setdefault(f.remaining_top_owner, []).append(
                f.remaining_top_coverage
            )
    gaps = [
        RemainingOwnerGap(
            email=email,
            picked_up_files=len(covs),
            avg_coverage_on_picked_up=sum(covs) / len(covs),
        )
        for email, covs in by_email.items()
    ]
    gaps.sort(key=lambda g: (-g.picked_up_files, -g.avg_coverage_on_picked_up))
    return tuple(gaps[:limit])


@dataclass(frozen=True, slots=True)
class DepartureContext:
    """Standalone HTML report for a single departure simulation.

    Separate from `ReportContext` because the surface is different: the
    audience wants 'what happens if this person leaves' as a focused
    briefing, not a full repo health report.
    """
    repo_path: str
    generated_at: datetime
    since_days: int
    blindspot_version: str

    departure: DepartureReport
    names: dict[str, str] = field(default_factory=dict)
    narrative: DepartureNarrative | None = None
    remaining_gaps: tuple[RemainingOwnerGap, ...] = ()

    def label(self, email: str) -> str:
        name = self.names.get(email)
        if name and name != email:
            return f"{name} ({email})"
        return email
