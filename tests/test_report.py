from datetime import UTC, datetime

from blindspot import __version__
from blindspot.collector import GitCollector
from blindspot.ownership import OwnershipEngine
from blindspot.report import (
    DepartureContext,
    ReportContext,
    ReportRenderer,
    compute_remaining_gaps,
)
from blindspot.risk_models import BusFactorEngine, DepartureSimulation, KnowledgeDecayEngine

from blindspot.narrative.rule_based import RuleBasedNarrator

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


def test_rule_based_narrative_shows_upgrade_hint(make_repo):
    repo = make_repo([CommitSpec("Alice", "alice@x.com", "src/a.py", "1\n", 5)])
    ctx = _build_context(repo)
    narrative = RuleBasedNarrator(language="en").summarize(ctx)
    from dataclasses import replace
    ctx = replace(ctx, narrative=narrative)
    html = ReportRenderer().render(ctx)
    assert "Want a richer, prose-style executive summary" in html
    assert "--api-key" in html
    assert 'class="upgrade-hint"' in html


def test_cloud_narrative_hides_upgrade_hint(make_repo):
    from blindspot.narrative.models import NarrativeReport
    repo = make_repo([CommitSpec("Alice", "alice@x.com", "src/a.py", "1\n", 5)])
    ctx = _build_context(repo)
    # Simulate a cloud-generated narrative — model set to a real id
    narrative = NarrativeReport(
        executive_summary="Cloud-generated prose.",
        headline_action="Take action.",
        rationales={},
        language="en",
        model="claude-sonnet-4-6",
    )
    from dataclasses import replace
    ctx = replace(ctx, narrative=narrative)
    html = ReportRenderer().render(ctx)
    assert "Want a richer, prose-style executive summary" not in html


def test_review_hint_when_github_remote_detected_no_creds(make_repo):
    repo = make_repo([CommitSpec("Alice", "alice@x.com", "src/a.py", "1\n", 5)])
    base = _build_context(repo)
    from dataclasses import replace
    ctx = replace(base, reviews_enabled=False, detected_remote="github")
    html = ReportRenderer().render(ctx)
    assert "Review metrics unavailable" in html
    assert "gh auth login" in html
    assert 'class="notice-box"' in html


def test_review_hint_when_bitbucket_remote_detected_no_creds(make_repo):
    repo = make_repo([CommitSpec("Alice", "alice@x.com", "src/a.py", "1\n", 5)])
    base = _build_context(repo)
    from dataclasses import replace
    ctx = replace(base, reviews_enabled=False, detected_remote="bitbucket")
    html = ReportRenderer().render(ctx)
    assert "Review metrics unavailable" in html
    assert "bitbucket" in html.lower()
    assert "id.atlassian.com" in html


def test_no_review_hint_when_no_remote_detected(make_repo):
    repo = make_repo([CommitSpec("Alice", "alice@x.com", "src/a.py", "1\n", 5)])
    base = _build_context(repo)
    from dataclasses import replace
    ctx = replace(base, reviews_enabled=False, detected_remote=None)
    html = ReportRenderer().render(ctx)
    assert "Review metrics unavailable" not in html


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


def test_executive_brief_renders_when_signals_present(make_repo):
    """0.0.7 — top-of-report executive brief block surfaces top risks +
    business implication."""
    from blindspot.actions.models import (
        ActionCategory,
        ActionPriority,
        FragilityPattern,
        RecommendedAction,
    )
    from blindspot.narrative.exec_risks import ExecRisk
    repo = make_repo(
        [
            CommitSpec("Alice", "alice@x.com", "payment/main.py", "1\n", 5),
            CommitSpec("Bob", "bob@x.com", "shared/util.py", "2\n", 4),
        ]
    )
    ctx = _build_context(repo)
    from dataclasses import replace as _replace
    ctx = _replace(
        ctx,
        recommendations=(
            RecommendedAction(
                priority=ActionPriority.HIGH,
                category=ActionCategory.OWNERSHIP_DIVERSIFICATION,
                title="Diversify ownership of 'payment'",
                description="…", target="payment",
                evidence="…", pattern=FragilityPattern.SINGLE_OWNER_CONCENTRATION,
            ),
        ),
        top_risks=(
            ExecRisk(
                priority=ActionPriority.HIGH,
                title="Diversify ownership of 'payment'",
                target="payment",
                pattern=FragilityPattern.SINGLE_OWNER_CONCENTRATION,
            ),
        ),
        business_implication="Test implication sentence appearing in brief.",
    )
    html = ReportRenderer().render(ctx)
    assert "executive-brief" in html
    assert "Top 1 risk" in html
    assert "Diversify ownership of &#39;payment&#39;" in html
    assert "Test implication sentence appearing in brief." in html
    assert "Business implication" in html


def test_executive_brief_absent_when_no_signals(make_repo):
    """Empty repo → no top_risks, no business_implication → no brief block."""
    repo = make_repo([])
    ctx = _build_context(repo)
    html = ReportRenderer().render(ctx)
    # CSS class lives in the <style> block always — but the <section>
    # itself must be absent when there's nothing to say.
    assert '<section class="executive-brief">' not in html


def test_report_renders_four_group_headers(make_repo):
    """0.0.5a hygiene pass — sections grouped under 4 h1 headers."""
    repo = make_repo(
        [
            CommitSpec("Alice", "alice@x.com", "payment/main.py", "1\n", 5),
            CommitSpec("Bob", "bob@x.com", "shared/util.py", "2\n", 4),
        ]
    )
    ctx = _build_context(repo)
    html = ReportRenderer().render(ctx)

    assert 'class="group-title"' in html
    assert "TL;DR" in html
    assert "People &amp; Ownership" in html
    assert "Knowledge State" in html
    assert "Process Quality" in html
    # Exactly 4 group headers (we don't want accidental duplication).
    assert html.count('<h1 class="group-title">') == 4


def test_removed_low_signal_sections_are_absent(make_repo):
    """0.0.5a hygiene pass + 0.0.5c finalisation — these sections were
    intentionally removed from the HTML report. Engines still compute the
    data and the recommendation rules still fire; only the display was
    dropped."""
    repo = make_repo(
        [
            CommitSpec("Alice", "alice@x.com", "payment/main.py", "1\n", 5),
            CommitSpec("Bob", "bob@x.com", "shared/util.py", "2\n", 4),
        ]
    )
    ctx = _build_context(repo)
    html = ReportRenderer().render(ctx)

    assert "Activity summary" not in html
    assert "Central models" not in html
    assert "Structural backbone" not in html
    assert "PR activity mix" not in html
    assert "Top churned files" not in html
    assert "CODEOWNERS validation" not in html


def test_renders_empty_repo_gracefully(make_repo):
    repo = make_repo([])
    ctx = _build_context(repo)
    html = ReportRenderer().render(ctx)

    assert "No services analyzed" in html
    assert "No critical single-owner files" in html


def test_renders_departure_scenarios_for_top_contributors(make_repo):
    repo = make_repo(
        [
            CommitSpec("Alice", "alice@x.com", "payment/main.py", "1\n", 5),
            CommitSpec("Alice", "alice@x.com", "payment/billing.py", "2\n", 5),
            CommitSpec("Bob", "bob@x.com", "shared/util.py", "x\n", 4),
        ]
    )
    commits = list(GitCollector(repo, since_days=365).collect())
    ownership = OwnershipEngine().compute(commits)
    base = _build_context(repo)
    sim = DepartureSimulation()
    scenarios = (
        sim.simulate(ownership, ["alice@x.com"]),
        sim.simulate(ownership, ["bob@x.com"]),
    )
    from dataclasses import replace
    ctx = replace(base, departure_scenarios=scenarios, names=dict(ownership.names))
    html = ReportRenderer().render(ctx)

    assert "Departure scenarios" in html
    assert "If" in html and "alice@x.com" in html
    assert "If" in html and "bob@x.com" in html
    assert "Orphan files" in html


def test_omits_departure_section_when_no_scenarios(make_repo):
    repo = make_repo(
        [
            CommitSpec("Alice", "alice@x.com", "payment/main.py", "1\n", 5),
        ]
    )
    ctx = _build_context(repo)
    html = ReportRenderer().render(ctx)
    assert "Departure scenarios" not in html


def test_renders_departure_briefing_html(make_repo):
    repo = make_repo(
        [
            CommitSpec("Alice", "alice@x.com", "payment/main.py", "1\n", 5),
            CommitSpec("Alice", "alice@x.com", "payment/billing.py", "2\n", 5),
            CommitSpec("Bob", "bob@x.com", "shared/util.py", "x\n", 4),
        ]
    )
    commits = list(GitCollector(repo, since_days=365).collect())
    ownership = OwnershipEngine().compute(commits)
    report = DepartureSimulation().simulate(ownership, ["alice@x.com"])
    ctx = DepartureContext(
        repo_path=str(repo),
        generated_at=datetime.now(UTC),
        since_days=365,
        blindspot_version=__version__,
        departure=report,
        names=dict(ownership.names),
        remaining_gaps=compute_remaining_gaps(report),
    )
    html = ReportRenderer().render_departure(ctx)

    assert "<title>blindspot — Departure Briefing</title>" in html
    assert "alice@x.com" in html
    assert "Impact summary" in html
    assert "Files in scope" in html


def test_departure_briefing_omits_orphan_section_when_no_orphans(make_repo):
    # Two contributors balanced — no file becomes orphan when one leaves.
    repo = make_repo(
        [
            CommitSpec("Alice", "alice@x.com", "shared/util.py", "1\n", 5),
            CommitSpec("Bob", "bob@x.com", "shared/util.py", "2\n", 5),
        ]
    )
    commits = list(GitCollector(repo, since_days=365).collect())
    ownership = OwnershipEngine().compute(commits)
    report = DepartureSimulation().simulate(ownership, ["alice@x.com"])
    ctx = DepartureContext(
        repo_path=str(repo),
        generated_at=datetime.now(UTC),
        since_days=365,
        blindspot_version=__version__,
        departure=report,
        names=dict(ownership.names),
    )
    html = ReportRenderer().render_departure(ctx)
    # Header + summary present, but orphan section should not appear.
    assert "Impact summary" in html
    assert "Files becoming orphaned" not in html


def test_compute_remaining_gaps_ranks_top_inheritor(make_repo):
    # Alice dominates with multiple recent commits per file; Bob has one
    # old commit. When Alice leaves, the files become orphan but Bob is
    # the only remaining candidate inheritor.
    repo = make_repo(
        [
            CommitSpec("Alice", "alice@x.com", "payment/main.py", "a1\n", 30),
            CommitSpec("Alice", "alice@x.com", "payment/main.py", "a2\n", 20),
            CommitSpec("Alice", "alice@x.com", "payment/main.py", "a3\n", 10),
            CommitSpec("Alice", "alice@x.com", "payment/billing.py", "b1\n", 30),
            CommitSpec("Alice", "alice@x.com", "payment/billing.py", "b2\n", 20),
            CommitSpec("Alice", "alice@x.com", "payment/billing.py", "b3\n", 10),
            CommitSpec("Bob", "bob@x.com", "payment/main.py", "z1\n", 60),
            CommitSpec("Bob", "bob@x.com", "payment/billing.py", "z2\n", 60),
        ]
    )
    commits = list(GitCollector(repo, since_days=365).collect())
    ownership = OwnershipEngine().compute(commits)
    report = DepartureSimulation().simulate(ownership, ["alice@x.com"])
    gaps = compute_remaining_gaps(report)
    bob_gap = next((g for g in gaps if g.email == "bob@x.com"), None)
    assert bob_gap is not None
    assert bob_gap.picked_up_files >= 1


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
