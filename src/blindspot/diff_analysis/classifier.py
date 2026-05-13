from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum

from blindspot.collector.github.pr_models import PullRequest


class PRCategory(str, Enum):
    FEATURE = "feature"
    REFACTOR = "refactor"
    CLEANUP = "cleanup"
    TEST = "test"
    DOCS = "docs"
    CHORE = "chore"


# Where intent and trade-offs live, not what each line literally does.
_TEST_DIR_PARTS = {
    "test", "tests", "__tests__", "spec", "specs", "e2e",
    "integration-tests", "integration_tests", "unit-tests", "unit_tests",
    "benchmarks",
}
_DOCS_DIR_PARTS = {"docs", "doc", "documentation", "website", "site"}
_CHORE_BASENAMES = {
    "dockerfile", "makefile", ".gitignore", ".gitattributes", ".dockerignore",
    ".editorconfig", ".pre-commit-config.yaml", ".pre-commit-config.yml",
    "renovate.json", "dependabot.yml",
}
_CHORE_TOP_LEVEL_EXTS = (".toml", ".cfg", ".ini")


def _is_test_file(parts: list[str], basename_lc: str, basename_raw: str) -> bool:
    if any(p.lower() in _TEST_DIR_PARTS for p in parts):
        return True
    # Python: test_foo.py, foo_test.py
    if basename_lc.startswith("test_") or basename_lc.endswith("_test.py"):
        return True
    # JS/TS: foo.test.ts, foo.spec.ts
    if ".test." in basename_lc or ".spec." in basename_lc:
        return True
    # Rust: foo_tests.rs, foo_test.rs
    if basename_lc.endswith(("_tests.rs", "_test.rs")):
        return True
    # Go: foo_test.go
    if basename_lc.endswith("_test.go"):
        return True
    # Java/Kotlin/Groovy: FooTest.java, FooTests.java, FooIT.java, TestFoo.java
    # (case-sensitive: convention is CamelCase; lowercasing would catch e.g.
    #  Contestable.java)
    if basename_lc.endswith((".java", ".kt", ".kts", ".groovy")):
        stem = basename_raw.rsplit(".", 1)[0]
        if stem.endswith(("Test", "Tests", "IT", "Spec", "Specs")):
            return True
        if stem.startswith(("Test", "It")) and len(stem) > 4 and stem[4].isupper():
            return True
    # .NET (C#/F#): FooTest.cs, FooTests.cs, FooSpec.cs, FooFixture.cs
    if basename_lc.endswith((".cs", ".fs", ".vb")):
        stem = basename_raw.rsplit(".", 1)[0]
        if stem.endswith(("Test", "Tests", "Spec", "Specs", "Fixture")):
            return True
    # Ruby: foo_spec.rb, foo_test.rb
    if basename_lc.endswith(("_spec.rb", "_test.rb")):
        return True
    return False


def classify_file(path: str) -> str:
    """Return one of: code, test, docs, chore."""
    parts = path.split("/")
    basename_raw = parts[-1]
    basename = basename_raw.lower()

    if _is_test_file(parts, basename, basename_raw):
        return "test"

    if any(p.lower() in _DOCS_DIR_PARTS for p in parts):
        return "docs"
    if basename.endswith((".md", ".rst", ".adoc")) and basename not in {"license", "license.md"}:
        return "docs"

    if path.startswith(".github/") or path.startswith(".gitlab/") or path.startswith(".circleci/"):
        return "chore"
    if basename in _CHORE_BASENAMES:
        return "chore"
    if len(parts) <= 2 and basename.endswith(_CHORE_TOP_LEVEL_EXTS):
        return "chore"

    return "code"


@dataclass(frozen=True, slots=True)
class PRClassification:
    pr_number: int
    category: PRCategory
    code_files: int
    test_files: int
    docs_files: int
    chore_files: int
    additions: int
    deletions: int


def classify_pr(pr: PullRequest) -> PRClassification:
    counts = {"code": 0, "test": 0, "docs": 0, "chore": 0}
    for f in pr.files:
        counts[classify_file(f.path)] += 1
    total = sum(counts.values())

    if total == 0:
        category = PRCategory.CHORE
    elif counts["code"] > 0:
        churn = pr.additions + pr.deletions
        if churn == 0:
            category = PRCategory.REFACTOR
        else:
            ratio = pr.additions / churn
            if ratio > 0.7:
                category = PRCategory.FEATURE
            elif ratio < 0.3:
                category = PRCategory.CLEANUP
            else:
                category = PRCategory.REFACTOR
    elif counts["test"] >= counts["docs"] and counts["test"] >= counts["chore"]:
        category = PRCategory.TEST
    elif counts["docs"] >= counts["chore"]:
        category = PRCategory.DOCS
    else:
        category = PRCategory.CHORE

    return PRClassification(
        pr_number=pr.number,
        category=category,
        code_files=counts["code"],
        test_files=counts["test"],
        docs_files=counts["docs"],
        chore_files=counts["chore"],
        additions=pr.additions,
        deletions=pr.deletions,
    )


@dataclass(frozen=True, slots=True)
class FileChurn:
    file: str
    pr_count: int
    additions: int
    deletions: int

    @property
    def total_changes(self) -> int:
        return self.additions + self.deletions


@dataclass(frozen=True, slots=True)
class DiffChurnSummary:
    total_prs: int
    counts: dict[PRCategory, int]
    ratios: dict[PRCategory, float]
    top_churned_files: tuple[FileChurn, ...]
    classifications: tuple[PRClassification, ...]


def summarise(prs: Iterable[PullRequest], top_n: int = 15) -> DiffChurnSummary:
    classifications = tuple(classify_pr(pr) for pr in prs)
    counts: dict[PRCategory, int] = {cat: 0 for cat in PRCategory}
    for c in classifications:
        counts[c.category] += 1
    total = len(classifications)
    ratios = {cat: (n / total if total else 0.0) for cat, n in counts.items()}

    churn: dict[str, list[int]] = {}
    for pr in prs:
        for f in pr.files:
            entry = churn.setdefault(f.path, [0, 0, 0])
            entry[0] += 1
            entry[1] += f.additions
            entry[2] += f.deletions
    top_churned = tuple(
        FileChurn(file=path, pr_count=v[0], additions=v[1], deletions=v[2])
        for path, v in sorted(
            churn.items(), key=lambda kv: kv[1][1] + kv[1][2], reverse=True
        )[:top_n]
    )

    return DiffChurnSummary(
        total_prs=total,
        counts=counts,
        ratios=ratios,
        top_churned_files=top_churned,
        classifications=classifications,
    )


__all__ = [
    "DiffChurnSummary",
    "FileChurn",
    "PRCategory",
    "PRClassification",
    "classify_file",
    "classify_pr",
    "summarise",
]
