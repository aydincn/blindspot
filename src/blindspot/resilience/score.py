"""Composite Engineering Resilience Score (0–100).

Combines three sub-scores into a single number a non-technical stakeholder can
track over time. Each sub-score is 0–100, higher = healthier. Sub-scores that
have no data are excluded from the weighted average rather than treated as 0.
"""

from dataclasses import dataclass
from typing import Iterable

from blindspot.review_graph.engine import FileReviewStats
from blindspot.risk_models.bus_factor import ServiceBusFactor
from blindspot.risk_models.knowledge_decay import FileDecay


# Sub-score weights when all signals are present.
DEFAULT_WEIGHTS = {
    "ownership": 0.40,
    "decay": 0.35,
    "review": 0.25,
}


def letter_grade(score: int | None) -> str | None:
    """Map a 0–100 sub-score to a letter grade (A–F). Returns None for None."""
    if score is None:
        return None
    if score >= 90:
        return "A"
    if score >= 80:
        return "B"
    if score >= 70:
        return "C"
    if score >= 60:
        return "D"
    return "F"


@dataclass(frozen=True, slots=True)
class ResilienceScore:
    overall: int
    ownership: int | None
    decay: int | None
    review: int | None
    band: str
    summary: str

    @property
    def sub_scores(self) -> dict[str, int | None]:
        return {
            "ownership": self.ownership,
            "decay": self.decay,
            "review": self.review,
        }

    @property
    def overall_grade(self) -> str:
        return letter_grade(self.overall) or "F"

    @property
    def ownership_grade(self) -> str | None:
        return letter_grade(self.ownership)

    @property
    def decay_grade(self) -> str | None:
        return letter_grade(self.decay)

    @property
    def review_grade(self) -> str | None:
        return letter_grade(self.review)


def _band(score: int) -> str:
    if score >= 80:
        return "Strong"
    if score >= 60:
        return "Moderate"
    if score >= 40:
        return "Fragile"
    return "Critical"


@dataclass
class ResilienceScoreEngine:
    weights: dict[str, float] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.weights is None:
            self.weights = dict(DEFAULT_WEIGHTS)

    def compute(
        self,
        services: Iterable[ServiceBusFactor],
        decays: Iterable[FileDecay],
        review_stats: dict[str, FileReviewStats] | None = None,
    ) -> ResilienceScore:
        services = tuple(services)
        decays = tuple(decays)

        ownership = self._ownership_score(services)
        decay = self._decay_score(decays)
        review = self._review_score(review_stats) if review_stats else None

        components = {
            "ownership": ownership,
            "decay": decay,
            "review": review,
        }
        available = {k: v for k, v in components.items() if v is not None}
        if not available:
            return ResilienceScore(
                overall=50,
                ownership=ownership,
                decay=decay,
                review=review,
                band="Moderate",
                summary="Insufficient data to compute resilience.",
            )

        weight_sum = sum(self.weights[k] for k in available)
        overall = sum(self.weights[k] * v for k, v in available.items()) / weight_sum
        overall_int = int(round(overall))

        return ResilienceScore(
            overall=overall_int,
            ownership=ownership,
            decay=decay,
            review=review,
            band=_band(overall_int),
            summary=_summary(overall_int, available),
        )

    def _ownership_score(self, services: tuple[ServiceBusFactor, ...]) -> int | None:
        if not services:
            return None
        # Healthy = bus factor >= 2 (more than one person carries the service).
        healthy = sum(1 for s in services if s.bus_factor >= 2)
        ratio = healthy / len(services)
        # Slight penalty for any critical-services even if most are healthy.
        critical = sum(1 for s in services if s.risk_level == "critical")
        crit_penalty = min(0.30, critical * 0.05)
        score = max(0.0, ratio - crit_penalty) * 100
        return int(round(score))

    def _decay_score(self, decays: tuple[FileDecay, ...]) -> int | None:
        if not decays:
            return None
        avg = sum(d.decay_score for d in decays) / len(decays)
        return int(round((1 - avg) * 100))

    def _review_score(self, stats: dict[str, FileReviewStats]) -> int | None:
        if not stats:
            return None
        # Average two indicators: 1 - rubber_stamp, and diversity.
        files = [s for s in stats.values() if s.total_reviews > 0]
        if not files:
            return None
        avg_rs = sum(s.rubber_stamp_ratio for s in files) / len(files)
        avg_div = sum(s.diversity_hhi for s in files) / len(files)
        score = ((1 - avg_rs) * 0.6 + avg_div * 0.4) * 100
        return int(round(score))


def _summary(overall: int, available: dict[str, int]) -> str:
    band = _band(overall)
    weakest = min(available.items(), key=lambda kv: kv[1])
    weakest_label = {
        "ownership": "ownership concentration",
        "decay": "knowledge decay",
        "review": "review hygiene",
    }[weakest[0]]
    return (
        f"{band} resilience overall (score {overall}). "
        f"Weakest dimension: {weakest_label} at {weakest[1]}."
    )


__all__ = [
    "DEFAULT_WEIGHTS",
    "ResilienceScore",
    "ResilienceScoreEngine",
    "letter_grade",
]
