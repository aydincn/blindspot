"""Hidden silo detection — services whose reviewer set is disjoint from
the rest of the org.

A silo here means: the same handful of reviewers always review one
service's PRs and never appear on other services'. That's tribal
knowledge — one cluster can ship, another can't read it.

MVP heuristic: for every pair of services, compute Jaccard overlap of
their reviewer sets. A service is "siloed" when its reviewers do not
appear at all in any other service with non-trivial review volume.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from blindspot.review_graph.engine import ReviewGraph
from blindspot.risk_models.bus_factor import top_level_dir


@dataclass(frozen=True, slots=True)
class SilosFinding:
    service: str
    reviewers: tuple[str, ...]
    review_count: int  # total reviews observed on this service
    other_services_with_overlap: int  # 0 = fully isolated


@dataclass(frozen=True, slots=True)
class SilosReport:
    findings: tuple[SilosFinding, ...]  # only isolated services
    services_analysed: int


def detect_silos(
    review_graph: ReviewGraph,
    *,
    service_of: Callable[[str], str] = top_level_dir,
    min_reviews_per_service: int = 5,
    min_unique_reviewers: int = 2,
) -> SilosReport:
    """Return services whose reviewer set is disjoint from every other
    service's. Services below ``min_reviews_per_service`` or
    ``min_unique_reviewers`` are excluded — there isn't enough signal to
    call them siloed.
    """
    per_service_reviewers: dict[str, set[str]] = {}
    per_service_reviews: dict[str, int] = {}
    for (reviewer, path), score in review_graph.by_reviewer_file.items():
        if score <= 0:
            continue
        svc = service_of(path)
        per_service_reviewers.setdefault(svc, set()).add(reviewer)
        per_service_reviews[svc] = per_service_reviews.get(svc, 0) + 1

    eligible = {
        svc: reviewers
        for svc, reviewers in per_service_reviewers.items()
        if per_service_reviews.get(svc, 0) >= min_reviews_per_service
        and len(reviewers) >= min_unique_reviewers
    }
    if len(eligible) < 2:
        return SilosReport(findings=(), services_analysed=len(eligible))

    findings: list[SilosFinding] = []
    for svc, reviewers in eligible.items():
        overlap_count = sum(
            1 for other_svc, other_reviewers in eligible.items()
            if other_svc != svc and (reviewers & other_reviewers)
        )
        if overlap_count == 0:
            findings.append(
                SilosFinding(
                    service=svc,
                    reviewers=tuple(sorted(reviewers)),
                    review_count=per_service_reviews[svc],
                    other_services_with_overlap=0,
                )
            )
    findings.sort(key=lambda f: -f.review_count)
    return SilosReport(
        findings=tuple(findings),
        services_analysed=len(eligible),
    )


__all__ = ["SilosFinding", "SilosReport", "detect_silos"]
