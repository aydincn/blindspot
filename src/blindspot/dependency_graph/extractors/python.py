"""AST-based Python import + structural-class extractor.

Replaces the earlier regex-only implementation. Three pieces:

1. **Imports** — `import` and `from … import` statements resolve to
   repo-relative paths via `_resolve`. Same coverage as the old regex,
   but properly: aliased imports, parenthesised lists, relative imports.

2. **Class inheritance** — `class Foo(Bar)` records `Bar` as a dependency
   edge target. `Bar` must be in scope via an import in the same file;
   we map `Bar` back through the import table to the defining file.
   Inheritance is structurally stronger than a plain import — the
   subclass file is genuinely *bound* to the base file. We emit it as
   an extra edge so the graph reflects that.

3. **Model detection** — flag files that contain at least one class
   that looks like a "central model": dataclass-decorated, or a
   subclass of `BaseModel` (pydantic), `Struct` (msgspec), `attrs.define`.
   The count is stashed on `ExtractionContext.model_files` for the
   report layer to surface.

The previous regex fallback is preserved as `_extract_imports_regex` for
files that fail to parse (Python 2 leftovers, partial Python files).
"""

import ast
import re

from blindspot.dependency_graph.extractors.base import ExtractionContext

# Class names that signal "this class is a model/schema/struct."
_MODEL_BASE_NAMES = frozenset({
    "BaseModel",       # pydantic
    "Struct",          # msgspec
    "Schema",          # marshmallow, drf-spectacular
    "TypedDict",       # typing
    "NamedTuple",      # typing
})

# Decorators that mark a class as a data model.
_MODEL_DECORATOR_NAMES = frozenset({
    "dataclass",       # stdlib
    "define",          # attrs
    "frozen",          # attrs
    "mutable",         # attrs
    "attrs",           # legacy attrs
    "attr.s",          # legacy attrs
    "model",           # pydantic v2 (less common)
})

# Fallback regex for files we can't parse. Same shape as the pre-AST
# implementation, only used after `ast.parse` raises.
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

    def prime_namespace_index(
        self, file_path: str, content: str, ctx: ExtractionContext
    ) -> None:
        return

    def extract(
        self, file_path: str, content: str, ctx: ExtractionContext
    ) -> list[str]:
        caller_pkg = self._caller_package(file_path)
        try:
            tree = ast.parse(content)
        except SyntaxError:
            # Fall back to regex when AST parsing fails. Inheritance
            # edges and model detection are skipped for these files —
            # better to keep a partial result than nothing.
            return self._extract_imports_regex(content, caller_pkg, ctx)

        resolved: set[str] = set()

        # Walk imports, recording both resolved files and the in-scope
        # local-name → target-file map. The map lets us resolve class
        # bases (`class Foo(Bar)`) back through the imports.
        local_name_to_file: dict[str, str] = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                # `import a.b.c` or `import a.b as c`
                for alias in node.names:
                    target = self._resolve(alias.name, caller_pkg, ctx)
                    if target:
                        resolved.add(target)
                        local = alias.asname or alias.name.split(".")[0]
                        local_name_to_file[local] = target
            elif isinstance(node, ast.ImportFrom):
                # `from a.b import c, d as e` or `from . import x`
                if node.module is None and node.level == 0:
                    continue
                module = ("." * node.level) + (node.module or "")
                module_target = self._resolve(module, caller_pkg, ctx)
                if module_target:
                    resolved.add(module_target)
                # Map each imported name to either the submodule file
                # (if `from pkg import sub` where sub.py exists) or the
                # parent module file (if `from mod import symbol`).
                for alias in node.names:
                    if alias.name == "*":
                        continue
                    submodule = (
                        module + "." + alias.name if module and not module.endswith(".") else
                        module + alias.name
                    )
                    sub_target = self._resolve(submodule, caller_pkg, ctx)
                    final_target = sub_target or module_target
                    if final_target:
                        local = alias.asname or alias.name
                        local_name_to_file[local] = final_target
                        if sub_target:
                            resolved.add(sub_target)

        # Inheritance edges + model detection.
        model_class_count = 0
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            if self._is_model_class(node):
                model_class_count += 1
            for base in node.bases:
                base_name = self._base_name(base)
                if base_name is None:
                    continue
                target = local_name_to_file.get(base_name)
                if target and target != file_path:
                    resolved.add(target)

        if model_class_count > 0:
            ctx.model_files[file_path] = (
                ctx.model_files.get(file_path, 0) + model_class_count
            )

        return sorted(resolved)

    # ------------------------------------------------------------------
    # Helpers

    def _extract_imports_regex(
        self, content: str, caller_pkg: list[str], ctx: ExtractionContext
    ) -> list[str]:
        """Regex fallback used only when AST parsing fails."""
        results: set[str] = set()
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

    @staticmethod
    def _base_name(node: ast.expr) -> str | None:
        """Extract the leftmost name from a class base expression.

        For `class Foo(Bar):` → "Bar".
        For `class Foo(mod.Bar):` → "mod" (so we can resolve via imports).
        For complex expressions (`Generic[T]`, calls) → None.
        """
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            inner = node
            while isinstance(inner, ast.Attribute):
                inner = inner.value
            if isinstance(inner, ast.Name):
                return inner.id
        return None

    @staticmethod
    def _is_model_class(node: ast.ClassDef) -> bool:
        # Decorator-based detection (@dataclass, @attrs.define, etc.).
        for dec in node.decorator_list:
            name = PythonImportExtractor._decorator_name(dec)
            if name and name in _MODEL_DECORATOR_NAMES:
                return True
        # Base-class detection (BaseModel, Struct, Schema, TypedDict).
        for base in node.bases:
            base_name = PythonImportExtractor._base_name(base)
            if base_name and base_name in _MODEL_BASE_NAMES:
                return True
        return False

    @staticmethod
    def _decorator_name(node: ast.expr) -> str | None:
        if isinstance(node, ast.Call):
            node = node.func
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            # @attr.s, @dataclasses.dataclass — take the rightmost name.
            return node.attr
        return None

    # ------------------------------------------------------------------
    # Module-to-file resolution (preserved from the regex implementation).

    # Common Python source-root prefixes — covers `src/` layout (modern
    # PEP 621) and root layout (older). Order matters: try root before src.
    _SOURCE_ROOTS: tuple[str, ...] = ("", "src/", "lib/", "python/")

    @classmethod
    def _resolve(
        cls, module: str, caller_pkg: list[str], ctx: ExtractionContext
    ) -> str | None:
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
            return cls._first_match(module_parts, [""], ctx)

        module_parts = module.split(".")
        if not module_parts:
            return None
        return cls._first_match(module_parts, cls._SOURCE_ROOTS, ctx)

    @staticmethod
    def _first_match(
        module_parts: list[str],
        roots: tuple[str, ...] | list[str],
        ctx: ExtractionContext,
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
