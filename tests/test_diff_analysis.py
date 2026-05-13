from datetime import UTC, datetime

import pytest

from blindspot.collector.github.pr_models import PullRequest, PullRequestFile
from blindspot.diff_analysis import (
    PRCategory,
    classify_file,
    classify_pr,
    summarise,
)


def _file(path: str, additions: int = 10, deletions: int = 2) -> PullRequestFile:
    return PullRequestFile(
        path=path, status="modified", additions=additions,
        deletions=deletions, changes=additions + deletions,
    )


def _pr(number: int, files: tuple[PullRequestFile, ...]) -> PullRequest:
    now = datetime.now(UTC)
    return PullRequest(
        number=number, title=f"#{number}", author_login="alice",
        state="closed", merged=True, created_at=now, closed_at=now,
        merged_at=now, body="", labels=(), milestone=None,
        requested_reviewers=(), files=files, reviews=(), review_comments=(),
        additions=sum(f.additions for f in files),
        deletions=sum(f.deletions for f in files),
    )


@pytest.mark.parametrize(
    "path,expected",
    [
        ("src/app.py", "code"),
        ("src/services/payment.py", "code"),
        ("tests/test_payment.py", "test"),
        ("test/foo.py", "test"),
        ("src/__tests__/index.spec.js", "test"),
        ("e2e/login.spec.ts", "test"),
        ("tests/integration/billing_test.py", "test"),
        ("docs/architecture.md", "docs"),
        ("README.md", "docs"),
        ("docs/index.rst", "docs"),
        (".github/workflows/ci.yml", "chore"),
        ("Dockerfile", "chore"),
        ("pyproject.toml", "chore"),
        ("setup.cfg", "chore"),
        (".pre-commit-config.yaml", "chore"),
        ("LICENSE", "code"),
        # Multi-language test conventions
        ("src/openhuman/tools/impl/system/update_apply_tests.rs", "test"),
        ("src/foo/bar_test.rs", "test"),
        ("internal/service/handler_test.go", "test"),
        ("app/src/components/__tests__/Foo.test.tsx", "test"),
        ("app/src/components/Foo.spec.ts", "test"),
        ("src/test/java/com/x/UserServiceTest.java", "test"),
        ("src/test/java/com/x/UserServiceTests.java", "test"),
        ("MyApp.Tests/UserServiceTests.cs", "test"),
        ("MyApp/Domain/UserSpec.cs", "test"),
        ("spec/models/user_spec.rb", "test"),
        ("spec/billing_test.rb", "test"),
        # Code files that look similar but shouldn't be tests
        ("src/contestable.py", "code"),
        ("lib/manifest.rs", "code"),
        ("src/util/AttestService.cs", "code"),
    ],
)
def test_file_classification(path, expected):
    assert classify_file(path) == expected


def test_pr_with_code_and_additions_is_feature():
    pr = _pr(1, (_file("src/app.py", additions=100, deletions=5),))
    result = classify_pr(pr)
    assert result.category == PRCategory.FEATURE


def test_pr_with_balanced_add_delete_is_refactor():
    pr = _pr(1, (_file("src/app.py", additions=40, deletions=40),))
    result = classify_pr(pr)
    assert result.category == PRCategory.REFACTOR


def test_pr_mostly_deletions_is_cleanup():
    pr = _pr(1, (_file("src/app.py", additions=5, deletions=80),))
    result = classify_pr(pr)
    assert result.category == PRCategory.CLEANUP


def test_pr_with_only_tests_is_test():
    pr = _pr(
        1,
        (
            _file("tests/test_a.py"),
            _file("tests/test_b.py"),
        ),
    )
    assert classify_pr(pr).category == PRCategory.TEST


def test_pr_with_only_docs_is_docs():
    pr = _pr(1, (_file("docs/setup.md"), _file("README.md")))
    assert classify_pr(pr).category == PRCategory.DOCS


def test_pr_with_only_chore_is_chore():
    pr = _pr(1, (_file(".github/workflows/ci.yml"), _file("Dockerfile")))
    assert classify_pr(pr).category == PRCategory.CHORE


def test_pr_with_code_plus_test_is_feature_not_test():
    pr = _pr(
        1,
        (
            _file("src/app.py", additions=80, deletions=2),
            _file("tests/test_app.py", additions=30, deletions=0),
        ),
    )
    assert classify_pr(pr).category == PRCategory.FEATURE


def test_summarise_aggregates_counts_and_ratios():
    prs = [
        _pr(1, (_file("src/a.py", additions=100, deletions=5),)),  # feature
        _pr(2, (_file("src/b.py", additions=5, deletions=80),)),   # cleanup
        _pr(3, (_file("tests/test_c.py"),)),                       # test
        _pr(4, (_file("docs/readme.md"),)),                        # docs
    ]
    summary = summarise(prs)
    assert summary.total_prs == 4
    assert summary.counts[PRCategory.FEATURE] == 1
    assert summary.counts[PRCategory.CLEANUP] == 1
    assert summary.counts[PRCategory.TEST] == 1
    assert summary.counts[PRCategory.DOCS] == 1
    assert summary.ratios[PRCategory.FEATURE] == 0.25


def test_summarise_top_churned_files_sorted_by_changes():
    prs = [
        _pr(1, (_file("hot.py", additions=100, deletions=50),)),
        _pr(2, (_file("hot.py", additions=200, deletions=20),)),
        _pr(3, (_file("cold.py", additions=2, deletions=1),)),
    ]
    summary = summarise(prs, top_n=5)
    assert summary.top_churned_files[0].file == "hot.py"
    assert summary.top_churned_files[0].pr_count == 2
    assert summary.top_churned_files[0].total_changes == 370
