import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pytest

from blindspot.actions import ActionCategory, ActionPriority, RecommendedAction
from blindspot.narrative import (
    NarrativeConfigError,
    NarrativeEngine,
    load_narrative_config,
)
from blindspot.narrative.prompt import build_departure_prompt, build_user_prompt
from blindspot.report.context import ReportContext
from blindspot.resilience import ResilienceScoreEngine
from blindspot.risk_models.bus_factor import ServiceBusFactor
from blindspot.risk_models.departure import (
    DepartureReport,
    FileDepartureImpact,
    ServiceDepartureImpact,
)
from blindspot.risk_models.knowledge_decay import FileDecay


@dataclass
class _MockCompleter:
    payload: dict
    captured_user: str = ""
    captured_system: str = ""
    model: str = "mock-model"

    def complete(self, system: str, user: str) -> str:
        self.captured_system = system
        self.captured_user = user
        return json.dumps(self.payload)


def _service(name: str, bf: int, risk: str) -> ServiceBusFactor:
    return ServiceBusFactor(
        service=name, file_count=5, bus_factor=bf, threshold=0.8,
        risk_level=risk, top_owners=(("alice@x.com", 0.8),),
    )


def _decay(file: str, score: float) -> FileDecay:
    return FileDecay(
        file=file, top_owner="alice@x.com", top_owner_coverage=0.7,
        owner_last_touch=datetime.now(UTC), days_since_owner_touch=120,
        lines_changed_after=300, volatility=score, person_absence=score,
        decay_score=score, risk_level="critical" if score >= 0.75 else "high",
        projections={30: score, 60: score, 90: score},
    )


def _ctx_with_signals() -> ReportContext:
    services = (_service("payment", 1, "critical"),)
    decays = (_decay("legacy/old.py", 0.85),)
    resilience = ResilienceScoreEngine().compute(services, decays)
    rec = RecommendedAction(
        priority=ActionPriority.HIGH,
        category=ActionCategory.OWNERSHIP_DIVERSIFICATION,
        title="Diversify ownership of 'payment'",
        description="bus factor 1",
        target="payment",
        evidence="bf=1",
    )
    return ReportContext(
        repo_path="/tmp/x",
        generated_at=datetime.now(UTC),
        since_days=180,
        blindspot_version="0.0.1",
        commit_count=200,
        author_count=4,
        file_count=50,
        additions=1000,
        deletions=500,
        services=services,
        critical_files=(),
        decay_top=decays,
        decay_services=(),
        resilience=resilience,
        recommendations=(rec,),
    )


def test_narrative_engine_parses_clean_json():
    payload = {
        "executive_summary": "Overall resilience is critical; payment service has bus factor 1.",
        "headline_action": "Pair an additional engineer with the payment owner this week.",
        "rationales": {
            "payment": "Single-owner risk on a revenue-critical service.",
        },
    }
    mock = _MockCompleter(payload=payload)
    ctx = _ctx_with_signals()
    report = NarrativeEngine(client=mock).summarize(ctx, language="en")
    assert "payment service" in report.executive_summary
    assert "Pair" in report.headline_action
    assert report.rationales["payment"] == "Single-owner risk on a revenue-critical service."
    assert report.language == "en"


def test_narrative_engine_strips_markdown_fences():
    payload = {
        "executive_summary": "S", "headline_action": "A", "rationales": {},
    }

    @dataclass
    class FencedCompleter:
        model: str = "fenced"
        def complete(self, system: str, user: str) -> str:
            return "```json\n" + json.dumps(payload) + "\n```"

    report = NarrativeEngine(client=FencedCompleter()).summarize(_ctx_with_signals())
    assert report.executive_summary == "S"


def test_narrative_engine_extracts_json_with_trailing_chatter():
    payload = {"executive_summary": "S", "headline_action": "A", "rationales": {}}

    @dataclass
    class ChattyCompleter:
        model: str = "chatty"
        def complete(self, system: str, user: str) -> str:
            return "Sure, here is the JSON:\n" + json.dumps(payload) + "\nLet me know if you need more."

    report = NarrativeEngine(client=ChattyCompleter()).summarize(_ctx_with_signals())
    assert report.executive_summary == "S"


def test_prompt_includes_resilience_and_recommendations():
    ctx = _ctx_with_signals()
    user_prompt = build_user_prompt(ctx, language="en")
    assert "resilience" in user_prompt
    assert "payment" in user_prompt
    assert "legacy/old.py" in user_prompt
    assert "Diversify ownership" in user_prompt


def test_prompt_turkish_uses_turkish_instructions():
    ctx = _ctx_with_signals()
    prompt_tr = build_user_prompt(ctx, language="tr")
    assert "JSON" in prompt_tr
    assert ("Sadece JSON" in prompt_tr) or ("şema" in prompt_tr)


def test_prompt_omits_resilience_when_absent():
    ctx = _ctx_with_signals()
    from dataclasses import replace
    ctx2 = replace(ctx, resilience=None)
    user_prompt = build_user_prompt(ctx2, language="en")
    # No resilience block, but other fields still present
    assert "\"resilience\"" not in user_prompt
    assert "payment" in user_prompt


def test_config_picks_cli_over_yaml(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    # Redirect user config to a non-existent path so it cannot interfere.
    monkeypatch.setattr(
        "blindspot.narrative.config.USER_CONFIG_PATH",
        tmp_path / "absent.yaml",
    )
    # Run from a clean cwd so any real ./.blindspot.yaml in dev env is ignored.
    cwd_dir = tmp_path / "cwd"
    cwd_dir.mkdir()
    monkeypatch.chdir(cwd_dir)
    (tmp_path / ".blindspot.yaml").write_text(
        "narrative:\n  provider: anthropic\n  api_key: from-yaml\n  model: m-yaml\n"
    )
    cfg = load_narrative_config(
        repo_path=tmp_path,
        cli_api_key="from-cli",
        cli_model="m-cli",
        cli_provider=None,
    )
    assert cfg.api_key == "from-cli"
    assert cfg.model == "m-cli"
    assert cfg.provider == "anthropic"  # default


def test_config_falls_back_to_user_when_no_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    user_path = tmp_path / "user.yaml"
    user_path.write_text(
        "narrative:\n  provider: anthropic\n  api_key: from-user\n"
    )
    monkeypatch.setattr(
        "blindspot.narrative.config.USER_CONFIG_PATH", user_path
    )
    cwd_dir = tmp_path / "cwd"
    cwd_dir.mkdir()
    monkeypatch.chdir(cwd_dir)
    cfg = load_narrative_config(repo_path=tmp_path)
    assert cfg.api_key == "from-user"


def test_config_returns_empty_when_no_source_provides_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    # As of 0.0.3: missing api_key is valid — the caller (generate_narrative)
    # falls back to the rule-based narrator. Only YAML-parse errors raise.
    monkeypatch.setattr(
        "blindspot.narrative.config.USER_CONFIG_PATH", tmp_path / "absent.yaml"
    )
    cwd_dir = tmp_path / "cwd"
    cwd_dir.mkdir()
    monkeypatch.chdir(cwd_dir)
    cfg = load_narrative_config(repo_path=tmp_path)
    assert cfg.api_key == ""
    assert cfg.provider == "anthropic"  # default


def test_config_picks_cwd_over_scanned_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "blindspot.narrative.config.USER_CONFIG_PATH", tmp_path / "absent.yaml"
    )
    cwd_dir = tmp_path / "cwd"
    cwd_dir.mkdir()
    (cwd_dir / ".blindspot.yaml").write_text(
        "narrative:\n  provider: anthropic\n  api_key: from-cwd\n"
    )
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    (repo_dir / ".blindspot.yaml").write_text(
        "narrative:\n  provider: anthropic\n  api_key: from-repo\n"
    )
    monkeypatch.chdir(cwd_dir)
    cfg = load_narrative_config(repo_path=repo_dir)
    assert cfg.api_key == "from-cwd"


def test_config_reads_scanned_repo_when_cwd_has_none(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "blindspot.narrative.config.USER_CONFIG_PATH", tmp_path / "absent.yaml"
    )
    cwd_dir = tmp_path / "cwd"
    cwd_dir.mkdir()
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    (repo_dir / ".blindspot.yaml").write_text(
        "narrative:\n  provider: anthropic\n  api_key: from-repo\n"
    )
    monkeypatch.chdir(cwd_dir)
    cfg = load_narrative_config(repo_path=repo_dir)
    assert cfg.api_key == "from-repo"


def _departure_report() -> DepartureReport:
    files = (
        FileDepartureImpact(
            file="payment/billing.py", coverage_loss=1.0,
            remaining_top_owner=None, remaining_top_coverage=0.0,
            becomes_orphan=True, severity="critical",
        ),
        FileDepartureImpact(
            file="auth/legacy.py", coverage_loss=0.85,
            remaining_top_owner="bob@x.com", remaining_top_coverage=0.15,
            becomes_orphan=False, severity="high",
        ),
    )
    services = (
        ServiceDepartureImpact(
            service="payment", file_count=4, affected_files=4, orphaned_files=2,
            avg_coverage_loss=0.78, max_coverage_loss=1.0, severity="critical",
        ),
    )
    return DepartureReport(
        departing=("alice@x.com",),
        files=files, services=services,
        total_files=10, affected_files=2, orphaned_files=1,
        avg_coverage_loss=0.40,
    )


def test_departure_prompt_includes_names_and_metrics():
    report = _departure_report()
    names = {"alice@x.com": "Alice", "bob@x.com": "Bob"}
    prompt = build_departure_prompt(report, names, language="en")
    assert "Alice (alice@x.com)" in prompt
    assert "Bob (bob@x.com)" in prompt
    assert "payment" in prompt
    assert "payment/billing.py" in prompt
    assert "becomes_orphan" in prompt


def test_summarize_departure_parses_response():
    payload = {
        "executive_summary": "Alice's departure orphans payment/billing.py.",
        "headline_action": "Pair Bob with the payment team this sprint.",
        "mitigations": [
            "Schedule a knowledge transfer for payment/billing.py.",
            "Document the auth/legacy.py logic before Alice leaves.",
        ],
    }
    mock = _MockCompleter(payload=payload)
    report = _departure_report()
    out = NarrativeEngine(client=mock).summarize_departure(
        report, names={"alice@x.com": "Alice"}, language="en",
    )
    assert "orphans payment" in out.executive_summary
    assert out.mitigations == (
        "Schedule a knowledge transfer for payment/billing.py.",
        "Document the auth/legacy.py logic before Alice leaves.",
    )
    assert "Alice (alice@x.com)" in mock.captured_user
