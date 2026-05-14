"""Roll a file-level DependencyGraph up to a module-level summary.

Used to render a Mermaid architecture diagram in the HTML report. A
"module" is the top-N path segments of a file (default 2): for example
`src/openhuman/config/mod.rs` rolls up to `src/openhuman`. Intra-module
edges are dropped (they don't help a high-level picture); inter-module
edges are summed.

To keep the diagram readable we cap the diagram to the top-K modules by
total degree (in + out). Edges whose endpoints aren't in that set are
dropped.
"""

from blindspot.dependency_graph.models import (
    DependencyGraph,
    ModuleEdge,
    ModuleGraph,
    ModuleNode,
)

DEFAULT_DEPTH = 2
DEFAULT_TOP_K = 12
DEFAULT_MIN_WEIGHT = 1


def module_of(path: str, depth: int = DEFAULT_DEPTH, peel_prefix: str = "") -> str:
    """Map a repo-relative path to a module name.

    Strategy: drop the filename, then keep up to `depth` leading
    directory segments. Top-level files (no parent dir) bucket under
    "(root)". This way `scripts/foo.mjs` and `scripts/bar.mjs` both
    roll up to the same "scripts" module rather than each becoming
    its own one-file node.

    `peel_prefix` is the common parent prefix shared by *every* file
    in the graph — stripping it before aggregation lets us drill into
    the internal architecture instead of bucketing everything into a
    single top-level module. (e.g. all of Flask's files live under
    `src/flask/`, so peeling that off makes `json/`, `cli.py`, etc.
    visible as separate modules.)
    """
    rel = path
    if peel_prefix:
        prefix = peel_prefix.rstrip("/") + "/"
        if rel.startswith(prefix):
            rel = rel[len(prefix):]
    parts = [p for p in rel.split("/") if p]
    if len(parts) <= 1:
        return "(root)"
    parent_parts = parts[:-1]
    return "/".join(parent_parts[:depth])


def _longest_common_parent(files: list[str]) -> str:
    """Find the longest directory prefix shared by every file's parent.

    Used to auto-detect the 'architectural root' for a repo whose code
    all lives under a deeply nested folder (e.g. `src/flask/`). Returns
    an empty string when there's no common prefix.
    """
    parents = [
        f.rsplit("/", 1)[0].split("/") if "/" in f else []
        for f in files
    ]
    if not parents or not parents[0]:
        return ""
    common = list(parents[0])
    for p in parents[1:]:
        new: list[str] = []
        for a, b in zip(common, p):
            if a == b:
                new.append(a)
            else:
                break
        common = new
        if not common:
            return ""
    return "/".join(common)


def aggregate_modules(
    graph: DependencyGraph,
    depth: int = DEFAULT_DEPTH,
    top_k: int = DEFAULT_TOP_K,
    min_weight: int = DEFAULT_MIN_WEIGHT,
) -> ModuleGraph:
    """Roll the file graph up to a module-level graph for visualization."""
    if graph.file_count == 0:
        return ModuleGraph(nodes=(), edges=())

    # Auto-peel a shared parent prefix so we surface internal architecture
    # rather than a single "everything" module.
    nodes_list = list(graph.nx_graph.nodes())
    peel = _longest_common_parent(nodes_list)

    file_to_module: dict[str, str] = {}
    file_counts: dict[str, int] = {}
    for f in graph.nx_graph.nodes():
        m = module_of(f, depth, peel_prefix=peel)
        file_to_module[f] = m
        file_counts[m] = file_counts.get(m, 0) + 1

    edge_weights: dict[tuple[str, str], int] = {}
    for u, v, data in graph.nx_graph.edges(data=True):
        mu = file_to_module.get(u)
        mv = file_to_module.get(v)
        if mu is None or mv is None or mu == mv:
            continue
        w = int(data.get("weight", 1))
        key = (mu, mv)
        edge_weights[key] = edge_weights.get(key, 0) + w

    # Score modules by total degree to pick the top-K to display.
    module_degree: dict[str, int] = {}
    for (mu, mv), w in edge_weights.items():
        module_degree[mu] = module_degree.get(mu, 0) + w
        module_degree[mv] = module_degree.get(mv, 0) + w

    ranked = sorted(
        module_degree.items(), key=lambda kv: (-kv[1], kv[0])
    )
    selected = {m for m, _ in ranked[:top_k]}

    edges = [
        ModuleEdge(from_module=mu, to_module=mv, weight=w)
        for (mu, mv), w in edge_weights.items()
        if mu in selected and mv in selected and w >= min_weight
    ]
    edges.sort(key=lambda e: (-e.weight, e.from_module, e.to_module))

    # Only emit nodes that actually participate in a kept edge — isolated
    # nodes clutter the diagram without telling you anything.
    referenced: set[str] = set()
    for e in edges:
        referenced.add(e.from_module)
        referenced.add(e.to_module)

    nodes = tuple(
        sorted(
            (
                ModuleNode(name=m, file_count=file_counts.get(m, 0))
                for m in referenced
            ),
            key=lambda n: (-n.file_count, n.name),
        )
    )
    return ModuleGraph(nodes=nodes, edges=tuple(edges))


__all__ = ["DEFAULT_DEPTH", "DEFAULT_TOP_K", "aggregate_modules", "module_of"]
