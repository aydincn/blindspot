from datetime import UTC, datetime

from blindspot.resilience import ResilienceScoreEngine
from blindspot.resilience.score import ResilienceScore, letter_grade
from blindspot.review_graph.engine import FileReviewStats
from blindspot.risk_models.bus_factor import ServiceBusFactor
from blindspot.risk_models.knowledge_decay import FileDecay


def _service(name: str, bf: int, risk: str) -> ServiceBusFactor:
    return ServiceBusFactor(
        service=name, file_count=5, bus_factor=bf, threshold=0.8,
        risk_level=risk, top_owners=(("a@x.com", 0.7),),
    )


def _decay(file: str, score: float) -> FileDecay:
    return FileDecay(
        file=file, top_owner="a@x.com", top_owner_coverage=0.7,
        owner_last_touch=datetime.now(UTC), days_since_owner_touch=10,
        lines_changed_after=50, volatility=score, person_absence=score,
        decay_score=score,
        risk_level="critical" if score >= 0.75 else "medium",
        projections={30: score, 60: score, 90: score},
    )


def test_strong_repo_scores_high():
    services = [_service(s, bf=3, risk="healthy") for s in ("a", "b", "c")]
    decays = [_decay(f"f{i}.py", 0.1) for i in range(5)]
    score = ResilienceScoreEngine().compute(services, decays)
    assert score.overall >= 80
    assert score.band == "Strong"


def test_critical_concentration_drops_score():
    services = [_service(s, bf=1, risk="critical") for s in ("a", "b", "c")]
    decays = [_decay(f"f{i}.py", 0.5) for i in range(5)]
    score = ResilienceScoreEngine().compute(services, decays)
    assert score.ownership == 0
    assert score.overall < 40
    assert score.band == "Critical"


def test_high_decay_pulls_score_down():
    services = [_service(s, bf=3, risk="healthy") for s in ("a", "b")]
    decays = [_decay(f"f{i}.py", 0.85) for i in range(5)]
    score = ResilienceScoreEngine().compute(services, decays)
    assert score.decay is not None and score.decay < 25
    assert score.overall < 70


def test_review_subscore_uses_rubber_stamp_and_diversity():
    services = [_service("a", bf=3, risk="healthy")]
    decays = [_decay("f.py", 0.1)]
    stats = {
        "f.py": FileReviewStats(
            file="f.py", unique_reviewers=3, total_reviews=10, total_comments=8,
            rubber_stamp_ratio=0.1, diversity_hhi=0.7,
        )
    }
    score = ResilienceScoreEngine().compute(services, decays, review_stats=stats)
    assert score.review is not None and score.review > 60


def test_missing_sub_scores_renormalise_overall():
    services = [_service("a", bf=3, risk="healthy")]
    decays = [_decay("f.py", 0.1)]
    score = ResilienceScoreEngine().compute(services, decays)
    # No review_stats. Overall should be based purely on ownership+decay.
    assert score.review is None
    assert score.overall > 0


def test_no_data_returns_neutral():
    score = ResilienceScoreEngine().compute([], [])
    assert score.overall == 50
    assert "Insufficient" in score.summary


def test_band_thresholds():
    services = [_service(s, bf=3, risk="healthy") for s in ("a", "b")]
    decays = [_decay("f.py", 0.0)]
    score = ResilienceScoreEngine().compute(services, decays)
    assert score.band in ("Strong", "Moderate")


# ---------------------------------------------------------------------------
# Letter grades (0.0.5a)

def test_letter_grade_thresholds():
    assert letter_grade(95) == "A"
    assert letter_grade(85) == "B"
    assert letter_grade(75) == "C"
    assert letter_grade(65) == "D"
    assert letter_grade(50) == "F"
    assert letter_grade(0) == "F"
    assert letter_grade(None) is None


def test_resilience_score_letter_grade_properties():
    score = ResilienceScore(
        overall=72, ownership=95, decay=65, review=None,
        band="Moderate", summary="…",
    )
    assert score.overall_grade == "C"
    assert score.ownership_grade == "A"
    assert score.decay_grade == "D"
    assert score.review_grade is None
