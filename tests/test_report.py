from datetime import UTC, datetime

from blindspot import __version__
from blindspot.collector import GitCollector
from blindspot.ownership import OwnershipEngine
from blindspot.report import ReportContext, ReportRenderer
from blindspot.risk_models import BusFactorEngine, KnowledgeDecayEngine

from tests.conftest import CommitSpec


def _build_context(repo) -> ReportContext:
    commits = list(GitCollector(repo, since_days=365).collect())
    ownership = OwnershipEngine().compute(commits)
    bf_engine = BusFactorEngine()
    decay_engine = KnowledgeDecayEngine()
    services = bf_engine.for_services(ownership)
    file_bf = bf_engine.for_files(ownership)
    critical = [f for f in file_bf if f.risk_level == "critical"]
    decays = decay_engine.for_files(commits, ownership)
    decay_services = decay_engine.for_services(commits, ownership)

    files = set()
    additions = 0
    deletions = 0
    authors = set()
    for c in commits:
        authors.add(c.author_email)
        for f in c.files:
            files.add(f.path)
            additions += f.additions
            deletions += f.deletions

    return ReportContext(
        repo_path=str(repo),
        generated_at=datetime.now(UTC),
        since_days=365,
        blindspot_version=__version__,
        commit_count=len(commits),
        author_count=len(authors),
        file_count=len(files),
        additions=additions,
        deletions=deletions,
        services=tuple(services),
        critical_files=tuple(critical[:20]),
        decay_top=tuple(decays[:20]),
        decay_services=tuple(decay_services),
    )


def test_renders_html_with_expected_sections(make_repo):
    repo = make_repo(
        [
            CommitSpec("Alice", "alice@x.com", "payment/main.py", "1\n", 5),
            CommitSpec("Bob", "bob@x.com", "shared/util.py", "2\n", 4),
        ]
    )
    ctx = _build_context(repo)
    html = ReportRenderer().render(ctx)

    assert "<title>blindspot" in html
    assert "Knowledge resilience report" in html
    assert "Service risk map" in html
    assert "Files with single ownership" in html
    assert "Knowledge decay" in html
    assert __version__ in html


def test_renders_empty_repo_gracefully(make_repo):
    repo = make_repo([])
    ctx = _build_context(repo)
    html = ReportRenderer().render(ctx)

    assert "No services analyzed" in html
    assert "No critical single-owner files" in html


def test_escapes_user_supplied_content(make_repo):
    repo = make_repo(
        [
            CommitSpec(
                "Mallory",
                "mallory@x.com",
                "<script>alert(1)</script>.py",
                "x\n",
                5,
            )
        ]
    )
    ctx = _build_context(repo)
    html = ReportRenderer().render(ctx)

    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html
