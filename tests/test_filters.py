from pathlib import Path

import pytest

from blindspot.collector.filters import FileFilter, canonical_email


@pytest.mark.parametrize(
    "path",
    [
        "logo.png", "icon.svg", "Arial.woff2", "demo.mp4", "archive.tar.gz",
        "build.zip", "tool.exe", "lib.dylib", "compiled.pyc",
    ],
)
def test_binary_extensions_are_skipped(path):
    assert FileFilter().should_skip(path)


@pytest.mark.parametrize(
    "path",
    [
        "package-lock.json", "poetry.lock", "Cargo.lock", "yarn.lock", "go.sum",
    ],
)
def test_lock_files_are_skipped(path):
    assert FileFilter().should_skip(path)


@pytest.mark.parametrize(
    "path",
    [
        "dist/bundle.min.js", "static/site.min.css", "build/app.bundle.js",
        "static/app.js.map",
    ],
)
def test_generated_suffixes_and_dist_dirs_are_skipped(path):
    assert FileFilter().should_skip(path)


@pytest.mark.parametrize(
    "path",
    [
        "node_modules/lodash/index.js",
        "vendor/aws-sdk/lib/core.js",
        "__pycache__/cli.cpython-312.pyc",
        ".venv/lib/python3.12/site-packages/foo.py",
    ],
)
def test_ignored_dirs_are_skipped(path):
    assert FileFilter().should_skip(path)


@pytest.mark.parametrize(
    "path",
    [
        "src/blindspot/cli.py",
        "tests/test_cli.py",
        "config.yaml",
        "docs/architecture.md",
        "README.md",
    ],
)
def test_code_files_are_kept(path):
    assert not FileFilter().should_skip(path)


@pytest.mark.parametrize(
    "path",
    [
        "docs/en/data/people.yml",
        "docs/en/data/sponsors.yml",
        "docs/en/data/contributors.yml",
        "_data/site.yml",
        "src/i18n/en.json",
        "app/locales/tr/translation.json",
    ],
)
def test_data_patterns_are_skipped(path):
    assert FileFilter().should_skip(path)


def test_data_pattern_does_not_match_regular_config(make_repo=None):
    assert not FileFilter().should_skip("config.yaml")
    assert not FileFilter().should_skip("docs/architecture.md")


def test_linguist_generated_from_gitattributes(tmp_path: Path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / ".gitattributes").write_text(
        "# header comment\n"
        "*.gen.go linguist-generated=true\n"
        "vendored/** linguist-generated\n"
        "src/manual.go text\n"
    )

    ff = FileFilter.from_repo(repo_root)
    assert ff.should_skip("api/server.gen.go")
    assert ff.should_skip("vendored/foo/bar.go")
    assert not ff.should_skip("src/manual.go")


def test_canonical_email_strips_github_noreply_user_id():
    assert canonical_email("109919500+yuriimotov@users.noreply.github.com") == "yuriimotov@github"


def test_canonical_email_strips_github_noreply_without_user_id():
    assert canonical_email("alice@users.noreply.github.com") == "alice@github"


def test_canonical_email_keeps_real_emails_unchanged():
    assert canonical_email("Bob@Example.COM") == "bob@example.com"
    assert canonical_email("dev@company.io") == "dev@company.io"


@pytest.mark.parametrize(
    "path",
    [
        "src-tauri/gen/android/app/src/main/java/com/x/Bridge.kt",
        "src-tauri/gen/ios/Plugins/Foo.swift",
        "app/build/generated/source/buildConfig/release/com/x/BuildConfig.java",
        "service/target/generated-sources/protobuf/Foo.java",
        "components/__snapshots__/Foo.test.tsx.snap",
        "src/__generated__/queries.ts",
        "lib/generated/openapi/types.ts",
    ],
)
def test_generated_path_patterns_are_skipped(path):
    assert FileFilter().should_skip(path)


@pytest.mark.parametrize(
    "path",
    [
        "src/foo.pb.go",
        "lib/messages.pb.cc",
        "app/main.gen.ts",
        "models/user.freezed.dart",
        "Forms/MainForm.designer.cs",
    ],
)
def test_generated_suffixes_extended(path):
    assert FileFilter().should_skip(path)


def test_is_generated_alias():
    ff = FileFilter()
    assert ff.is_generated("Cargo.lock")
    assert ff.is_generated("src-tauri/gen/android/app/Foo.kt")
    assert not ff.is_generated("src/foo.py")
