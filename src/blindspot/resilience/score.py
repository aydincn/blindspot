"""Composite Engineering Resilience Score (0–100).

Combines four sub-scores into a single number a non-technical stakeholder can
track over time. Each sub-score is 0–100, higher = healthier. Sub-scores that
have no data are excluded from the weighted average rather than treated as 0.
"""

from dataclasses import dataclass
from typing import Iterable

from blindspot.ai_signal.models import AuthorProfile, AuthorProfileType
from blindspot.review_graph.engine import FileReviewStats
from blindspot.risk_models.bus_factor import ServiceBusFactor
from blindspot.risk_models.knowledge_decay import FileDecay


# Sub-score weights when all signals are present.
DEFAULT_WEIGHTS = {
    "ownership": 0.35,
    "decay": 0.30,
    "review": 0.20,
    "activity": 0.15,
}


@dataclass(frozen=True, slots=True)
class ResilienceScore:
    overall: int
    ownership: int | None
    decay: int | None
    review: int | None
    activity: int | None
    band: str
    summary: str

    @property
    def sub_scores(self) -> dict[str, int | None]:
        return {
            "ownership": self.ownership,
            "decay": self.decay,
            "review": self.review,
            "activity": self.activity,
        }


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
        author_profiles: dict[str, AuthorProfile] | None = None,
    ) -> ResilienceScore:
        services = tuple(services)
        decays = tuple(decays)

        ownership = self._ownership_score(services)
        decay = self._decay_score(decays)
        review = self._review_score(review_stats) if review_stats else None
        activity = self._activity_score(author_profiles) if author_profiles else None

        components = {
            "ownership": ownership,
            "decay": decay,
            "review": review,
            "activity": activity,
        }
        available = {k: v for k, v in components.items() if v is not None}
        if not available:
            return ResilienceScore(
                overall=50,
                ownership=ownership,
                decay=decay,
                review=review,
                activity=activity,
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
            activity=activity,
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

    def _activity_score(self, profiles: dict[str, AuthorProfile]) -> int | None:
        # Excludes bots and insufficient-data authors from the denominator.
        relevant = [
            p
            for p in profiles.values()
            if p.profile_type
            not in (AuthorProfileType.BOT, AuthorProfileType.INSUFFICIENT_DATA)
        ]
        if not relevant:
            return None
        bad = sum(1 for p in relevant if p.profile_type == AuthorProfileType.FAKE_VELOCITY)
        ratio_good = 1 - bad / len(relevant)
        return int(round(ratio_good * 100))


def _summary(overall: int, available: dict[str, int]) -> str:
    band = _band(overall)
    weakest = min(available.items(), key=lambda kv: kv[1])
    weakest_label = {
        "ownership": "ownership concentration",
        "decay": "knowledge decay",
        "review": "review hygiene",
        "activity": "author activity signals",
    }[weakest[0]]
    return (
        f"{band} resilience overall (score {overall}). "
        f"Weakest dimension: {weakest_label} at {weakest[1]}."
    )


__all__ = ["DEFAULT_WEIGHTS", "ResilienceScore", "ResilienceScoreEngine"]
