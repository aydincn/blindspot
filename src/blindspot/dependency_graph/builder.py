"""Walk a repo, run language extractors, build a DependencyGraph."""

from dataclasses import dataclass, field
from pathlib import Path

from blindspot.collector.filters import FileFilter
from blindspot.dependency_graph.extractors import DEFAULT_EXTRACTORS
from blindspot.dependency_graph.extractors.base import (
    ExtractionContext,
    ImportExtractor,
)
from blindspot.dependency_graph.llm_fallback import LLMImportExtractor
from blindspot.dependency_graph.models import DependencyGraph

DEFAULT_MAX_FILE_BYTES = 1_048_576  # skip files larger than 1 MB


@dataclass
class DependencyGraphBuilder:
    extractors: dict[str, ImportExtractor] = field(
        default_factory=lambda: dict(DEFAULT_EXTRACTORS)
    )
    llm_fallback: LLMImportExtractor | None = None
    file_filter: FileFilter | None = None
    max_file_bytes: int = DEFAULT_MAX_FILE_BYTES

    def build(self, repo_root: Path) -> DependencyGraph:
        repo_root = repo_root.resolve()
        ff = self.file_filter or FileFilter.from_repo(repo_root)

        # 1. Walk the filesystem, collecting candidate files.
        repo_files: set[str] = set()
        for fs_path in repo_root.rglob("*"):
            if not fs_path.is_file():
                continue
            try:
                rel = fs_path.relative_to(repo_root).as_posix()
            except ValueError:
                continue
            if ff.should_skip(rel):
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
            # LLM fallback: if static returned nothing but content looks like
            # it has imports, ask the LLM. Only runs when configured.
            if self.llm_fallback is not None:
                imports = self.llm_fallback.maybe_extract(rel, content, ctx, imports)
            for target in imports:
                graph.add_dependency(rel, target)

        return graph

    def _extractor_for(self, rel_path: str) -> ImportExtractor | None:
        basename = rel_path.rsplit("/", 1)[-1]
        if "." not in basename:
            return None
        ext = "." + basename.rsplit(".", 1)[1].lower()
        return self.extractors.get(ext)

    @staticmethod
    def _read(path: Path) -> str | None:
        try:
            return path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return None


__all__ = ["DependencyGraphBuilder"]
