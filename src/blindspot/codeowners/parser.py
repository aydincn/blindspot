"""Parse GitHub-style CODEOWNERS files.

Format reference: https://docs.github.com/en/repositories/managing-your-repositories-settings-and-features/customizing-your-repository/about-code-owners

- One rule per non-empty, non-comment line: `pattern owner1 owner2 …`
- Patterns follow .gitignore-like semantics but **last matching rule wins**.
- Owners are `@username`, `@org/team`, or `email@host`.
"""

import re
from dataclasses import dataclass
from pathlib import Path

CODEOWNERS_LOCATIONS = (
    ".github/CODEOWNERS",
    "CODEOWNERS",
    "docs/CODEOWNERS",
)


@dataclass(frozen=True, slots=True)
class CodeOwnersRule:
    pattern: str
    owners: tuple[str, ...]
    line_number: int
    regex: re.Pattern[str]

    def matches(self, path: str) -> bool:
        return bool(self.regex.match(path))


@dataclass(frozen=True, slots=True)
class CodeOwnersFile:
    source_path: Path
    rules: tuple[CodeOwnersRule, ...]

    def owners_for(self, file_path: str) -> tuple[str, ...]:
        # Last matching rule wins (GitHub semantics).
        path = file_path.lstrip("/")
        match: CodeOwnersRule | None = None
        for rule in self.rules:
            if rule.matches(path):
                match = rule
        return match.owners if match else ()

    def rule_for(self, file_path: str) -> CodeOwnersRule | None:
        path = file_path.lstrip("/")
        match: CodeOwnersRule | None = None
        for rule in self.rules:
            if rule.matches(path):
                match = rule
        return match


def find_codeowners_file(repo_root: Path) -> Path | None:
    for rel in CODEOWNERS_LOCATIONS:
        candidate = repo_root / rel
        if candidate.is_file():
            return candidate
    return None


def parse_codeowners(source: Path) -> CodeOwnersFile:
    rules: list[CodeOwnersRule] = []
    for line_no, raw in enumerate(source.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        pattern = parts[0]
        owners = tuple(parts[1:])
        regex = _pattern_to_regex(pattern)
        rules.append(CodeOwnersRule(
            pattern=pattern, owners=owners, line_number=line_no, regex=regex,
        ))
    return CodeOwnersFile(source_path=source, rules=tuple(rules))


def _pattern_to_regex(pattern: str) -> re.Pattern[str]:
    """Convert a CODEOWNERS pattern to a regex.

    Rules (simplified — covers the realistic majority):
    - Leading `/` anchors to repo root.
    - Trailing `/` matches the directory and everything beneath it.
    - `**` matches any number of path segments.
    - `*` matches anything except `/`.
    - `?` matches a single character except `/`.
    - Patterns without a leading `/` match at any directory level.
    """
    anchored = pattern.startswith("/")
    dir_only = pattern.endswith("/")
    pat = pattern.strip("/")

    # Build regex piece by piece.
    out: list[str] = []
    i = 0
    while i < len(pat):
        c = pat[i]
        if c == "*":
            if i + 1 < len(pat) and pat[i + 1] == "*":
                # `**` — any path
                out.append(".*")
                i += 2
                if i < len(pat) and pat[i] == "/":
                    i += 1
            else:
                out.append("[^/]*")
                i += 1
        elif c == "?":
            out.append("[^/]")
            i += 1
        elif c in ".+()^$|{}[]\\":
            out.append(re.escape(c))
            i += 1
        else:
            out.append(c)
            i += 1
    body = "".join(out)

    if anchored:
        prefix = "^"
    else:
        # Match at any depth: either at root or after a `/`.
        prefix = "^(?:.*/)?"
    if dir_only:
        suffix = "(?:/.*)?$"
    else:
        # If pattern has no slash and no leading anchor, it matches the basename anywhere.
        # Otherwise allow optional trailing path segments only if pattern looks like a dir.
        suffix = "$"
    return re.compile(prefix + body + suffix)
