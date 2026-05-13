"""Go import extractor.

Resolves imports against `go.mod`'s module path. Falls back to suffix
matching the import path against repo directories.

Imports can be single or grouped:

    import "foo/bar"

    import (
        "foo/bar"
        "baz/qux"
    )
"""

import re

from blindspot.dependency_graph.extractors.base import ExtractionContext

_SINGLE_IMPORT_RE = re.compile(r'^\s*import\s+(?:(\w+)\s+)?"([^"]+)"', re.MULTILINE)
_GROUP_IMPORT_RE = re.compile(r"import\s*\(([^)]*)\)", re.MULTILINE | re.DOTALL)
_GROUP_LINE_RE = re.compile(r'(?:(\w+)\s+)?"([^"]+)"')


def _read_module_prefix(ctx: ExtractionContext) -> str:
    """Read `module foo/bar` from go.mod if present (cached on ctx)."""
    cache_key = "__go_module_prefix__"
    if cache_key in ctx.namespace_index:
        cached = ctx.namespace_index[cache_key]
        return cached[0] if cached else ""
    go_mod = ctx.repo_root / "go.mod"
    prefix = ""
    if go_mod.is_file():
        try:
            for line in go_mod.read_text(encoding="utf-8", errors="ignore").splitlines():
                if line.startswith("module "):
                    prefix = line.split(None, 1)[1].strip()
                    break
        except OSError:
            pass
    ctx.namespace_index[cache_key] = [prefix]
    return prefix


class GoImportExtractor:
    extensions: tuple[str, ...] = (".go",)
    needs_namespace_index: bool = False

    def prime_namespace_index(
        self, file_path: str, content: str, ctx: ExtractionContext
    ) -> None:
        return

    def extract(
        self, file_path: str, content: str, ctx: ExtractionContext
    ) -> list[str]:
        module_prefix = _read_module_prefix(ctx)
        specs: list[str] = []
        for match in _SINGLE_IMPORT_RE.finditer(content):
            specs.append(match.group(2))
        for group in _GROUP_IMPORT_RE.finditer(content):
            block = group.group(1)
            for line in _GROUP_LINE_RE.finditer(block):
                specs.append(line.group(2))

        results: set[str] = set()
        for spec in specs:
            resolved = self._resolve(spec, module_prefix, ctx)
            if resolved:
                results.add(resolved)
        return sorted(results)

    @staticmethod
    def _resolve(
        spec: str, module_prefix: str, ctx: ExtractionContext
    ) -> str | None:
        if module_prefix and spec.startswith(module_prefix + "/"):
            rel = spec[len(module_prefix) + 1 :]
        elif module_prefix and spec == module_prefix:
            rel = ""
        elif spec.startswith("./") or spec.startswith("../"):
            rel = spec
        else:
            # External package — out of scope.
            return None

        # Each Go package is a directory; any .go file in that dir counts
        # as the dependency (we link to the first non-test file found).
        rel = rel.strip("/")
        candidates = sorted(
            f for f in ctx.repo_files
            if f.startswith(rel + "/") and f.endswith(".go")
            and not f.endswith("_test.go")
        )
        return candidates[0] if candidates else None


__all__ = ["GoImportExtractor"]
