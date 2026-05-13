from pathlib import Path

import pytest

from blindspot.dependency_graph import (
    DependencyGraphBuilder,
    ImportanceEngine,
    top_n,
)
from blindspot.dependency_graph.extractors import PythonImportExtractor
from blindspot.dependency_graph.extractors.base import ExtractionContext
from blindspot.dependency_graph.models import DependencyGraph


def _write(root: Path, rel: str, content: str) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)


# ---- DependencyGraph dataclass ---------------------------------------------

def test_dependency_graph_dedupes_self_edges():
    g = DependencyGraph()
    g.add_dependency("a.py", "a.py")  # self-edge ignored
    assert g.edge_count == 0


def test_dependency_graph_increments_weight_on_repeat_edge():
    g = DependencyGraph()
    g.add_dependency("a.py", "b.py")
    g.add_dependency("a.py", "b.py")
    assert g.edge_count == 1
    assert g.nx_graph["a.py"]["b.py"]["weight"] == 2


# ---- Python extractor -------------------------------------------------------

def test_python_resolves_module_to_file(tmp_path: Path):
    ctx = ExtractionContext(
        repo_root=tmp_path,
        repo_files={"pkg/a.py", "pkg/b.py", "pkg/__init__.py"},
    )
    content = "from pkg.b import helper\nimport pkg.b as bb\n"
    imports = PythonImportExtractor().extract("pkg/a.py", content, ctx)
    assert "pkg/b.py" in imports


def test_python_resolves_package_init(tmp_path: Path):
    ctx = ExtractionContext(
        repo_root=tmp_path,
        repo_files={"pkg/__init__.py", "pkg/a.py", "other/__init__.py"},
    )
    content = "from pkg import foo\nimport other\n"
    imports = PythonImportExtractor().extract("pkg/a.py", content, ctx)
    assert "pkg/__init__.py" in imports
    assert "other/__init__.py" in imports


def test_python_relative_import(tmp_path: Path):
    ctx = ExtractionContext(
        repo_root=tmp_path,
        repo_files={"pkg/sub/main.py", "pkg/sub/helper.py", "pkg/utils.py"},
    )
    content = "from .helper import bar\nfrom ..utils import qux\n"
    imports = PythonImportExtractor().extract("pkg/sub/main.py", content, ctx)
    assert "pkg/sub/helper.py" in imports
    assert "pkg/utils.py" in imports


def test_python_ignores_unresolvable_imports(tmp_path: Path):
    ctx = ExtractionContext(
        repo_root=tmp_path, repo_files={"a.py"},
    )
    content = "import os\nimport requests\nfrom collections import OrderedDict\n"
    imports = PythonImportExtractor().extract("a.py", content, ctx)
    assert imports == []


def test_python_resolves_when_symbol_is_in_module(tmp_path: Path):
    # `from pkg.bar import helper` where helper is defined inside bar.py
    ctx = ExtractionContext(
        repo_root=tmp_path,
        repo_files={"pkg/bar.py", "main.py"},
    )
    content = "from pkg.bar import helper\n"
    imports = PythonImportExtractor().extract("main.py", content, ctx)
    assert imports == ["pkg/bar.py"]


# ---- Builder end-to-end -----------------------------------------------------

def test_builder_walks_repo_and_builds_graph(tmp_path: Path):
    _write(tmp_path, "core/util.py", "")
    _write(tmp_path, "core/__init__.py", "")
    _write(tmp_path, "app/main.py", "from core.util import x\n")
    _write(tmp_path, "app/__init__.py", "")
    _write(tmp_path, "node_modules/whatever.py", "")     # should skip
    _write(tmp_path, "README.md", "# hello")             # no extractor

    graph = DependencyGraphBuilder().build(tmp_path)
    nodes = set(graph.nx_graph.nodes())
    assert "app/main.py" in nodes
    assert "core/util.py" in nodes
    # node_modules excluded
    assert "node_modules/whatever.py" not in nodes
    # Edge from main → util
    assert graph.nx_graph.has_edge("app/main.py", "core/util.py")


def test_builder_skips_oversize_files(tmp_path: Path):
    _write(tmp_path, "tiny.py", "import other\n")
    big = "x = 1\n" * 100_000  # > 1MB? let's reduce limit instead
    _write(tmp_path, "big.py", big)

    builder = DependencyGraphBuilder(max_file_bytes=1000)
    graph = builder.build(tmp_path)
    # tiny.py kept (small)
    assert "tiny.py" in graph.nx_graph.nodes()
    # big.py over the size limit → not even added as a node
    assert "big.py" not in graph.nx_graph.nodes()


# ---- Importance / PageRank --------------------------------------------------

def test_pagerank_central_file_ranks_highest(tmp_path: Path):
    # Many files depend on `core.py`; nobody depends on `leaf.py`.
    _write(tmp_path, "core.py", "")
    _write(tmp_path, "leaf.py", "import core\n")
    _write(tmp_path, "a.py", "import core\n")
    _write(tmp_path, "b.py", "import core\n")
    _write(tmp_path, "c.py", "import core\n")

    graph = DependencyGraphBuilder().build(tmp_path)
    scores = ImportanceEngine().compute(graph)
    # core.py is imported by 4 others; should rank well above leaf.py
    assert scores["core.py"] > scores["leaf.py"]
    assert scores["core.py"] == max(scores.values())


def test_top_n_returns_central_files(tmp_path: Path):
    _write(tmp_path, "core.py", "")
    _write(tmp_path, "a.py", "import core\n")
    _write(tmp_path, "b.py", "import core\n")

    graph = DependencyGraphBuilder().build(tmp_path)
    scores = ImportanceEngine().compute(graph)
    centrals = top_n(scores, graph, n=2)
    assert centrals[0].file == "core.py"
    assert centrals[0].in_degree == 2
    assert centrals[0].importance > 0


def test_empty_graph_returns_empty_scores(tmp_path: Path):
    # No .py files at all
    _write(tmp_path, "README.md", "hello")
    graph = DependencyGraphBuilder().build(tmp_path)
    scores = ImportanceEngine().compute(graph)
    assert scores == {}
    assert top_n(scores, graph) == []


# ---- Module aggregation ----------------------------------------------------

from blindspot.dependency_graph.aggregation import aggregate_modules, module_of


def test_module_of_buckets_root_files():
    assert module_of("Cargo.toml") == "(root)"
    assert module_of("README.md") == "(root)"


def test_module_of_takes_first_two_segments_by_default():
    assert module_of("src/openhuman/config/mod.rs") == "src/openhuman"
    assert module_of("app/src/services/foo.ts", depth=2) == "app/src"
    assert module_of("app/src/services/foo.ts", depth=3) == "app/src/services"


def test_aggregate_modules_drops_intra_module_edges(tmp_path: Path):
    # core/util ↔ core/helper is intra-module; core/util → app/main is inter.
    _write(tmp_path, "core/util.py", "")
    _write(tmp_path, "core/__init__.py", "")
    _write(tmp_path, "core/helper.py", "from core.util import x\n")
    _write(tmp_path, "app/main.py", "from core.util import x\n")
    _write(tmp_path, "app/__init__.py", "")

    graph = DependencyGraphBuilder().build(tmp_path)
    mg = aggregate_modules(graph, depth=1)
    pairs = {(e.from_module, e.to_module) for e in mg.edges}
    assert ("app", "core") in pairs
    # No core→core self-edge — that was intra-module.
    assert ("core", "core") not in pairs


def test_aggregate_modules_sums_edge_weights(tmp_path: Path):
    _write(tmp_path, "core/util.py", "")
    _write(tmp_path, "core/__init__.py", "")
    _write(tmp_path, "core/helper.py", "")
    _write(tmp_path, "app/__init__.py", "")
    _write(tmp_path, "app/a.py", "from core.util import x\n")
    _write(tmp_path, "app/b.py", "from core.helper import y\n")

    graph = DependencyGraphBuilder().build(tmp_path)
    mg = aggregate_modules(graph, depth=1)
    by_pair = {(e.from_module, e.to_module): e.weight for e in mg.edges}
    # Two distinct file→file edges roll up to the same module pair → weight 2.
    assert by_pair[("app", "core")] == 2


def test_aggregate_modules_empty_graph_returns_empty():
    from blindspot.dependency_graph.models import DependencyGraph
    mg = aggregate_modules(DependencyGraph())
    assert mg.nodes == ()
    assert mg.edges == ()


def test_aggregate_modules_respects_top_k(tmp_path: Path):
    # Build six modules each importing one shared "core" module.
    _write(tmp_path, "core/util.py", "")
    _write(tmp_path, "core/__init__.py", "")
    for letter in "abcdef":
        _write(tmp_path, f"{letter}/__init__.py", "")
        _write(tmp_path, f"{letter}/main.py", "from core.util import x\n")

    graph = DependencyGraphBuilder().build(tmp_path)
    mg = aggregate_modules(graph, depth=1, top_k=3)
    # core + 2 callers max — total 3 modules kept.
    names = {n.name for n in mg.nodes}
    assert len(names) <= 3
    assert "core" in names  # highest-degree module always kept


# ---- LLM fallback -----------------------------------------------------------

from dataclasses import dataclass as _dc, field as _field

from blindspot.dependency_graph.llm_fallback import LLMImportExtractor


@_dc
class _MockCompleter:
    response: str = "[]"
    calls: list[tuple[str, str]] = _field(default_factory=list)

    def complete(self, system: str, user: str) -> str:
        self.calls.append((system, user))
        return self.response


def test_llm_runs_on_every_file_and_unions_with_static(tmp_path: Path):
    # main.py statically imports helper.py; LLM additionally returns
    # extra.py. Final graph must contain BOTH edges (union, static-first).
    _write(tmp_path, "main.py", "from helper import x\n")
    _write(tmp_path, "helper.py", "")
    _write(tmp_path, "extra.py", "")
    mock = _MockCompleter(response='["extra.py"]')
    builder = DependencyGraphBuilder(
        llm_fallback=LLMImportExtractor(client=mock),
    )
    graph = builder.build(tmp_path)
    assert len(mock.calls) >= 1
    assert graph.nx_graph.has_edge("main.py", "helper.py")
    assert graph.nx_graph.has_edge("main.py", "extra.py")


def test_llm_runs_when_static_returns_nothing(tmp_path: Path):
    _write(tmp_path, "main.weird", "import helper_thing\n")
    _write(tmp_path, "helper.weird", "")
    # Custom no-op extractor that always returns [] — simulates a DSL we
    # don't statically support; LLM must fill the gap.

    @_dc
    class _NoOpExtractor:
        extensions: tuple[str, ...] = (".weird",)
        needs_namespace_index: bool = False
        def prime_namespace_index(self, *a, **kw) -> None: return None
        def extract(self, *a, **kw) -> list[str]: return []

    mock = _MockCompleter(response='["helper.weird"]')
    builder = DependencyGraphBuilder(
        extractors={".weird": _NoOpExtractor()},
        llm_fallback=LLMImportExtractor(client=mock),
    )
    graph = builder.build(tmp_path)
    # LLM is invoked for both .weird files (every file when opted-in).
    assert len(mock.calls) >= 1
    assert graph.nx_graph.has_edge("main.weird", "helper.weird")


def test_llm_fallback_respects_max_calls_cap(tmp_path: Path):
    @_dc
    class _NoOp:
        extensions: tuple[str, ...] = (".weird",)
        needs_namespace_index: bool = False
        def prime_namespace_index(self, *a, **kw) -> None: return None
        def extract(self, *a, **kw) -> list[str]: return []

    for i in range(5):
        _write(tmp_path, f"f{i}.weird", f"import thing{i}\n")
    mock = _MockCompleter(response="[]")
    extractor = LLMImportExtractor(client=mock, max_calls=2)
    builder = DependencyGraphBuilder(
        extractors={".weird": _NoOp()}, llm_fallback=extractor,
    )
    builder.build(tmp_path)
    assert len(mock.calls) == 2  # cap honoured


def test_llm_fallback_cache_avoids_duplicate_calls(tmp_path: Path):
    @_dc
    class _NoOp:
        extensions: tuple[str, ...] = (".weird",)
        needs_namespace_index: bool = False
        def prime_namespace_index(self, *a, **kw) -> None: return None
        def extract(self, *a, **kw) -> list[str]: return []

    # Two files with identical content — cache should hit on second.
    _write(tmp_path, "a.weird", "import same\n")
    _write(tmp_path, "b.weird", "import same\n")
    mock = _MockCompleter(response="[]")
    builder = DependencyGraphBuilder(
        extractors={".weird": _NoOp()},
        llm_fallback=LLMImportExtractor(client=mock),
    )
    builder.build(tmp_path)
    assert len(mock.calls) == 1


def test_llm_runs_even_when_file_has_no_import_pattern(tmp_path: Path):
    # File with NO import-like keywords — LLM must still be called when
    # opt-in is on (we removed the heuristic pattern gate).
    _write(tmp_path, "main.py", "x = 1\ny = x + 2\n")
    _write(tmp_path, "other.py", "")
    mock = _MockCompleter(response='["other.py"]')
    builder = DependencyGraphBuilder(
        llm_fallback=LLMImportExtractor(client=mock),
    )
    graph = builder.build(tmp_path)
    assert len(mock.calls) >= 1
    assert graph.nx_graph.has_edge("main.py", "other.py")
