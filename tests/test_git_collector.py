from blindspot.collector import GitCollector

from tests.conftest import CommitSpec


def test_collect_basic(make_repo):
    repo = make_repo(
        [
            CommitSpec("Alice", "alice@example.com", "service_a/main.py", "print('hi')\n", 5),
            CommitSpec(
                "Bob", "bob@example.com", "service_a/main.py", "print('hi')\nprint('bye')\n", 3
            ),
            CommitSpec("Alice", "alice@example.com", "service_b/util.py", "x = 1\n", 1),
        ]
    )

    commits = list(GitCollector(repo, since_days=30).collect())

    assert len(commits) == 3
    assert commits[0].author_email == "alice@example.com"
    assert commits[0].files[0].path == "service_b/util.py"


def test_collect_respects_since_window(make_repo):
    repo = make_repo(
        [
            CommitSpec("Old", "old@example.com", "old.py", "1", 365),
            CommitSpec("New", "new@example.com", "new.py", "2", 5),
        ]
    )

    commits = list(GitCollector(repo, since_days=30).collect())

    assert len(commits) == 1
    assert commits[0].author_email == "new@example.com"


def test_email_is_lowercased(make_repo):
    repo = make_repo(
        [CommitSpec("Alice", "Alice@Example.COM", "a.py", "1", 1)]
    )

    commits = list(GitCollector(repo, since_days=30).collect())

    assert commits[0].author_email == "alice@example.com"


def test_additions_and_deletions_captured(make_repo):
    repo = make_repo(
        [
            CommitSpec("A", "a@x.com", "f.py", "line1\n", 5),
            CommitSpec("A", "a@x.com", "f.py", "line1\nline2\nline3\n", 4),
        ]
    )

    commits = list(GitCollector(repo, since_days=30).collect())

    most_recent = commits[0]
    f = most_recent.files[0]
    assert f.path == "f.py"
    assert f.additions == 2
    assert f.deletions == 0
