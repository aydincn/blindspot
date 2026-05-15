"""Narrative orchestrator.

Two tiers:
- **Cloud LLM** (Anthropic / OpenAI) — used when an api_key is configured.
  Produces fluent prose; output marked with the model id.
- **Rule-based** — deterministic Python over `ReportContext`. Used when
  no cloud key is available. Output marked `model="rule-based"`.

The HTML report inspects `NarrativeReport.model` and shows a small
upgrade hint when rule-based is used.
"""

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from blindspot.narrative.client import (
    NarrativeError,
    build_client,
)
from blindspot.narrative.config import NarrativeConfig
from blindspot.narrative.models import DepartureNarrative, NarrativeReport
from blindspot.narrative.prompt import (
    build_departure_prompt,
    build_user_prompt,
    departure_system_prompt,
    system_prompt,
)
from blindspot.narrative.rule_based import RuleBasedNarrator

if TYPE_CHECKING:
    from blindspot.report.context import ReportContext
    from blindspot.risk_models.departure import DepartureReport


class _Completer(Protocol):
    def complete(self, system: str, user: str) -> str: ...


def generate_narrative(
    cfg: NarrativeConfig,
    ctx: "ReportContext",
    language: str = "en",
) -> NarrativeReport:
    """Top-level narrative entry point.

    If `cfg.api_key` is set, use the cloud provider (Anthropic / OpenAI)
    and emit fluent prose. Otherwise fall back to the rule-based
    narrator — deterministic, no network, always available.
    """
    client = build_client(cfg.provider, cfg.api_key, cfg.model)
    if client is None:
        return RuleBasedNarrator(language=language).summarize(ctx)
    return NarrativeEngine(client=client).summarize(ctx, language=language)


@dataclass
class NarrativeEngine:
    client: _Completer
    model: str = ""

    def summarize(self, ctx: "ReportContext", language: str = "en") -> NarrativeReport:
        sys_msg = system_prompt(language)
        user_msg = build_user_prompt(ctx, language)
        raw = self.client.complete(sys_msg, user_msg)

        parsed = _parse_json_response(raw)
        rationales_raw = parsed.get("rationales") or {}
        rationales = {
            str(k): str(v).strip()
            for k, v in rationales_raw.items()
            if isinstance(v, (str, int, float)) and str(v).strip()
        }
        model_id = getattr(self.client, "model", "") or self.model
        return NarrativeReport(
            executive_summary=str(parsed.get("executive_summary", "")).strip(),
            headline_action=str(parsed.get("headline_action", "")).strip(),
            rationales=rationales,
            language=language,
            model=model_id,
        )

    def summarize_departure(
        self,
        report: "DepartureReport",
        names: dict[str, str],
        language: str = "en",
    ) -> DepartureNarrative:
        sys_msg = departure_system_prompt(language)
        user_msg = build_departure_prompt(report, names, language)
        raw = self.client.complete(sys_msg, user_msg)
        parsed = _parse_json_response(raw)
        mitigations_raw = parsed.get("mitigations") or []
        mitigations = tuple(
            str(m).strip() for m in mitigations_raw
            if isinstance(m, (str, int, float)) and str(m).strip()
        )
        return DepartureNarrative(
            executive_summary=str(parsed.get("executive_summary", "")).strip(),
            headline_action=str(parsed.get("headline_action", "")).strip(),
            mitigations=mitigations,
            language=language,
            model=getattr(self.client, "model", "") or self.model,
        )


def _parse_json_response(raw: str) -> dict:
    s = raw.strip()
    # Strip ```json fences if the model produced them despite the instruction.
    if s.startswith("```"):
        s = s.strip("`")
        if s.lower().startswith("json"):
            s = s[4:].lstrip()
        if s.endswith("```"):
            s = s[:-3]
        s = s.strip()
    try:
        data = json.loads(s)
    except json.JSONDecodeError as e:
        # Last-ditch: try to extract the outermost {...} block.
        start = s.find("{")
        end = s.rfind("}")
        if start >= 0 and end > start:
            try:
                data = json.loads(s[start : end + 1])
            except json.JSONDecodeError:
                raise NarrativeError(f"LLM did not return valid JSON: {e}") from e
        else:
            raise NarrativeError(f"LLM did not return valid JSON: {e}") from e
    if not isinstance(data, dict):
        raise NarrativeError("LLM response was not a JSON object.")
    return data


__all__ = ["NarrativeEngine"]
