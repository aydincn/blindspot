"""Per-language extractor tests.

One repo per language, written via `make_repo`-style direct file writing
(not git, since we're testing the file-system walker). Each test verifies
that the builder produces the expected edge.
"""

from pathlib import Path

from blindspot.dependency_graph import DependencyGraphBuilder


def _write(root: Path, rel: str, content: str) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)


def _build_and_edges(repo: Path):
    graph = DependencyGraphBuilder().build(repo)
    return set(graph.nx_graph.edges())


# ---- JavaScript / TypeScript -----------------------------------------------

def test_js_import_resolves_relative(tmp_path: Path):
    _write(tmp_path, "src/foo.ts", "export const x = 1;\n")
    _write(tmp_path, "src/bar.ts", 'import { x } from "./foo";\n')
    edges = _build_and_edges(tmp_path)
    assert ("src/bar.ts", "src/foo.ts") in edges


def test_js_require_resolves(tmp_path: Path):
    _write(tmp_path, "helper.js", "module.exports = 1;\n")
    _write(tmp_path, "main.js", 'const h = require("./helper");\n')
    edges = _build_and_edges(tmp_path)
    assert ("main.js", "helper.js") in edges


def test_js_index_file_resolves(tmp_path: Path):
    _write(tmp_path, "lib/index.ts", "export const a = 1;\n")
    _write(tmp_path, "app/main.ts", 'import { a } from "../lib";\n')
    edges = _build_and_edges(tmp_path)
    assert ("app/main.ts", "lib/index.ts") in edges


def test_js_type_import_is_resolved(tmp_path: Path):
    _write(tmp_path, "types.ts", "export type X = number;\n")
    _write(tmp_path, "use.ts", 'import type { X } from "./types";\n')
    edges = _build_and_edges(tmp_path)
    assert ("use.ts", "types.ts") in edges


def test_js_external_package_ignored(tmp_path: Path):
    _write(tmp_path, "a.ts", 'import React from "react";\n')
    graph = DependencyGraphBuilder().build(tmp_path)
    assert graph.edge_count == 0


# ---- .NET (C# / F#) --------------------------------------------------------

def test_csharp_using_resolves_via_namespace_index(tmp_path: Path):
    _write(tmp_path, "src/Auth/Login.cs", "namespace App.Auth { public class Login {} }\n")
    _write(
        tmp_path, "src/App.cs",
        "using App.Auth;\nnamespace App { public class Main {} }\n",
    )
    edges = _build_and_edges(tmp_path)
    assert ("src/App.cs", "src/Auth/Login.cs") in edges


def test_csharp_file_scoped_namespace_resolves(tmp_path: Path):
    _write(tmp_path, "src/Db.cs", "namespace App.Data;\npublic class Db {}\n")
    _write(tmp_path, "src/Use.cs", "using App.Data;\n")
    edges = _build_and_edges(tmp_path)
    assert ("src/Use.cs", "src/Db.cs") in edges


def test_csharp_using_static_resolves(tmp_path: Path):
    _write(tmp_path, "src/Math.cs", "namespace App.Math { public static class Helpers {} }\n")
    _write(tmp_path, "src/Use.cs", "using static App.Math.Helpers;\n")
    edges = _build_and_edges(tmp_path)
    assert ("src/Use.cs", "src/Math.cs") in edges


def test_fsharp_open_resolves(tmp_path: Path):
    _write(tmp_path, "Lib.fs", "namespace App.Lib\nmodule Foo = ()\n")
    _write(tmp_path, "Main.fs", "open App.Lib\n")
    edges = _build_and_edges(tmp_path)
    assert ("Main.fs", "Lib.fs") in edges


# ---- Java ------------------------------------------------------------------

def test_java_import_resolves_to_declaring_file(tmp_path: Path):
    _write(
        tmp_path,
        "src/main/java/com/x/Foo.java",
        "package com.x;\npublic class Foo {}\n",
    )
    _write(
        tmp_path,
        "src/main/java/com/y/Bar.java",
        "package com.y;\nimport com.x.Foo;\npublic class Bar {}\n",
    )
    edges = _build_and_edges(tmp_path)
    assert (
        "src/main/java/com/y/Bar.java",
        "src/main/java/com/x/Foo.java",
    ) in edges


def test_java_wildcard_import(tmp_path: Path):
    _write(
        tmp_path,
        "src/main/java/com/x/Foo.java",
        "package com.x;\npublic class Foo {}\n",
    )
    _write(
        tmp_path,
        "src/main/java/com/y/User.java",
        "package com.y;\nimport com.x.*;\n",
    )
    edges = _build_and_edges(tmp_path)
    assert (
        "src/main/java/com/y/User.java",
        "src/main/java/com/x/Foo.java",
    ) in edges


# ---- Kotlin ----------------------------------------------------------------

def test_kotlin_import_resolves(tmp_path: Path):
    _write(tmp_path, "src/main/kotlin/com/x/Foo.kt", "package com.x\nclass Foo\n")
    _write(
        tmp_path, "src/main/kotlin/com/y/Bar.kt",
        "package com.y\nimport com.x.Foo\n",
    )
    edges = _build_and_edges(tmp_path)
    assert (
        "src/main/kotlin/com/y/Bar.kt",
        "src/main/kotlin/com/x/Foo.kt",
    ) in edges


# ---- Go --------------------------------------------------------------------

def test_go_import_resolves_via_go_mod(tmp_path: Path):
    _write(tmp_path, "go.mod", "module example.com/svc\n\ngo 1.22\n")
    _write(tmp_path, "internal/auth/auth.go", "package auth\nfunc Login() {}\n")
    _write(
        tmp_path,
        "cmd/main.go",
        'package main\nimport "example.com/svc/internal/auth"\nfunc main() { auth.Login() }\n',
    )
    edges = _build_and_edges(tmp_path)
    assert ("cmd/main.go", "internal/auth/auth.go") in edges


def test_go_grouped_import(tmp_path: Path):
    _write(tmp_path, "go.mod", "module foo/bar\n")
    _write(tmp_path, "a/a.go", "package a\n")
    _write(tmp_path, "b/b.go", "package b\n")
    _write(
        tmp_path,
        "main.go",
        'package main\nimport (\n\t"foo/bar/a"\n\t"foo/bar/b"\n)\n',
    )
    edges = _build_and_edges(tmp_path)
    assert ("main.go", "a/a.go") in edges
    assert ("main.go", "b/b.go") in edges


def test_go_external_import_ignored(tmp_path: Path):
    _write(tmp_path, "go.mod", "module ours\n")
    _write(tmp_path, "main.go", 'package main\nimport "github.com/x/y"\n')
    graph = DependencyGraphBuilder().build(tmp_path)
    assert graph.edge_count == 0


# ---- Rust ------------------------------------------------------------------

def test_rust_mod_resolves(tmp_path: Path):
    _write(tmp_path, "src/lib.rs", "mod helper;\n")
    _write(tmp_path, "src/helper.rs", "pub fn hi() {}\n")
    edges = _build_and_edges(tmp_path)
    assert ("src/lib.rs", "src/helper.rs") in edges


def test_rust_use_crate_resolves(tmp_path: Path):
    _write(tmp_path, "src/lib.rs", "")
    _write(tmp_path, "src/auth/session.rs", "")
    _write(tmp_path, "src/api.rs", "use crate::auth::session::Token;\n")
    edges = _build_and_edges(tmp_path)
    assert ("src/api.rs", "src/auth/session.rs") in edges


def test_rust_mod_rs_form_resolves(tmp_path: Path):
    _write(tmp_path, "src/foo/mod.rs", "")
    _write(tmp_path, "src/main.rs", "use crate::foo::Bar;\n")
    edges = _build_and_edges(tmp_path)
    assert ("src/main.rs", "src/foo/mod.rs") in edges


def test_rust_stdlib_ignored(tmp_path: Path):
    _write(tmp_path, "src/lib.rs", "use std::collections::HashMap;\n")
    graph = DependencyGraphBuilder().build(tmp_path)
    assert graph.edge_count == 0


# ---- C / C++ ---------------------------------------------------------------

def test_cpp_user_include_resolves_relative(tmp_path: Path):
    _write(tmp_path, "src/foo.h", "#pragma once\n")
    _write(tmp_path, "src/foo.cpp", '#include "foo.h"\n')
    edges = _build_and_edges(tmp_path)
    assert ("src/foo.cpp", "src/foo.h") in edges


def test_cpp_system_include_resolves_via_include_dir(tmp_path: Path):
    _write(tmp_path, "include/lib/api.h", "#pragma once\n")
    _write(tmp_path, "src/main.cpp", "#include <lib/api.h>\n")
    edges = _build_and_edges(tmp_path)
    assert ("src/main.cpp", "include/lib/api.h") in edges


def test_cpp_unresolved_system_include_ignored(tmp_path: Path):
    _write(tmp_path, "main.c", "#include <stdio.h>\n#include <stdlib.h>\n")
    graph = DependencyGraphBuilder().build(tmp_path)
    assert graph.edge_count == 0


# ---- Ruby ------------------------------------------------------------------

def test_ruby_require_relative(tmp_path: Path):
    _write(tmp_path, "lib/helper.rb", "module Helper; end\n")
    _write(tmp_path, "lib/main.rb", "require_relative 'helper'\n")
    edges = _build_and_edges(tmp_path)
    assert ("lib/main.rb", "lib/helper.rb") in edges


def test_ruby_require_lib_path(tmp_path: Path):
    _write(tmp_path, "lib/calc.rb", "")
    # `bin/` is in FileFilter ignore_dirs, so use a non-ignored path.
    _write(tmp_path, "app/runner.rb", "require 'calc'\n")
    edges = _build_and_edges(tmp_path)
    assert ("app/runner.rb", "lib/calc.rb") in edges


def test_ruby_external_gem_ignored(tmp_path: Path):
    _write(tmp_path, "a.rb", "require 'json'\nrequire 'rails'\n")
    graph = DependencyGraphBuilder().build(tmp_path)
    assert graph.edge_count == 0


# ---- PHP -------------------------------------------------------------------

def test_php_path_include(tmp_path: Path):
    _write(tmp_path, "lib/util.php", "<?php\n")
    _write(tmp_path, "lib/app.php", "<?php\nrequire_once 'util.php';\n")
    edges = _build_and_edges(tmp_path)
    assert ("lib/app.php", "lib/util.php") in edges


def test_php_use_namespace_resolves_via_suffix(tmp_path: Path):
    _write(tmp_path, "src/App/Services/Mailer.php", "<?php\nnamespace App\\Services;\n")
    _write(tmp_path, "src/App/Controller.php", "<?php\nuse App\\Services\\Mailer;\n")
    edges = _build_and_edges(tmp_path)
    assert ("src/App/Controller.php", "src/App/Services/Mailer.php") in edges


# ---- Swift -----------------------------------------------------------------

def test_swift_module_import_resolves(tmp_path: Path):
    _write(tmp_path, "Sources/Auth/Login.swift", "public struct Login {}\n")
    _write(tmp_path, "Sources/App/Main.swift", "import Auth\n")
    edges = _build_and_edges(tmp_path)
    assert ("Sources/App/Main.swift", "Sources/Auth/Login.swift") in edges


def test_swift_external_module_ignored(tmp_path: Path):
    _write(tmp_path, "Sources/App/Main.swift", "import Foundation\n")
    graph = DependencyGraphBuilder().build(tmp_path)
    assert graph.edge_count == 0
