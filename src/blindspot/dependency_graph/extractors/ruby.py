"""Ruby require / require_relative extractor.

Ruby uses three module-loading idioms:
- `require_relative "foo/bar"` — relative to current file
- `require "foo/bar"` — searched on $LOAD_PATH (typically `lib/`)
- `autoload :Foo, "foo/bar"` — lazy load

System gems (`require "json"`, `require "rails"`) are silently skipped.
"""

import re

from blindspot.dependency_graph.extractors.base import ExtractionContext

_REQ_RE = re.compile(
    r"""^\s*
        (?:
            require_relative\s+["']([^"']+)["']
            |require\s+["']([^"']+)["']
            |autoload\s+:[A-Z]\w*\s*,\s*["']([^"']+)["']
        )
    """,
    re.MULTILINE | re.VERBOSE,
)


class RubyImportExtractor:
    extensions: tuple[str, ...] = (".rb",)
    needs_namespace_index: bool = False

    def prime_namespace_index(self, file_path: str, content: str, ctx: ExtractionContext) -> None:
        return

    def extract(self, file_path: str, content: str, ctx: ExtractionContext) -> list[str]:
        results: set[str] = set()
        caller_dir = file_path.rsplit("/", 1)[0] if "/" in file_path else ""

        for match in _REQ_RE.finditer(content):
            rel, abs_, auto = match.groups()
            if rel is not None:
                target = self._resolve_relative(rel, caller_dir, ctx)
            elif abs_ is not None:
                target = self._resolve_absolute(abs_, ctx)
            else:
                target = self._resolve_absolute(auto, ctx)
            if target:
                results.add(target)
        return sorted(results)

    @staticmethod
    def _resolve_relative(spec: str, caller_dir: str, ctx: ExtractionContext) -> str | None:
        spec = spec.removesuffix(".rb")
        base = f"{caller_dir}/{spec}" if caller_dir else spec
        candidates = (
            f"{base}.rb",
            f"{base}/index.rb",
        )
        for c in candidates:
            if c in ctx.repo_files:
                return c
        return None

    @staticmethod
    def _resolve_absolute(spec: str, ctx: ExtractionContext) -> str | None:
        spec = spec.removesuffix(".rb")
        for root in ("lib/", "app/", ""):
            cand = f"{root}{spec}.rb"
            if cand in ctx.repo_files:
                return cand
        return None


__all__ = ["RubyImportExtractor"]
