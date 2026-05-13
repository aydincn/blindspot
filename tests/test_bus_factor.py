from blindspot.collector import GitCollector
from blindspot.ownership import OwnershipEngine
from blindspot.risk_models import BusFactorEngine
from blindspot.risk_models.bus_factor import top_level_dir

from tests.conftest import CommitSpec


def _compute(repo):
    commits = list(GitCollector(repo, since_days=365).collect())
    return OwnershipEngine().compute(commits)


def test_single_owner_file_is_critical(make_repo):
    repo = make_repo([CommitSpec("Solo", "solo@x.com", "x.py", "1\n", 5)])
    om = _compute(repo)
    bf = BusFactorEngine().for_files(om)
    assert len(bf) == 1
    assert bf[0].bus_factor == 1
    assert bf[0].risk_level == "critical"


def test_two_balanced_owners_lowers_bus_factor_risk(make_repo):
    repo = make_repo(
        [
            CommitSpec("A", "a@x.com", "x.py", "1\n", 5),
            CommitSpec("B", "b@x.com", "x.py", "1\n2\n", 4),
            CommitSpec("A", "a@x.com", "x.py", "1\n2\n3\n", 3),
            CommitSpec("B", "b@x.com", "x.py", "1\n2\n3\n4\n", 2),
        ]
    )
    om = _compute(repo)
    bf = BusFactorEngine(threshold=0.80).for_files(om)
    assert bf[0].bus_factor == 2
    assert bf[0].risk_level == "high"


def test_service_bus_factor_aggregates_across_files(make_repo):
    repo = make_repo(
        [
            CommitSpec("Solo", "solo@x.com", "payment/a.py", "1\n", 5),
            CommitSpec("Solo", "solo@x.com", "payment/b.py", "1\n", 4),
            CommitSpec("A", "a@x.com", "shared/x.py", "1\n", 5),
            CommitSpec("B", "b@x.com", "shared/x.py", "1\n2\n", 4),
            CommitSpec("A", "a@x.com", "shared/y.py", "1\n", 3),
            CommitSpec("B", "b@x.com", "shared/y.py", "1\n2\n", 2),
        ]
    )
    om = _compute(repo)
    services = BusFactorEngine().for_services(om)

    payment = next(s for s in services if s.service == "payment")
    shared = next(s for s in services if s.service == "shared")

    assert payment.bus_factor == 1
    assert payment.risk_level == "critical"
    assert payment.file_count == 2
    assert shared.bus_factor == 2
    assert shared.file_count == 2


def test_root_level_files_grouped_under_root(make_repo):
    repo = make_repo([CommitSpec("Solo", "solo@x.com", "README.md", "hi\n", 5)])
    om = _compute(repo)
    services = BusFactorEngine().for_services(om)
    assert services[0].service == "(root)"


def test_top_level_dir_strips_leading_quotes():
    assert top_level_dir('"gitbooks/foo.md') == "gitbooks"
    assert top_level_dir("'src/main.py") == "src"


def test_top_level_dir_groups_garbage_paths_as_other():
    # Stray `path=...` or whitespace in head segment -> (other)
    assert top_level_dir("path=src/foo.py") == "(other)"
    assert top_level_dir("some dir/foo.py") == "(other)"
    assert top_level_dir("") == "(other)"


def test_top_level_dir_groups_known_config_dotfiles():
    assert top_level_dir(".husky/pre-commit") == "(config)"
    assert top_level_dir(".codex/agents.md") == "(config)"
    assert top_level_dir(".vscode/settings.json") == "(config)"
    assert top_level_dir(".cursor/rules.md") == "(config)"
    # .github is product-meaningful (CI workflows): stays as-is
    assert top_level_dir(".github/workflows/ci.yml") == ".github"


def test_files_sorted_by_risk_first(make_repo):
    repo = make_repo(
        [
            CommitSpec("Solo", "solo@x.com", "risky.py", "1\n", 5),
            CommitSpec("A", "a@x.com", "safe.py", "1\n", 5),
            CommitSpec("B", "b@x.com", "safe.py", "1\n2\n", 4),
            CommitSpec("C", "c@x.com", "safe.py", "1\n2\n3\n", 3),
            CommitSpec("D", "d@x.com", "safe.py", "1\n2\n3\n4\n", 2),
        ]
    )
    om = _compute(repo)
    bf = BusFactorEngine().for_files(om)
    assert bf[0].file == "risky.py"
    assert bf[0].bus_factor == 1
