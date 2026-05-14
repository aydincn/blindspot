from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol


@dataclass
class ExtractionContext:
    """Shared state between language extractors during a single build.

    - `repo_root` is the absolute path of the repo being scanned.
    - `repo_files` is the set of repo-relative paths of files that survived
      filtering (so extractors can validate that a resolved target exists).
    - `namespace_index` is a language-specific map populated in a first pass
      (e.g. .NET / Java / Kotlin "namespace → list of files"). Other
      extractors don't need it.
    - `model_files` is populated by AST-capable extractors to flag files
      that define "central model" classes (dataclasses, pydantic models,
      attrs/msgspec). The HTML report surfaces these separately so a
      reader can find the structural types fast.
    """
    repo_root: Path
    repo_files: set[str] = field(default_factory=set)
    namespace_index: dict[str, list[str]] = field(default_factory=dict)
    model_files: dict[str, int] = field(default_factory=dict)


class ImportExtractor(Protocol):
    extensions: tuple[str, ...]
    needs_namespace_index: bool

    def prime_namespace_index(
        self, file_path: str, content: str, ctx: ExtractionContext
    ) -> None:
        """First-pass hook for languages that need a namespace index.

        Default: no-op. Concrete extractors that need it (.NET, Java, Kotlin)
        override this to populate ctx.namespace_index.
        """
        ...

    def extract(
        self, file_path: str, content: str, ctx: ExtractionContext
    ) -> list[str]:
        """Return repo-relative paths this file imports."""
        ...


__all__ = ["ExtractionContext", "ImportExtractor"]
