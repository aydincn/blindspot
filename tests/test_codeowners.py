from datetime import UTC, datetime, timedelta
from pathlib import Path

from blindspot.codeowners import (
    CodeOwnersValidator,
    find_codeowners_file,
    parse_codeowners,
)
from blindspot.collector.git import Commit, FileChange
from blindspot.ownership import OwnershipEngine


def _commit(email: str, name: str, files: tuple[str, ...], days_ago: int) -> Commit:
    now = datetime.now(UTC)
    return Commit(
        sha=f"{email}-{days_ago}-{'-'.join(files)}",
        author_name=name,
        author_email=email,
        authored_at=now - timedelta(days=days_ago),
        message="msg",
        files=tuple(
            FileChange(path=f, additions=10, deletions=2) for f in files
        ),
        is_merge=False,
    )


def test_parse_basic_codeowners(tmp_path: Path) -> None:
    src = tmp_path / "CODEOWNERS"
    src.write_text(
        "# top comment\n"
        "*.py @alice\n"
        "/src/auth/ @bob @org/auth-team\n"
        "docs/   @carol\n"
        "\n"
        "*.md  user@example.com\n"
    )
    parsed = parse_codeowners(src)
    assert len(parsed.rules) == 4
    assert parsed.rules[0].pattern == "*.py"
    assert parsed.rules[0].owners == ("@alice",)
    assert parsed.owners_for("src/main.py") == ("@alice",)
    assert parsed.owners_for("src/auth/login.py") == ("@bob", "@org/auth-team")
    # docs/readme.md matches both `docs/` (@carol) and `*.md` (email); last wins.
    assert parsed.owners_for("docs/readme.md") == ("user@example.com",)
    assert parsed.owners_for("docs/handbook.txt") == ("@carol",)
    assert parsed.owners_for("README.md") == ("user@example.com",)


def test_pattern_anchored_vs_unanchored(tmp_path: Path) -> None:
    src = tmp_path / "CODEOWNERS"
    src.write_text(
        "/scripts/ @root-team\n"
        "scripts/ @nested-team\n"
    )
    parsed = parse_codeowners(src)
    # Anchored matches only at root
    assert parsed.owners_for("scripts/build.sh") == ("@nested-team",)  # last wins
    assert parsed.owners_for("tools/scripts/build.sh") == ("@nested-team",)


def test_find_codeowners_file(tmp_path: Path) -> None:
    (tmp_path / ".github").mkdir()
    (tmp_path / ".github" / "CODEOWNERS").write_text("* @x\n")
    found = find_codeowners_file(tmp_path)
    assert found is not None
    assert found.name == "CODEOWNERS"


def test_validator_categorizes_aligned_orphan_mismatch(tmp_path: Path) -> None:
    src = tmp_path / "CODEOWNERS"
    src.write_text(
        "src/auth/  @alice\n"
        "src/billing/ @bob\n"
    )
    co = parse_codeowners(src)

    commits = [
        # Alice owns auth — matches CODEOWNERS
        _commit("alice@x.com", "Alice", ("src/auth/login.py",), 10),
        _commit("alice@x.com", "Alice", ("src/auth/login.py",), 5),
        # Carol owns billing (not Bob as declared) — mismatch
        _commit("carol@x.com", "Carol", ("src/billing/charge.py",), 10),
        _commit("carol@x.com", "Carol", ("src/billing/charge.py",), 5),
        # Random orphan file with no CODEOWNERS rule
        _commit("dave@x.com", "Dave", ("misc/util.py",), 5),
    ]
    om = OwnershipEngine().compute(commits)
    report = CodeOwnersValidator().validate(co, om, commits)

    aligned_files = {f.file for f in report.aligned}
    mismatch_files = {f.file for f in report.mismatches}
    orphan_files = {f.file for f in report.orphans}

    assert "src/auth/login.py" in aligned_files
    assert "src/billing/charge.py" in mismatch_files
    assert "misc/util.py" in orphan_files


def test_validator_marks_stale_when_owner_quiet(tmp_path: Path) -> None:
    src = tmp_path / "CODEOWNERS"
    src.write_text("src/legacy/ @alice\n")
    co = parse_codeowners(src)

    commits = [
        # Alice touched it long ago — still top owner but stale
        _commit("alice@x.com", "Alice", ("src/legacy/old.py",), 200),
        _commit("alice@x.com", "Alice", ("src/legacy/old.py",), 180),
    ]
    om = OwnershipEngine().compute(commits)
    report = CodeOwnersValidator(stale_days=90).validate(co, om, commits)

    stale_files = {f.file for f in report.stale}
    assert "src/legacy/old.py" in stale_files


def test_validator_team_only_when_no_individuals(tmp_path: Path) -> None:
    src = tmp_path / "CODEOWNERS"
    src.write_text("src/  @org/platform-team\n")
    co = parse_codeowners(src)
    commits = [_commit("dave@x.com", "Dave", ("src/foo.py",), 5)]
    om = OwnershipEngine().compute(commits)
    report = CodeOwnersValidator().validate(co, om, commits)
    assert any(f.category == "team_only" for f in report.findings)


def test_github_noreply_username_matches(tmp_path: Path) -> None:
    src = tmp_path / "CODEOWNERS"
    src.write_text("*.py @alice\n")
    co = parse_codeowners(src)
    commits = [
        _commit("111+alice@users.noreply.github.com", "Alice", ("a.py",), 5),
        _commit("111+alice@users.noreply.github.com", "Alice", ("a.py",), 3),
    ]
    om = OwnershipEngine().compute(commits)
    report = CodeOwnersValidator().validate(co, om, commits)
    assert any(f.category == "aligned" for f in report.findings)
