from dataclasses import dataclass, field
from datetime import datetime

from blindspot.actions import RecommendedAction
from blindspot.ai_signal.models import AuthorProfile
from blindspot.codeowners import CodeOwnersReport
from blindspot.dependency_graph import CentralFile, ModuleGraph
from blindspot.diff_analysis import DiffChurnSummary
from blindspot.narrative import NarrativeReport
from blindspot.resilience import ResilienceScore
from blindspot.review_graph.engine import FileReviewStats
from blindspot.risk_models.bus_factor import FileBusFactor, ServiceBusFactor
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

    def label(self, email: str) -> str:
        name = self.names.get(email)
        if name and name != email:
            return f"{name} ({email})"
        return email
