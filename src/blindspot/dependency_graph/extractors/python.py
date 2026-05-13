"""Python import extractor.

Resolves `import` and `from … import` statements to repo-relative file
paths. Unresolvable imports (stdlib, third-party packages) are silently
dropped — they aren't part of the in-repo dependency graph.
"""

import re

from blindspot.dependency_graph.extractors.base import ExtractionContext

_IMPORT_RE = re.compile(
    r"""^\s*
    (?:
        from\s+(?P<from>[.\w]+)\s+import\b
        |
        import\s+(?P<imp>[.\w][\w.]*(?:\s*,\s*[\w.]+)*)
    )
    """,
    re.VERBOSE | re.MULTILINE,
)


class PythonImportExtractor:
    extensions: tuple[str, ...] = (".py",)
    needs_namespace_index: bool = False

    def prime_namespace_index(self, file_path: str, content: str, ctx: ExtractionContext) -> None:
        return

    def extract(self, file_path: str, content: str, ctx: ExtractionContext) -> list[str]:
        results: set[str] = set()
        caller_pkg = self._caller_package(file_path)

        for match in _IMPORT_RE.finditer(content):
            from_mod = match.group("from")
            if from_mod is not None:
                resolved = self._resolve(from_mod, caller_pkg, ctx)
                if resolved:
                    results.add(resolved)
                continue
            imp_clause = match.group("imp")
            if imp_clause is None:
                continue
            # `import a, b.c, d`
            for raw in imp_clause.split(","):
                module = raw.strip().split(" as ")[0].strip()
                if not module:
                    continue
                resolved = self._resolve(module, caller_pkg, ctx)
                if resolved:
                    results.add(resolved)
        return sorted(results)

    @staticmethod
    def _caller_package(file_path: str) -> list[str]:
        parts = file_path.split("/")
        if parts[-1].endswith(".py"):
            parts = parts[:-1]
        return parts

    # Common Python source-root prefixes — covers `src/` layout (modern
    # PEP 621) and root layout (older). Order matters: try root before src.
    _SOURCE_ROOTS: tuple[str, ...] = ("", "src/", "lib/", "python/")

    @classmethod
    def _resolve(cls, module: str, caller_pkg: list[str], ctx: ExtractionContext) -> str | None:
        if not module:
            return None

        # Handle relative imports: leading dots step up the package tree.
        if module.startswith("."):
            level = len(module) - len(module.lstrip("."))
            remainder = module[level:]
            base = caller_pkg[: max(0, len(caller_pkg) - (level - 1))]
            if remainder:
                base = base + remainder.split(".")
            module_parts = base
            # Relative imports are anchored at caller's location, no root sweep.
            return cls._first_match(module_parts, [""], ctx)

        module_parts = module.split(".")
        if not module_parts:
            return None
        return cls._first_match(module_parts, cls._SOURCE_ROOTS, ctx)

    @staticmethod
    def _first_match(
        module_parts: list[str], roots: tuple[str, ...] | list[str], ctx: ExtractionContext
    ) -> str | None:
        # Try <module>.py then <module>/__init__.py, peeling trailing names off.
        # (When `from foo.bar import baz`, baz might be a symbol within bar.py
        # rather than a separate file — peel "baz" first, then try "bar".)
        for root in roots:
            for end in range(len(module_parts), 0, -1):
                base = root + "/".join(module_parts[:end])
                for candidate in (f"{base}.py", f"{base}/__init__.py"):
                    if candidate in ctx.repo_files:
                        return candidate
        return None


__all__ = ["PythonImportExtractor"]
