from pathlib import Path

import pytest

from blindspot.dependency_graph import (
    DependencyGraphBuilder,
    ImportanceEngine,
    top_n,
)
from blindspot.dependency_graph.builder import auto_detect_code_root
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


def test_python_ast_resolves_aliased_import(tmp_path: Path):
    _write(tmp_path, "core/util.py", "")
    _write(tmp_path, "main.py", "import core.util as cu\n")
    graph = DependencyGraphBuilder(include_tests=True).build(tmp_path)
    assert graph.nx_graph.has_edge("main.py", "core/util.py")


def test_python_ast_resolves_parenthesised_from_import(tmp_path: Path):
    _write(tmp_path, "core/util.py", "")
    _write(tmp_path, "core/__init__.py", "")
    _write(tmp_path, "main.py", "from core.util import (\n    foo,\n    bar,\n)\n")
    graph = DependencyGraphBuilder(include_tests=True).build(tmp_path)
    assert graph.nx_graph.has_edge("main.py", "core/util.py")


def test_python_ast_records_inheritance_edge(tmp_path: Path):
    # base.py declares Base; sub.py imports it and inherits → edge expected.
    _write(tmp_path, "base.py", "class Base:\n    pass\n")
    _write(tmp_path, "sub.py", "from base import Base\nclass Sub(Base):\n    pass\n")
    graph = DependencyGraphBuilder(include_tests=True).build(tmp_path)
    assert graph.nx_graph.has_edge("sub.py", "base.py")


def test_python_ast_detects_dataclass_model(tmp_path: Path):
    from blindspot.dependency_graph.extractors.base import ExtractionContext
    _write(tmp_path, "models.py", (
        "from dataclasses import dataclass\n"
        "@dataclass\n"
        "class User:\n    name: str\n"
    ))
    ctx = ExtractionContext(repo_root=tmp_path, repo_files={"models.py"})
    PythonImportExtractor().extract(
        "models.py", (tmp_path / "models.py").read_text(), ctx,
    )
    assert ctx.model_files.get("models.py") == 1


def test_python_ast_detects_pydantic_basemodel(tmp_path: Path):
    from blindspot.dependency_graph.extractors.base import ExtractionContext
    _write(tmp_path, "schemas.py", (
        "from pydantic import BaseModel\n"
        "class User(BaseModel):\n    name: str\n"
        "class Order(BaseModel):\n    id: int\n"
    ))
    ctx = ExtractionContext(repo_root=tmp_path, repo_files={"schemas.py"})
    PythonImportExtractor().extract(
        "schemas.py", (tmp_path / "schemas.py").read_text(), ctx,
    )
    assert ctx.model_files.get("schemas.py") == 2


def test_python_ast_falls_back_to_regex_on_syntax_error(tmp_path: Path):
    # Broken syntax — AST parse fails. We should still recover the import.
    _write(tmp_path, "broken.py", "from helper import foo\nclass Bad(:\n")
    _write(tmp_path, "helper.py", "")
    graph = DependencyGraphBuilder(include_tests=True).build(tmp_path)
    assert graph.nx_graph.has_edge("broken.py", "helper.py")


def test_python_ast_skips_non_local_inheritance(tmp_path: Path):
    # If the base class isn't from an in-repo import, no edge is added.
    _write(tmp_path, "main.py", (
        "from typing import Generic, TypeVar\n"
        "T = TypeVar('T')\n"
        "class Box(Generic[T]):\n    pass\n"
    ))
    graph = DependencyGraphBuilder(include_tests=True).build(tmp_path)
    # No in-repo edges — Generic comes from stdlib.
    assert list(graph.nx_graph.successors("main.py")) == []


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


def test_auto_detect_picks_src_when_present(tmp_path: Path):
    _write(tmp_path, "src/pkg/__init__.py", "")
    _write(tmp_path, "src/pkg/main.py", "")
    _write(tmp_path, "scripts/build.py", "")
    assert auto_detect_code_root(tmp_path) == "src"


def test_auto_detect_falls_back_when_no_known_root(tmp_path: Path):
    _write(tmp_path, "pkg/main.py", "")
    _write(tmp_path, "scripts/build.py", "")
    assert auto_detect_code_root(tmp_path) == ""


def test_builder_constrains_walk_to_code_root(tmp_path: Path):
    _write(tmp_path, "src/pkg/__init__.py", "")
    _write(tmp_path, "src/pkg/main.py", "from pkg.util import x\n")
    _write(tmp_path, "src/pkg/util.py", "")
    _write(tmp_path, "scripts/build.py", "from pkg.main import y\n")

    graph = DependencyGraphBuilder(code_root="src").build(tmp_path)
    nodes = set(graph.nx_graph.nodes())
    assert "src/pkg/main.py" in nodes
    assert "src/pkg/util.py" in nodes
    # scripts/ is OUTSIDE the code root → not a node.
    assert "scripts/build.py" not in nodes


def test_builder_excludes_tests_and_examples_by_default(tmp_path: Path):
    _write(tmp_path, "src/pkg/__init__.py", "")
    _write(tmp_path, "src/pkg/main.py", "")
    _write(tmp_path, "tests/test_main.py", "from pkg.main import x\n")
    _write(tmp_path, "examples/demo.py", "from pkg.main import y\n")
    _write(tmp_path, "docs/conf.py", "")

    # Default: include_tests=False → tests/examples/docs excluded.
    graph = DependencyGraphBuilder().build(tmp_path)
    nodes = set(graph.nx_graph.nodes())
    assert "src/pkg/main.py" in nodes
    assert "tests/test_main.py" not in nodes
    assert "examples/demo.py" not in nodes
    assert "docs/conf.py" not in nodes


def test_builder_includes_tests_when_opt_in(tmp_path: Path):
    _write(tmp_path, "pkg/main.py", "")
    _write(tmp_path, "tests/test_main.py", "from pkg.main import x\n")
    graph = DependencyGraphBuilder(include_tests=True).build(tmp_path)
    assert "tests/test_main.py" in set(graph.nx_graph.nodes())


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


