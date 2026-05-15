"""generate_narrative() tier selection: cloud when key set, rule-based otherwise."""

from datetime import UTC, datetime

from blindspot import __version__
from blindspot.narrative.config import NarrativeConfig
from blindspot.narrative.engine import generate_narrative
from blindspot.report.context import ReportContext


def _empty_ctx() -> ReportContext:
    return ReportContext(
        repo_path="/tmp/r",
        generated_at=datetime.now(UTC),
        since_days=180,
        blindspot_version=__version__,
        commit_count=0, author_count=0, file_count=0,
        additions=0, deletions=0,
        services=(), critical_files=(), decay_top=(), decay_services=(),
    )


def test_generate_narrative_falls_back_to_rule_based_when_no_key():
    cfg = NarrativeConfig(provider="anthropic", api_key="", model="")
    nr = generate_narrative(cfg, _empty_ctx(), language="en")
    assert nr.model == "rule-based"


def test_generate_narrative_uses_cloud_when_key_set(monkeypatch):
    """When an api_key is configured, the cloud path is selected.

    We don't actually call the API here — only verify the selection logic
    by stubbing the client.complete to return a fake JSON response.
    """
    fake_json = (
        '{"executive_summary": "From cloud", '
        '"headline_action": "Act now", "rationales": {}}'
    )

    class _FakeClient:
        model = "fake-model"

        def complete(self, system, user):
            return fake_json

    # Patch build_client to return our fake client when called with a key
    import blindspot.narrative.engine as engine_mod

    def fake_build(provider, api_key, model):
        return _FakeClient() if api_key else None

    monkeypatch.setattr(engine_mod, "build_client", fake_build)

    cfg = NarrativeConfig(provider="anthropic", api_key="sk-test", model="")
    nr = generate_narrative(cfg, _empty_ctx(), language="en")
    assert nr.executive_summary == "From cloud"
    assert nr.headline_action == "Act now"
    assert nr.model == "fake-model"


def test_generate_narrative_respects_language():
    cfg = NarrativeConfig(provider="anthropic", api_key="", model="")
    nr = generate_narrative(cfg, _empty_ctx(), language="tr")
    assert nr.language == "tr"
    assert nr.model == "rule-based"
