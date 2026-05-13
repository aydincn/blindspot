"""JavaScript / TypeScript import extractor.

Handles ES module imports (`import X from "..."`, `import "..."`,
`import type X from "..."`, dynamic `import("...")`), CommonJS require,
and TypeScript `export ... from "..."` re-exports.

Resolves only repo-relative imports (paths starting with `.` or `/`).
External package imports (`import x from 'react'`) are out of scope —
they don't form in-repo dependency edges.
"""

import re

from blindspot.dependency_graph.extractors.base import ExtractionContext

# Catches: import x from "y", import { x } from "y", import "y",
# import * as x from "y", import type x from "y", export ... from "y".
_STATIC_IMPORT_RE = re.compile(
    r"""
    (?:^|[\s;])
    (?:import\s+(?:type\s+)?(?:[^\"']+\s+from\s+)?
       |export\s+(?:\*|\{[^}]*\})\s+from\s+
       |import\s*\(
       |require\s*\(
    )
    ["']([^"']+)["']
    """,
    re.VERBOSE,
)

_RESOLVE_EXTS = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs")


class JavaScriptImportExtractor:
    extensions: tuple[str, ...] = (
        ".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx",
    )
    needs_namespace_index: bool = False

    def prime_namespace_index(self, file_path: str, content: str, ctx: ExtractionContext) -> None:
        return

    def extract(self, file_path: str, content: str, ctx: ExtractionContext) -> list[str]:
        results: set[str] = set()
        caller_dir = file_path.rsplit("/", 1)[0] if "/" in file_path else ""

        for match in _STATIC_IMPORT_RE.finditer(content):
            spec = match.group(1)
            if not spec:
                continue
            if not (spec.startswith(".") or spec.startswith("/")):
                continue  # external package — out of scope
            resolved = self._resolve(spec, caller_dir, ctx)
            if resolved:
                results.add(resolved)
        return sorted(results)

    @staticmethod
    def _resolve(spec: str, caller_dir: str, ctx: ExtractionContext) -> str | None:
        # Join with caller dir; normalize ../ and ./
        target = spec
        if spec.startswith("./") or spec.startswith("../"):
            target = caller_dir + "/" + spec if caller_dir else spec
        target = _normalize(target)

        # Try exact, then with each known extension, then /index variants.
        candidates: list[str] = []
        if "." in target.rsplit("/", 1)[-1]:
            candidates.append(target)
        else:
            for ext in _RESOLVE_EXTS:
                candidates.append(f"{target}{ext}")
            for ext in _RESOLVE_EXTS:
                candidates.append(f"{target}/index{ext}")

        for c in candidates:
            if c in ctx.repo_files:
                return c
        return None


def _normalize(path: str) -> str:
    parts: list[str] = []
    for segment in path.split("/"):
        if segment in ("", "."):
            continue
        if segment == "..":
            if parts:
                parts.pop()
            continue
        parts.append(segment)
    return "/".join(parts)


__all__ = ["JavaScriptImportExtractor"]
