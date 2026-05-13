from collections.abc import Iterable
from dataclasses import dataclass

from blindspot.ai_signal.models import (
    AIFlag,
    AISignal,
    AuthorProfile,
    AuthorProfileType,
    QualitySignal,
    SignalStrength,
)
from blindspot.collector.bots import is_bot_author
from blindspot.collector.models import Commit


def _evidence_weight(ai_flag: AIFlag, quality_risk: float) -> float:
    """Convert (AI flag, quality risk) to an evidence weight in [0.6, 1.0].

    The weight is applied as a multiplier on ownership scores. It expresses
    'how confident is the underlying activity signal' — never a punishment.
    """
    if ai_flag == AIFlag.LOW:
        return 1.0
    if ai_flag == AIFlag.MEDIUM:
        if quality_risk < 0.3:
            return 0.95
        if quality_risk >= 0.6:
            return 0.75
        return 0.85
    # AIFlag.HIGH
    if quality_risk < 0.3:
        return 0.90
    if quality_risk >= 0.6:
        return 0.60
    return 0.75


def _signal_strength_from_weight(weight: float) -> SignalStrength:
    if weight >= 0.90:
        return SignalStrength.STRONG
    if weight >= 0.75:
        return SignalStrength.MODERATE
    return SignalStrength.LOW


def _classify(ai_flag: AIFlag, quality_risk: float) -> AuthorProfileType:
    if ai_flag == AIFlag.LOW:
        return AuthorProfileType.REAL_GROWTH
    if quality_risk >= 0.6:
        return AuthorProfileType.FAKE_VELOCITY
    return AuthorProfileType.AI_AMPLIFIED_HEALTHY


def _explain(profile: AuthorProfileType, ai: AISignal, quality: QualitySignal | None) -> str:
    q_note = ""
    if quality is not None:
        if quality.risk_score > 0.6:
            q_note = " Quality signals (churn/bug-fix/revert) are elevated."
        elif quality.risk_score < 0.3:
            q_note = " Quality signals are stable."
        else:
            q_note = " Quality signals are mixed."

    if profile == AuthorProfileType.REAL_GROWTH:
        return "Activity matches baseline; output growth appears organic." + q_note
    if profile == AuthorProfileType.AI_AMPLIFIED_HEALTHY:
        return (
            "Activity signals (frequency/volume) above baseline."
            " Quality is preserved; verify before critical changes." + q_note
        )
    if profile == AuthorProfileType.FAKE_VELOCITY:
        return (
            "Activity sharply above baseline together with elevated quality risk."
            " Recommend deep code review of recent changes." + q_note
        )
    return "Insufficient data for a confident profile."


@dataclass
class AuthorProfiler:
    def profile(
        self,
        commits: Iterable[Commit],
        ai_signals: dict[str, AISignal],
        quality_signals: dict[str, QualitySignal],
    ) -> dict[str, AuthorProfile]:
        names: dict[str, str] = {}
        for c in commits:
            if c.author_name and c.author_email not in names:
                names[c.author_email] = c.author_name

        results: dict[str, AuthorProfile] = {}
        for email, ai in ai_signals.items():
            name = names.get(email, "")

            if is_bot_author(email, name):
                results[email] = AuthorProfile(
                    author_email=email,
                    author_name=name,
                    profile_type=AuthorProfileType.BOT,
                    signal_strength=SignalStrength.STRONG,
                    evidence_weight=1.0,
                    ai_signal=None,
                    quality_signal=None,
                    explanation=(
                        "Automated author (bot or AI agent). "
                        "Output is excluded from human knowledge attribution."
                    ),
                )
                continue

            quality = quality_signals.get(email)
            quality_risk = quality.risk_score if quality is not None else 0.0
            if ai.baseline_commits < 5:
                profile_type = AuthorProfileType.INSUFFICIENT_DATA
                weight = 1.0
                strength = SignalStrength.MODERATE
            else:
                profile_type = _classify(ai.flag, quality_risk)
                weight = _evidence_weight(ai.flag, quality_risk)
                strength = _signal_strength_from_weight(weight)

            results[email] = AuthorProfile(
                author_email=email,
                author_name=name,
                profile_type=profile_type,
                signal_strength=strength,
                evidence_weight=weight,
                ai_signal=ai,
                quality_signal=quality,
                explanation=_explain(profile_type, ai, quality),
            )
        return results


__all__ = ["AuthorProfiler"]
