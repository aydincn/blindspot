"""Kotlin import extractor.

Mirrors the Java strategy: package declaration in pass 1, imports
resolved against the namespace index in pass 2. Top-level functions
and properties can be imported directly, so we also index file-level
member symbols when found (best-effort, regex-based).
"""

import re

from blindspot.dependency_graph.extractors.base import ExtractionContext

_PACKAGE_RE = re.compile(r"^\s*package\s+([\w.]+)", re.MULTILINE)
_IMPORT_RE = re.compile(r"^\s*import\s+([\w.]+(?:\.\*)?)", re.MULTILINE)


class KotlinImportExtractor:
    extensions: tuple[str, ...] = (".kt", ".kts")
    needs_namespace_index: bool = True

    def prime_namespace_index(
        self, file_path: str, content: str, ctx: ExtractionContext
    ) -> None:
        idx = ctx.namespace_index
        match = _PACKAGE_RE.search(content)
        pkg = match.group(1) if match else ""
        idx.setdefault(pkg, []).append(file_path)
        basename = file_path.rsplit("/", 1)[-1]
        for suffix in (".kt", ".kts"):
            if basename.endswith(suffix):
                stem = basename[: -len(suffix)]
                fqn = f"{pkg}.{stem}" if pkg else stem
                idx.setdefault(fqn, []).append(file_path)
                break

    def extract(
        self, file_path: str, content: str, ctx: ExtractionContext
    ) -> list[str]:
        idx = ctx.namespace_index
        if not idx:
            return []

        results: set[str] = set()
        for match in _IMPORT_RE.finditer(content):
            spec = match.group(1)
            if spec.endswith(".*"):
                ns = spec[:-2]
                for f in idx.get(ns, []):
                    if f != file_path:
                        results.add(f)
                continue
            for f in idx.get(spec, []):
                if f != file_path:
                    results.add(f)
            parent = ".".join(spec.split(".")[:-1])
            for f in idx.get(parent, []):
                if f != file_path:
                    results.add(f)
        return sorted(results)


__all__ = ["KotlinImportExtractor"]
