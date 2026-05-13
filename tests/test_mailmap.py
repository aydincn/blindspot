from datetime import UTC, datetime

from blindspot.collector import GitCollector, MailMap
from blindspot.collector.mailmap import MailMap as MM
from blindspot.ownership import FileOwnership, OwnershipEngine, OwnershipMap

from tests.conftest import CommitSpec


def test_parses_proper_name_then_commit_email():
    mm = MM.from_text("Alice Smith <alice@company.com>\n")
    name, email = mm.resolve("alice", "alice@company.com")
    assert name == "Alice Smith"
    assert email == "alice@company.com"


def test_remaps_commit_email_to_proper_email():
    mm = MM.from_text("<alice@company.com> <alice@gmail.com>\n")
    name, email = mm.resolve("Alice", "alice@gmail.com")
    assert email == "alice@company.com"


def test_remaps_with_proper_name_and_emails():
    mm = MM.from_text("Alice Smith <alice@company.com> <alice@gmail.com>\n")
    name, email = mm.resolve("anything", "alice@gmail.com")
    assert name == "Alice Smith"
    assert email == "alice@company.com"


def test_remaps_with_commit_name_and_email():
    mm = MM.from_text("Alice Smith <alice@company.com> A. <alice@gmail.com>\n")
    name, email = mm.resolve("A.", "alice@gmail.com")
    assert name == "Alice Smith"
    assert email == "alice@company.com"
    # Without matching commit_name, falls through
    name2, email2 = mm.resolve("Different Name", "alice@gmail.com")
    assert email2 == "alice@gmail.com"


def test_skips_comments_and_blank_lines():
    mm = MM.from_text("# header\n\n   \nAlice <a@a.com>\n")
    name, email = mm.resolve("anything", "a@a.com")
    assert name == "Alice"


def test_empty_mailmap_is_passthrough():
    mm = MM.from_text("")
    name, email = mm.resolve("Bob", "bob@x.com")
    assert name == "Bob"
    assert email == "bob@x.com"


def test_collector_applies_mailmap_when_present(make_repo, tmp_path):
    repo = make_repo(
        [
            CommitSpec("Burak (outlook)", "burakisleyici@outlook.com", "f.py", "1\n", 5),
            CommitSpec("Burak (corp)", "burak.isleyici@company.com", "f.py", "1\n2\n", 3),
        ]
    )
    (repo / ".mailmap").write_text(
        "Burak Isleyici <burak.isleyici@company.com> <burakisleyici@outlook.com>\n"
    )

    commits = list(GitCollector(repo, since_days=30).collect())
    emails = {c.author_email for c in commits}
    assert emails == {"burak.isleyici@company.com"}
    assert {c.author_name for c in commits} == {"Burak Isleyici"}


def test_ownership_merges_aliased_identities_via_mailmap(make_repo):
    repo = make_repo(
        [
            CommitSpec("Burak", "burakisleyici@outlook.com", "f.py", "1\n", 5),
            CommitSpec("Burak", "burak.isleyici@company.com", "f.py", "1\n2\n", 3),
        ]
    )
    (repo / ".mailmap").write_text(
        "Burak Isleyici <burak.isleyici@company.com> <burakisleyici@outlook.com>\n"
    )

    commits = list(GitCollector(repo, since_days=30).collect())
    om = OwnershipEngine().compute(commits)

    for_file = om.for_file("f.py")
    assert len(for_file) == 1
    assert for_file[0].author_email == "burak.isleyici@company.com"
    assert om.name_for("burak.isleyici@company.com") == "Burak Isleyici"


def test_ownership_map_label_combines_name_and_email():
    fo = FileOwnership(
        file="a.py",
        author_email="alice@x.com",
        commit_count=1,
        additions=1,
        deletions=0,
        last_authored_at=datetime.now(UTC),
        days_since_last=0.0,
        raw_score=1.0,
        coverage=1.0,
    )
    om = OwnershipMap(scores=(fo,), names={"alice@x.com": "Alice Smith"})
    assert om.label_for("alice@x.com") == "Alice Smith (alice@x.com)"
    assert om.label_for("unknown@x.com") == "unknown@x.com"
