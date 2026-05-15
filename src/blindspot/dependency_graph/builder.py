"""Walk a repo, run language extractors, build a DependencyGraph."""

from dataclasses import dataclass, field
from pathlib import Path

from blindspot.collector.filters import FileFilter
from blindspot.dependency_graph.extractors import DEFAULT_EXTRACTORS
from blindspot.dependency_graph.extractors.base import (
    ExtractionContext,
    ImportExtractor,
)
from blindspot.dependency_graph.models import DependencyGraph

DEFAULT_MAX_FILE_BYTES = 1_048_576  # skip files larger than 1 MB
AUTO_CODE_ROOT_CANDIDATES: tuple[str, ...] = ("src", "lib", "app")
# Directories that almost always pollute the architectural view if they
# end up as graph nodes. We never put their files in the graph unless the
# user explicitly opts in via `include_tests=True`. Ownership/decay
# analysis still considers these — only the structural dependency graph
# filters them out.
DEFAULT_TEST_EXAMPLE_DIRS: tuple[str, ...] = (
    "tests", "test", "__tests__",
    "examples", "example", "samples",
    "docs", "doc",
    "benchmarks", "benchmark",
)


def auto_detect_code_root(repo_root: Path) -> str:
    """Pick the most likely source-code root for this repo.

    Returns a repo-relative directory string (empty string for repo root).
    `src/` is preferred when present and non-empty, then `lib/`, then `app/`.
    Falls back to the repo root.
    """
    for cand in AUTO_CODE_ROOT_CANDIDATES:
        candidate_dir = repo_root / cand
        if candidate_dir.is_dir() and any(candidate_dir.rglob("*.*")):
            return cand
    return ""


@dataclass
class DependencyGraphBuilder:
    extractors: dict[str, ImportExtractor] = field(
        default_factory=lambda: dict(DEFAULT_EXTRACTORS)
    )
    file_filter: FileFilter | None = None
    max_file_bytes: int = DEFAULT_MAX_FILE_BYTES
    code_root: str = ""
    """Repo-relative subdirectory to constrain the graph to. Empty string
    means 'whole repo' (the default — preserves library/programmatic
    callers' behaviour). The CLI auto-detects (`src/` → `lib/` → `app/`)
    and passes the result; programmatic callers can do the same via
    `auto_detect_code_root(repo_root)` if they want the same default."""
    include_tests: bool = False
    """If False (default), files under `tests/`, `examples/`, `docs/`,
    etc. are excluded from the dependency graph even when they live under
    the code root. They still count for ownership and decay analysis —
    this filter only affects the structural view."""

    def build(self, repo_root: Path) -> DependencyGraph:
        repo_root = repo_root.resolve()
        ff = self.file_filter or FileFilter.from_repo(repo_root)

        # Resolve which sub-tree the graph covers.
        effective_root = self.code_root.strip("/")

        if effective_root:
            walk_base = repo_root / effective_root
            code_root_prefix = effective_root + "/"
        else:
            walk_base = repo_root
            code_root_prefix = ""

        if not walk_base.is_dir():
            # Configured code root does not exist on disk → empty graph.
            return DependencyGraph()

        # 1. Walk the filesystem, collecting candidate files.
        repo_files: set[str] = set()
        for fs_path in walk_base.rglob("*"):
            if not fs_path.is_file():
                continue
            try:
                rel = fs_path.relative_to(repo_root).as_posix()
            except ValueError:
                continue
            if ff.should_skip(rel):
                continue
            if not self.include_tests and self._is_test_or_example(rel, code_root_prefix):
                continue
            ext = "." + rel.rsplit(".", 1)[1].lower() if "." in rel.rsplit("/", 1)[-1] else ""
            if ext not in self.extractors:
                continue
            try:
                size = fs_path.stat().st_size
            except OSError:
                continue
            if size > self.max_file_bytes:
                continue
            repo_files.add(rel)

        ctx = ExtractionContext(repo_root=repo_root, repo_files=repo_files)

        # 2. First pass: prime namespace indices for languages that need them.
        priming_needed = any(
            ext.needs_namespace_index for ext in self.extractors.values()
        )
        if priming_needed:
            for rel in repo_files:
                extractor = self._extractor_for(rel)
                if extractor is None or not extractor.needs_namespace_index:
                    continue
                content = self._read(repo_root / rel)
                if content is None:
                    continue
                extractor.prime_namespace_index(rel, content, ctx)

        # 3. Second pass: extract dependencies and build graph.
        graph = DependencyGraph()
        for rel in repo_files:
            graph.ensure_node(rel)
            extractor = self._extractor_for(rel)
            if extractor is None:
                continue
            content = self._read(repo_root / rel)
            if content is None:
                continue
            try:
                imports = extractor.extract(rel, content, ctx)
            except Exception:
                imports = []
            for target in imports:
                graph.add_dependency(rel, target)

        # Promote AST-discovered model annotations onto the graph so the
        # report layer can read them without holding a reference to the
        # extraction context.
        graph.model_files = dict(ctx.model_files)
        return graph

    def _extractor_for(self, rel_path: str) -> ImportExtractor | None:
        basename = rel_path.rsplit("/", 1)[-1]
        if "." not in basename:
            return None
        ext = "." + basename.rsplit(".", 1)[1].lower()
        return self.extractors.get(ext)

    @staticmethod
    def _is_test_or_example(rel: str, code_root_prefix: str) -> bool:
        # Trim the code-root prefix so `src/tests/utils.py` is also caught:
        # the question is whether the path, relative to the code root,
        # starts inside a test/example/docs directory at any depth.
        path = rel[len(code_root_prefix):] if rel.startswith(code_root_prefix) else rel
        segments = path.split("/")
        return any(seg in DEFAULT_TEST_EXAMPLE_DIRS for seg in segments[:-1])

    @staticmethod
    def _read(path: Path) -> str | None:
        try:
            return path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return None


__all__ = [
    "AUTO_CODE_ROOT_CANDIDATES",
    "DEFAULT_TEST_EXAMPLE_DIRS",
    "DependencyGraphBuilder",
    "auto_detect_code_root",
]
