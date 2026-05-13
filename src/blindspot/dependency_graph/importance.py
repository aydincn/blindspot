"""PageRank-based file importance ranking.

Implements PageRank in pure Python so blindspot avoids dragging in
numpy/scipy just for this one algorithm. The graph sizes we care about
(thousands, not millions, of nodes) converge in well under a second.
"""

from dataclasses import dataclass

from blindspot.dependency_graph.models import CentralFile, DependencyGraph


@dataclass
class ImportanceEngine:
    damping: float = 0.85
    max_iter: int = 100
    tol: float = 1.0e-06

    def compute(self, graph: DependencyGraph) -> dict[str, float]:
        if graph.file_count == 0:
            return {}

        # Build the *reverse* adjacency on the fly: for each node, which
        # nodes point at it in the original graph. PageRank ranks files
        # that are *imported by* many others, so we iterate over original
        # edges importer→imported.
        nodes = list(graph.nx_graph.nodes())
        n = len(nodes)
        if n == 1:
            return {nodes[0]: 1.0}

        idx = {node: i for i, node in enumerate(nodes)}
        # For each node u, store (sum_out_weight, list of (v, weight)) where v imports u.
        # In our forward graph, an edge importer→imported means importer
        # casts a vote for imported. PageRank sums incoming votes weighted
        # by importer's score / importer's out-degree.
        in_edges: list[list[tuple[int, float]]] = [[] for _ in range(n)]
        out_weight: list[float] = [0.0] * n
        for importer, imported, data in graph.nx_graph.edges(data=True):
            w = float(data.get("weight", 1.0))
            i_importer = idx[importer]
            i_imported = idx[imported]
            in_edges[i_imported].append((i_importer, w))
            out_weight[i_importer] += w

        damping = self.damping
        teleport = (1.0 - damping) / n
        scores = [1.0 / n] * n

        for _ in range(self.max_iter):
            # Dangling mass (nodes with no outgoing edges) gets redistributed
            # uniformly to keep the total probability conserved.
            dangling_sum = sum(scores[i] for i in range(n) if out_weight[i] == 0.0)
            dangling_contrib = damping * dangling_sum / n

            new_scores = [teleport + dangling_contrib] * n
            for j in range(n):
                contrib_sum = 0.0
                for i, w in in_edges[j]:
                    contrib_sum += scores[i] * (w / out_weight[i])
                new_scores[j] += damping * contrib_sum

            # Check convergence (L1 norm of difference).
            delta = sum(abs(new_scores[i] - scores[i]) for i in range(n))
            scores = new_scores
            if delta < self.tol:
                break

        return {nodes[i]: scores[i] for i in range(n)}


def top_n(
    scores: dict[str, float],
    graph: DependencyGraph,
    n: int = 10,
) -> list[CentralFile]:
    if not scores:
        return []
    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    return [
        CentralFile(
            file=file,
            importance=score,
            in_degree=graph.in_degree(file),
        )
        for file, score in ranked[:n]
    ]


__all__ = ["ImportanceEngine", "top_n"]
