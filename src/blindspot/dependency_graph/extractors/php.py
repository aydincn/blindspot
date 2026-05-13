"""PHP include / require / use extractor.

Two idioms:

- File-path includes: `require "../foo.php";`, `include_once 'foo.php';`.
  Resolved like JS/TS — relative to caller.
- Namespace usage: `use App\\Services\\Foo;`. Resolved via PSR-4 best-effort
  by looking for a file whose path ends with `Services/Foo.php`.
"""

import re

from blindspot.dependency_graph.extractors.base import ExtractionContext

_PATH_INCLUDE_RE = re.compile(
    r"""^\s*
        (?:require|include)(?:_once)?
        \s*\(?
        ["']([^"']+)["']
    """,
    re.MULTILINE | re.VERBOSE,
)
_USE_RE = re.compile(r"^\s*use\s+(?:function\s+|const\s+)?([\w\\]+)", re.MULTILINE)


class PhpImportExtractor:
    extensions: tuple[str, ...] = (".php",)
    needs_namespace_index: bool = False

    def prime_namespace_index(self, file_path: str, content: str, ctx: ExtractionContext) -> None:
        return

    def extract(self, file_path: str, content: str, ctx: ExtractionContext) -> list[str]:
        results: set[str] = set()
        caller_dir = file_path.rsplit("/", 1)[0] if "/" in file_path else ""

        for match in _PATH_INCLUDE_RE.finditer(content):
            spec = match.group(1)
            resolved = self._resolve_path(spec, caller_dir, ctx)
            if resolved:
                results.add(resolved)

        for match in _USE_RE.finditer(content):
            spec = match.group(1)
            resolved = self._resolve_namespace(spec, ctx)
            if resolved:
                results.add(resolved)
        return sorted(results)

    @staticmethod
    def _resolve_path(spec: str, caller_dir: str, ctx: ExtractionContext) -> str | None:
        if not spec.endswith(".php"):
            spec_with_ext = f"{spec}.php"
        else:
            spec_with_ext = spec

        # Build a list of candidate paths to try, in order of preference.
        candidates: list[str] = []
        if spec.startswith("./") or spec.startswith("../"):
            candidates.append(_norm_join(caller_dir, spec_with_ext))
        elif spec.startswith("/"):
            candidates.append(spec_with_ext.lstrip("/"))
        else:
            # PHP `require 'foo.php'` (no leading ./) is ambiguous: it can
            # be caller-relative, include_path-relative, or absolute.
            # Try caller dir first (most common), then root.
            if caller_dir:
                candidates.append(_norm_join(caller_dir, spec_with_ext))
            candidates.append(spec_with_ext)

        for c in candidates:
            if c in ctx.repo_files:
                return c
        return None

    @staticmethod
    def _resolve_namespace(spec: str, ctx: ExtractionContext) -> str | None:
        parts = [p for p in spec.split("\\") if p]
        if not parts:
            return None
        # PSR-4: namespace maps to directory. Suffix-match.
        suffix = "/".join(parts) + ".php"
        for f in ctx.repo_files:
            if f.endswith(suffix) or f.endswith("/" + suffix):
                return f
        return None


def _norm_join(base: str, path: str) -> str:
    parts = [p for p in base.split("/") if p] if base else []
    for segment in path.split("/"):
        if segment in ("", "."):
            continue
        if segment == "..":
            if parts:
                parts.pop()
            continue
        parts.append(segment)
    return "/".join(parts)


__all__ = ["PhpImportExtractor"]
