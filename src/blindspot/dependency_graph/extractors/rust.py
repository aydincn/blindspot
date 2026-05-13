"""Rust import extractor.

Rust modules are explicit (`mod foo;` includes `foo.rs` or `foo/mod.rs`)
and imports use `use crate::foo::bar` paths. We resolve both:

- `mod foo;` from `pkg/lib.rs` → `pkg/foo.rs` or `pkg/foo/mod.rs`
- `use crate::foo::bar` → `src/foo/bar.rs` (typical Cargo layout) or
  `src/foo/bar/mod.rs`; `super::` and `self::` resolved relative to caller.
"""

import re

from blindspot.dependency_graph.extractors.base import ExtractionContext

_MOD_RE = re.compile(r"^\s*(?:pub\s+)?mod\s+(\w+)\s*;", re.MULTILINE)
_USE_RE = re.compile(r"^\s*(?:pub\s+)?use\s+([\w:{}\s,*]+);", re.MULTILINE)


class RustImportExtractor:
    extensions: tuple[str, ...] = (".rs",)
    needs_namespace_index: bool = False

    def prime_namespace_index(self, file_path: str, content: str, ctx: ExtractionContext) -> None:
        return

    def extract(self, file_path: str, content: str, ctx: ExtractionContext) -> list[str]:
        results: set[str] = set()
        caller_dir = file_path.rsplit("/", 1)[0] if "/" in file_path else ""

        # `mod foo;` resolves to a sibling file/directory.
        for match in _MOD_RE.finditer(content):
            name = match.group(1)
            for candidate in self._mod_candidates(caller_dir, name):
                if candidate in ctx.repo_files:
                    results.add(candidate)
                    break

        # `use a::b::c;` paths.
        for match in _USE_RE.finditer(content):
            clause = match.group(1)
            # Strip grouping braces and parse comma-separated parts.
            for path in _split_use_clause(clause):
                resolved = self._resolve_path(path, caller_dir, ctx)
                if resolved:
                    results.add(resolved)
        return sorted(results)

    @staticmethod
    def _mod_candidates(caller_dir: str, name: str) -> list[str]:
        base = f"{caller_dir}/{name}" if caller_dir else name
        return [f"{base}.rs", f"{base}/mod.rs"]

    @staticmethod
    def _resolve_path(path: str, caller_dir: str, ctx: ExtractionContext) -> str | None:
        parts = [p for p in path.split("::") if p and p != "{}"]
        if not parts:
            return None

        # Determine source root: typical Cargo layout `src/`, also `lib/`.
        root_candidates = ("src/", "")

        if parts[0] == "crate":
            parts = parts[1:]
        elif parts[0] == "self":
            parts = parts[1:]
            root_candidates = (caller_dir + "/" if caller_dir else "",)
        elif parts[0] == "super":
            depth = 0
            while parts and parts[0] == "super":
                depth += 1
                parts = parts[1:]
            cur = caller_dir.split("/") if caller_dir else []
            base_parts = cur[: max(0, len(cur) - depth)]
            root = "/".join(base_parts) + "/" if base_parts else ""
            root_candidates = (root,)
        elif parts[0] in ("std", "core", "alloc"):
            return None  # stdlib

        if not parts:
            return None

        # Try peeling trailing symbols (similar to Python): `use foo::bar::Baz`
        # could be a symbol Baz in `foo/bar.rs` rather than file `foo/bar/Baz.rs`.
        for root in root_candidates:
            for end in range(len(parts), 0, -1):
                base = root + "/".join(parts[:end])
                for cand in (f"{base}.rs", f"{base}/mod.rs"):
                    if cand in ctx.repo_files:
                        return cand
        return None


def _split_use_clause(clause: str) -> list[str]:
    """`use a::b::{c, d::e};` -> ['a::b::c', 'a::b::d::e']."""
    clause = clause.strip().rstrip(";").strip()
    # Strip `as` aliases: `as Foo`
    if " as " in clause:
        clause = clause.split(" as ", 1)[0]
    if "{" not in clause:
        return [clause.strip()]
    prefix, _, rest = clause.partition("{")
    inner, _, _ = rest.rpartition("}")
    prefix = prefix.rstrip(":").rstrip()
    return [
        f"{prefix}::{piece.strip().split(' as ')[0].strip()}"
        for piece in inner.split(",")
        if piece.strip()
    ]


__all__ = ["RustImportExtractor"]
