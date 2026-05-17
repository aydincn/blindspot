"""Knowledge graph — bipartite (contributor × service) coverage map.

A compact visualisation surface for *who owns what* at a glance. The
graph is intentionally tiny — top-N contributors × top-M services with
edges only for non-trivial coverage — so it stays readable in a
boardroom slide. For the underlying file-level structure, see
``dependency_graph/`` (this is a different graph).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from blindspot.ownership.models import OwnershipMap
from blindspot.risk_models.bus_factor import top_level_dir


@dataclass(frozen=True, slots=True)
class KnowledgeEdge:
    contributor: str  # email
    service: str
    coverage: float   # 0.0–1.0, share of service files dominated by this person


@dataclass(frozen=True, slots=True)
class KnowledgeGraph:
    contributors: tuple[str, ...]
    services: tuple[str, ...]
    edges: tuple[KnowledgeEdge, ...]


def build_knowledge_graph(
    ownership: OwnershipMap,
    *,
    service_of: Callable[[str], str] = top_level_dir,
    top_contributors: int = 5,
    top_services: int = 6,
    min_edge_coverage: float = 0.10,
) -> KnowledgeGraph:
    """Build a small bipartite contributor × service coverage graph.

    * ``top_contributors`` and ``top_services`` cap how many of each are
      displayed (by aggregate coverage).
    * ``min_edge_coverage`` drops edges below this threshold so the graph
      is not a hairball.
    """
    # Aggregate: per (contributor, service) → summed coverage.
    pair_cov: dict[tuple[str, str], float] = {}
    per_service_files: dict[str, set[str]] = {}
    per_contrib_total: dict[str, float] = {}
    per_service_total: dict[str, float] = {}
    for s in ownership.scores:
        svc = service_of(s.file)
        key = (s.author_email, svc)
        pair_cov[key] = pair_cov.get(key, 0.0) + s.coverage
        per_service_files.setdefault(svc, set()).add(s.file)
        per_contrib_total[s.author_email] = (
            per_contrib_total.get(s.author_email, 0.0) + s.coverage
        )
        per_service_total[svc] = per_service_total.get(svc, 0.0) + s.coverage

    # Pick top-N contributors and top-M services by aggregate coverage.
    contrib_ranked = sorted(
        per_contrib_total.items(), key=lambda kv: -kv[1]
    )[:top_contributors]
    service_ranked = sorted(
        per_service_total.items(), key=lambda kv: -kv[1]
    )[:top_services]
    contributors = tuple(c for c, _ in contrib_ranked)
    services = tuple(s for s, _ in service_ranked)
    contrib_set = set(contributors)
    service_set = set(services)

    edges: list[KnowledgeEdge] = []
    for (contributor, svc), cov_sum in pair_cov.items():
        if contributor not in contrib_set or svc not in service_set:
            continue
        files_in_service = len(per_service_files.get(svc, ()))
        if files_in_service == 0:
            continue
        per_service_share = cov_sum / files_in_service
        if per_service_share < min_edge_coverage:
            continue
        edges.append(
            KnowledgeEdge(
                contributor=contributor,
                service=svc,
                coverage=per_service_share,
            )
        )

    edges.sort(key=lambda e: -e.coverage)
    return KnowledgeGraph(
        contributors=contributors,
        services=services,
        edges=tuple(edges),
    )


__all__ = [
    "KnowledgeEdge",
    "KnowledgeGraph",
    "build_knowledge_graph",
]
