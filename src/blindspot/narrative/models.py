from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class NarrativeReport:
    """LLM-generated narrative on top of the structured signals.

    All fields plain text/markdown — rendered as-is in HTML.
    `rationales` keys are recommendation `target` strings so we can splice
    one-liners next to each tabular action in the report.
    """
    executive_summary: str
    headline_action: str
    rationales: dict[str, str] = field(default_factory=dict)
    language: str = "en"
    model: str = ""


@dataclass(frozen=True, slots=True)
class DepartureNarrative:
    """LLM briefing on top of a departure simulation."""
    executive_summary: str
    headline_action: str
    mitigations: tuple[str, ...] = ()
    language: str = "en"
    model: str = ""
