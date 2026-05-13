"""C/C++ include extractor.

Only `#include "..."` (user includes) and `#include <X>` where X resolves
to a repo path are considered. System headers (`<vector>`, `<stdio.h>`)
are skipped.
"""

import re

from blindspot.dependency_graph.extractors.base import ExtractionContext

_INCLUDE_RE = re.compile(r'^\s*#\s*include\s*(["<])([^">]+)([">])', re.MULTILINE)


class CppImportExtractor:
    extensions: tuple[str, ...] = (
        ".c", ".cc", ".cpp", ".cxx", ".h", ".hpp", ".hxx",
    )
    needs_namespace_index: bool = False

    def prime_namespace_index(self, file_path: str, content: str, ctx: ExtractionContext) -> None:
        return

    def extract(self, file_path: str, content: str, ctx: ExtractionContext) -> list[str]:
        results: set[str] = set()
        caller_dir = file_path.rsplit("/", 1)[0] if "/" in file_path else ""

        for match in _INCLUDE_RE.finditer(content):
            open_q = match.group(1)
            spec = match.group(2)
            target = self._resolve(open_q, spec, caller_dir, ctx)
            if target:
                results.add(target)
        return sorted(results)

    @staticmethod
    def _resolve(
        open_q: str, spec: str, caller_dir: str, ctx: ExtractionContext
    ) -> str | None:
        candidates: list[str] = []
        if open_q == '"':
            # User include: try relative to caller first.
            if caller_dir:
                candidates.append(_join(caller_dir, spec))
            candidates.append(spec)
        else:
            # System include: only match if path exists verbatim in repo
            # (often `<MyLib/Foo.h>` resolves under `include/`).
            candidates.append(spec)
            candidates.append(_join("include", spec))
            candidates.append(_join("src", spec))

        for c in candidates:
            if c in ctx.repo_files:
                return c
        return None


def _join(base: str, path: str) -> str:
    parts: list[str] = []
    if base:
        parts.extend(p for p in base.split("/") if p)
    for segment in path.split("/"):
        if segment in ("", "."):
            continue
        if segment == "..":
            if parts:
                parts.pop()
            continue
        parts.append(segment)
    return "/".join(parts)


__all__ = ["CppImportExtractor"]
