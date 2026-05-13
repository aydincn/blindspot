import fnmatch
import re
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_BINARY_EXTENSIONS = frozenset({
    "png", "jpg", "jpeg", "gif", "svg", "ico", "webp", "bmp", "tiff", "tif",
    "woff", "woff2", "ttf", "eot", "otf",
    "mp3", "mp4", "webm", "ogg", "wav", "avi", "mov", "mkv", "flac",
    "zip", "tar", "gz", "tgz", "bz2", "xz", "7z", "rar",
    "pdf", "exe", "dll", "so", "dylib",
    "pyc", "pyo", "class", "o", "a", "obj",
    "psd", "ai", "sketch", "fig",
    "db", "sqlite", "sqlite3",
})

DEFAULT_GENERATED_FILES = frozenset({
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "npm-shrinkwrap.json",
    "poetry.lock", "Pipfile.lock", "uv.lock",
    "Cargo.lock", "Gemfile.lock", "composer.lock", "go.sum", "mix.lock",
})

DEFAULT_GENERATED_SUFFIXES = (
    ".min.js", ".min.css", ".map", ".bundle.js",
    ".pb.go", ".pb.cc", ".pb.h",        # protobuf generated
    ".g.dart", ".freezed.dart",          # dart generated
    ".gen.go", ".gen.ts",                # explicit-gen convention
    ".designer.cs",                       # .NET designer-generated
)

DEFAULT_IGNORE_DIRS = frozenset({
    "node_modules", "vendor", "dist", "build", "out",
    ".git", ".tox", ".nox", ".pytest_cache", ".ruff_cache", ".mypy_cache",
    "__pycache__", ".venv", "venv", "env",
    "target", ".gradle", ".idea", ".vscode",
    "obj", "bin",
    "Pods", "Carthage", "DerivedData",
    ".next", ".nuxt", ".cache", ".turbo",
    "coverage",
    # Build/codegen output:
    "__generated__", "generated", "Generated",
})

DEFAULT_GENERATED_PATH_PATTERNS = (
    # Tauri / cross-platform codegen output:
    "**/gen/android/**",
    "**/gen/ios/**",
    "**/gen/desktop/**",
    # Gradle / Maven:
    "**/build/generated/**",
    "**/target/generated-sources/**",
    # Jest snapshots are nominally tests but they are auto-updated, treat as generated:
    "**/__snapshots__/**",
)

DEFAULT_DATA_PATTERNS = (
    "**/data/*.yml", "**/data/*.yaml", "**/data/*.json",
    "_data/**",
    "**/i18n/**",
    "**/translations/**",
    "**/locales/**",
)

_GH_NOREPLY = re.compile(r"^(?:(\d+)\+)?([a-z0-9-]+)@users\.noreply\.github\.com$")


def canonical_email(email: str) -> str:
    """Normalize email for identity comparison.

    GitHub noreply emails ('123456+alice@users.noreply.github.com') are
    rewritten to a readable form ('alice@github') so the same human is
    not split into a stable-looking but cryptic identity.
    """
    email = email.strip().lower()
    match = _GH_NOREPLY.match(email)
    if match:
        return f"{match.group(2)}@github"
    return email


@dataclass
class FileFilter:
    binary_extensions: frozenset[str] = field(default_factory=lambda: DEFAULT_BINARY_EXTENSIONS)
    generated_files: frozenset[str] = field(default_factory=lambda: DEFAULT_GENERATED_FILES)
    generated_suffixes: tuple[str, ...] = DEFAULT_GENERATED_SUFFIXES
    generated_path_patterns: tuple[str, ...] = DEFAULT_GENERATED_PATH_PATTERNS
    ignore_dirs: frozenset[str] = field(default_factory=lambda: DEFAULT_IGNORE_DIRS)
    data_patterns: tuple[str, ...] = DEFAULT_DATA_PATTERNS
    linguist_generated_patterns: tuple[str, ...] = ()

    @classmethod
    def from_repo(cls, repo_path: Path) -> "FileFilter":
        patterns = _read_linguist_generated(repo_path / ".gitattributes")
        return cls(linguist_generated_patterns=patterns)

    def should_skip(self, path: str) -> bool:
        parts = path.split("/")
        for part in parts[:-1]:
            if part in self.ignore_dirs:
                return True

        basename = parts[-1]
        if basename in self.generated_files:
            return True
        for suffix in self.generated_suffixes:
            if basename.endswith(suffix):
                return True

        if "." in basename:
            ext = basename.rsplit(".", 1)[1].lower()
            if ext in self.binary_extensions:
                return True

        for pattern in self.data_patterns:
            if fnmatch.fnmatch(path, pattern):
                return True

        for pattern in self.generated_path_patterns:
            if fnmatch.fnmatch(path, pattern):
                return True

        for pattern in self.linguist_generated_patterns:
            if fnmatch.fnmatch(path, pattern):
                return True

        return False

    def is_generated(self, path: str) -> bool:
        """Cheap predicate for downstream filters.

        Same logic as `should_skip` but exposed as a positive check so
        recommendation/display layers can apply a consistent filter to
        data that already entered the collection (e.g. PR review files).
        """
        return self.should_skip(path)


def _read_linguist_generated(gitattributes_path: Path) -> tuple[str, ...]:
    if not gitattributes_path.exists():
        return ()
    patterns: list[str] = []
    for raw in gitattributes_path.read_text(errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        tokens = line.split()
        if len(tokens) < 2:
            continue
        pattern, attrs = tokens[0], tokens[1:]
        if "linguist-generated=true" in attrs or "linguist-generated" in attrs:
            patterns.append(pattern)
    return tuple(patterns)


__all__ = [
    "DEFAULT_BINARY_EXTENSIONS",
    "DEFAULT_DATA_PATTERNS",
    "DEFAULT_GENERATED_FILES",
    "DEFAULT_GENERATED_PATH_PATTERNS",
    "DEFAULT_GENERATED_SUFFIXES",
    "DEFAULT_IGNORE_DIRS",
    "FileFilter",
    "canonical_email",
]
