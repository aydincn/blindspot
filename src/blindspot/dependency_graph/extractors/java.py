"""Java import extractor.

Resolves `import com.foo.Bar;` and `import static com.foo.Bar.method;` to
files declaring `package com.foo;`. Two-pass via namespace index so we
handle the common Maven/Gradle `src/main/java/com/foo/Bar.java` layout.
"""

import re

from blindspot.dependency_graph.extractors.base import ExtractionContext

_PACKAGE_RE = re.compile(r"^\s*package\s+([\w.]+)\s*;", re.MULTILINE)
_IMPORT_RE = re.compile(
    r"^\s*import\s+(?:static\s+)?([\w.]+(?:\.\*)?)\s*;",
    re.MULTILINE,
)


class JavaImportExtractor:
    extensions: tuple[str, ...] = (".java",)
    needs_namespace_index: bool = True

    def prime_namespace_index(
        self, file_path: str, content: str, ctx: ExtractionContext
    ) -> None:
        idx = ctx.namespace_index
        match = _PACKAGE_RE.search(content)
        pkg = match.group(1) if match else ""
        idx.setdefault(pkg, []).append(file_path)
        # Also index by "package.ClassName" so static/single-class imports resolve.
        basename = file_path.rsplit("/", 1)[-1]
        if basename.endswith(".java"):
            class_name = basename[:-5]
            fqn = f"{pkg}.{class_name}" if pkg else class_name
            idx.setdefault(fqn, []).append(file_path)

    def extract(
        self, file_path: str, content: str, ctx: ExtractionContext
    ) -> list[str]:
        idx = ctx.namespace_index
        if not idx:
            return []

        results: set[str] = set()
        for match in _IMPORT_RE.finditer(content):
            spec = match.group(1)
            # Wildcard: `import com.foo.*;`
            if spec.endswith(".*"):
                ns = spec[:-2]
                for f in idx.get(ns, []):
                    if f != file_path:
                        results.add(f)
                continue
            # Specific: `import com.foo.Bar;` → match FQN directly.
            for f in idx.get(spec, []):
                if f != file_path:
                    results.add(f)
            # Static method: `import static com.foo.Bar.method;` → match Bar.
            parent = ".".join(spec.split(".")[:-1])
            for f in idx.get(parent, []):
                if f != file_path:
                    results.add(f)
        return sorted(results)


__all__ = ["JavaImportExtractor"]
