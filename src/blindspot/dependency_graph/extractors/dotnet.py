""".NET (C# / F#) import extractor — two-pass via namespace index.

Pass 1: scan every .cs/.fs file for `namespace X.Y { ... }` or
file-scoped `namespace X.Y;` declarations, build a map
`namespace_path -> [files]`.

Pass 2: for each file, scan `using X.Y;` (or `open X.Y` in F#) and
emit edges to every file that declares X.Y or a sub-namespace.

C# `using static X.Y` and aliased `using foo = X.Y;` are handled by
extracting only the right-hand-side namespace path.
"""

import re

from blindspot.dependency_graph.extractors.base import ExtractionContext

_CS_NAMESPACE_BLOCK = re.compile(r"^\s*namespace\s+([\w.]+)\s*\{", re.MULTILINE)
_CS_NAMESPACE_FILE_SCOPED = re.compile(r"^\s*namespace\s+([\w.]+)\s*;", re.MULTILINE)
_FS_NAMESPACE = re.compile(r"^\s*namespace\s+([\w.]+)", re.MULTILINE)

_CS_USING = re.compile(
    r"""^\s*using\s+
        (?:static\s+)?
        (?:\w+\s*=\s*)?       # aliased: `using foo = Bar.Baz;`
        ([\w.]+)
        \s*;""",
    re.MULTILINE | re.VERBOSE,
)
_FS_OPEN = re.compile(r"^\s*open\s+([\w.]+)", re.MULTILINE)


class DotNetImportExtractor:
    extensions: tuple[str, ...] = (".cs", ".fs")
    needs_namespace_index: bool = True

    def prime_namespace_index(
        self, file_path: str, content: str, ctx: ExtractionContext
    ) -> None:
        idx = ctx.namespace_index
        regexes = (
            (_CS_NAMESPACE_BLOCK, file_path.endswith(".cs")),
            (_CS_NAMESPACE_FILE_SCOPED, file_path.endswith(".cs")),
            (_FS_NAMESPACE, file_path.endswith(".fs")),
        )
        for regex, applies in regexes:
            if not applies:
                continue
            for match in regex.finditer(content):
                ns = match.group(1)
                idx.setdefault(ns, []).append(file_path)

    def extract(
        self, file_path: str, content: str, ctx: ExtractionContext
    ) -> list[str]:
        idx = ctx.namespace_index
        if not idx:
            return []

        regex = _CS_USING if file_path.endswith(".cs") else _FS_OPEN
        results: set[str] = set()
        for match in regex.finditer(content):
            ns = match.group(1)
            # `using X.Y` could mean: the namespace X.Y itself, a sub-namespace
            # X.Y.Z, OR (for `using static X.Y.Helpers`) the parent X.Y where
            # Helpers is a type.
            candidates = {ns}
            if "." in ns:
                candidates.add(ns.rsplit(".", 1)[0])
            for declared_ns, files in idx.items():
                if (
                    declared_ns in candidates
                    or any(declared_ns.startswith(c + ".") for c in candidates)
                ):
                    for f in files:
                        if f != file_path:
                            results.add(f)
        return sorted(results)


__all__ = ["DotNetImportExtractor"]
