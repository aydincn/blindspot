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


def test_scan_uses_smart_service_granularity(make_repo, tmp_path) -> None:
    """0.0.5c — auto-detected source root + single package: services should
    be the directories *inside* the package, not the source root itself."""
    repo = make_repo(
        [
            CommitSpec(
                "Alice", "alice@example.com",
                "src/pkg/risk_models/a.py", "x=1\n", 5,
            ),
            CommitSpec(
                "Bob", "bob@example.com",
                "src/pkg/actions/b.py", "y=2\n", 4,
            ),
            CommitSpec(
                "Carol", "carol@example.com",
                "src/pkg/report/c.py", "z=3\n", 3,
            ),
        ]
    )
    output = tmp_path / "report.html"
    result = runner.invoke(
        app,
        ["scan", str(repo), "--since-days", "30", "--detailed",
         "--output", str(output)],
    )
    assert result.exit_code == 0
    html = output.read_text()
    # Service names should be the directories *inside* src/pkg/, not "src"
    # or "pkg". (Service risk map lives in the --detailed sections.)
    assert "<code>risk_models</code>" in html
    assert "<code>actions</code>" in html
    assert "<code>report</code>" in html
    assert "<code>src</code>" not in html
    assert "<code>pkg</code>" not in html


def test_scan_with_multi_person_departure(make_repo, tmp_path) -> None:
    """0.0.5b — --simulate-departures should add a combined card."""
    repo = make_repo(
        [
            CommitSpec("Alice", "alice@example.com", "payment/a.py", "x=1\n", 5),
            CommitSpec("Bob", "bob@example.com", "payment/b.py", "y=2\n", 4),
            CommitSpec("Carol", "carol@example.com", "shared/c.py", "z=3\n", 3),
        ]
    )
    output = tmp_path / "report.html"
    result = runner.invoke(
        app,
        [
            "scan", str(repo), "--since-days", "30",
            "--simulate-departures", "alice@example.com,bob@example.com",
            "--detailed",  # departure cards live in the detailed sections
            "--output", str(output),
        ],
    )
    assert result.exit_code == 0
    html = output.read_text()
    assert "If 2 people leave together" in html
    assert "departure-card-multi" in html


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
