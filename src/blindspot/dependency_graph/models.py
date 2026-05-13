from dataclasses import dataclass, field

import networkx as nx


@dataclass(frozen=True, slots=True)
class CentralFile:
    """A file ranked among the most depended-on in the repo.

    `importance` is the PageRank score (sums to ~1.0 across all nodes).
    `in_degree` is how many other repo files directly import this one.
    Owner fields are filled in by the CLI layer when ownership is known.
    """
    file: str
    importance: float
    in_degree: int
    top_owner: str | None = None
    top_owner_coverage: float = 0.0


@dataclass(frozen=True, slots=True)
class ModuleNode:
    name: str          # e.g. "src/openhuman"
    file_count: int    # files that aggregated into this module


@dataclass(frozen=True, slots=True)
class ModuleEdge:
    from_module: str
    to_module: str
    weight: int        # sum of underlying file→file edge weights


@dataclass(frozen=True, slots=True)
class ModuleGraph:
    """Module-level rollup of a file DependencyGraph, for visualization."""
    nodes: tuple[ModuleNode, ...]
    edges: tuple[ModuleEdge, ...]


@dataclass
class DependencyGraph:
    """Repo-relative file dependency graph backed by networkx."""
    nx_graph: nx.DiGraph = field(default_factory=nx.DiGraph)

    def add_dependency(self, importer: str, imported: str) -> None:
        if importer == imported:
            return
        if self.nx_graph.has_edge(importer, imported):
            self.nx_graph[importer][imported]["weight"] += 1
        else:
            self.nx_graph.add_edge(importer, imported, weight=1)

    def ensure_node(self, file: str) -> None:
        if not self.nx_graph.has_node(file):
            self.nx_graph.add_node(file)

    @property
    def file_count(self) -> int:
        return self.nx_graph.number_of_nodes()

    @property
    def edge_count(self) -> int:
        return self.nx_graph.number_of_edges()

    def in_degree(self, file: str) -> int:
        if not self.nx_graph.has_node(file):
            return 0
        return self.nx_graph.in_degree(file)


__all__ = [
    "CentralFile",
    "DependencyGraph",
    "ModuleEdge",
    "ModuleGraph",
    "ModuleNode",
]
