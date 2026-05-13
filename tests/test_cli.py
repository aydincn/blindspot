from typer.testing import CliRunner

from blindspot import __version__
from blindspot.cli import app

from tests.conftest import CommitSpec

runner = CliRunner()


def test_version() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert __version__ in result.stdout


def test_scan_runs_on_real_repo(make_repo, tmp_path) -> None:
    repo = make_repo(
        [
            CommitSpec("Alice", "alice@example.com", "a.py", "x = 1\n", 5),
            CommitSpec("Bob", "bob@example.com", "b.py", "y = 2\n", 3),
        ]
    )
    output = tmp_path / "report.html"
    result = runner.invoke(
        app, ["scan", str(repo), "--since-days", "30", "--output", str(output)]
    )

    assert result.exit_code == 0
    assert "Commits" in result.stdout
    assert output.exists()
    assert "blindspot" in output.read_text()


def test_simulate_runs_on_real_repo(make_repo) -> None:
    repo = make_repo(
        [
            CommitSpec("Alice", "alice@example.com", "payment/main.py", "x = 1\n", 5),
            CommitSpec("Bob", "bob@example.com", "shared/util.py", "y = 2\n", 4),
        ]
    )
    result = runner.invoke(
        app, ["simulate", "--person", "alice@example.com", str(repo)]
    )
    assert result.exit_code == 0
    assert "Impact summary" in result.stdout
    assert "alice@example.com" in result.stdout
