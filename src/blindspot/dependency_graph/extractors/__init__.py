from blindspot.dependency_graph.extractors.base import (
    ExtractionContext,
    ImportExtractor,
)
from blindspot.dependency_graph.extractors.cpp import CppImportExtractor
from blindspot.dependency_graph.extractors.dotnet import DotNetImportExtractor
from blindspot.dependency_graph.extractors.go import GoImportExtractor
from blindspot.dependency_graph.extractors.java import JavaImportExtractor
from blindspot.dependency_graph.extractors.javascript import JavaScriptImportExtractor
from blindspot.dependency_graph.extractors.kotlin import KotlinImportExtractor
from blindspot.dependency_graph.extractors.php import PhpImportExtractor
from blindspot.dependency_graph.extractors.python import PythonImportExtractor
from blindspot.dependency_graph.extractors.ruby import RubyImportExtractor
from blindspot.dependency_graph.extractors.rust import RustImportExtractor
from blindspot.dependency_graph.extractors.swift import SwiftImportExtractor


def _build_default() -> dict[str, ImportExtractor]:
    """Wire each extractor under every extension it claims.

    Sharing one instance per extractor keeps the namespace_index population
    consistent across pass 1 / pass 2.
    """
    extractors: list[ImportExtractor] = [
        PythonImportExtractor(),
        JavaScriptImportExtractor(),
        DotNetImportExtractor(),
        JavaImportExtractor(),
        KotlinImportExtractor(),
        GoImportExtractor(),
        RustImportExtractor(),
        CppImportExtractor(),
        RubyImportExtractor(),
        PhpImportExtractor(),
        SwiftImportExtractor(),
    ]
    out: dict[str, ImportExtractor] = {}
    for ext in extractors:
        for suffix in ext.extensions:
            out[suffix] = ext
    return out


DEFAULT_EXTRACTORS: dict[str, ImportExtractor] = _build_default()


__all__ = [
    "CppImportExtractor",
    "DEFAULT_EXTRACTORS",
    "DotNetImportExtractor",
    "ExtractionContext",
    "GoImportExtractor",
    "ImportExtractor",
    "JavaImportExtractor",
    "JavaScriptImportExtractor",
    "KotlinImportExtractor",
    "PhpImportExtractor",
    "PythonImportExtractor",
    "RubyImportExtractor",
    "RustImportExtractor",
    "SwiftImportExtractor",
]
