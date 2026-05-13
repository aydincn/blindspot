"""Swift import extractor.

Swift's `import Foo` works at module granularity — a module is a Swift
Package or framework target. Without a SwiftPM/Xcode manifest parser we
can't resolve framework-level imports, so this extractor only catches
*intra-package* imports where the module name matches a directory in
the repo (typical SwiftPM convention: `Sources/<Module>/...`).
"""

import re

from blindspot.dependency_graph.extractors.base import ExtractionContext

_IMPORT_RE = re.compile(r"^\s*import\s+(\w+)", re.MULTILINE)


class SwiftImportExtractor:
    extensions: tuple[str, ...] = (".swift",)
    needs_namespace_index: bool = True

    def prime_namespace_index(
        self, file_path: str, content: str, ctx: ExtractionContext
    ) -> None:
        # SwiftPM convention: Sources/<Module>/...
        idx = ctx.namespace_index
        if file_path.startswith("Sources/"):
            parts = file_path.split("/", 2)
            if len(parts) >= 3:
                module = parts[1]
                idx.setdefault(module, []).append(file_path)

    def extract(
        self, file_path: str, content: str, ctx: ExtractionContext
    ) -> list[str]:
        idx = ctx.namespace_index
        if not idx:
            return []

        results: set[str] = set()
        for match in _IMPORT_RE.finditer(content):
            module = match.group(1)
            for f in idx.get(module, []):
                if f != file_path:
                    results.add(f)
        return sorted(results)


__all__ = ["SwiftImportExtractor"]
