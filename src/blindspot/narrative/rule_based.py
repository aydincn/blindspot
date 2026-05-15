"""Rule-based narrator — deterministic NarrativeReport from a ReportContext.

This is the Tier-0 narrative provider in blindspot. It needs no API key,
no network, no model file — pure Python over the same `ReportContext`
the HTML template renders. Output is information-dense rather than
prose-fluent (an LLM tier exists for that).

Outputs are bilingual: `language="en"` or `language="tr"`. Adding a
language means extending the `_LABELS` and `_TEMPLATES` dicts.

The HTML report identifies this tier by `NarrativeReport.model ==
"rule-based"` and renders a small footer hint inviting the reader to
upgrade to a cloud LLM.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING

from blindspot.narrative.models import NarrativeReport

if TYPE_CHECKING:
    from blindspot.report.context import ReportContext


_LABELS: dict[str, dict[str, str]] = {
    "en": {
        "band_strong": "Strong",
        "band_moderate": "Moderate",
        "band_fragile": "Fragile",
        "band_critical": "Critical",
        "dim_ownership": "ownership concentration",
        "dim_decay": "knowledge decay",
        "dim_review": "review hygiene",
        "dim_activity": "author activity signals",
        "verdict_score": "Resilience is **{band}** ({score}/100).",
        "verdict_weakest": "Weakest dimension: {dim}.",
        "para_counts_lead": "Risk inventory:",
        "para_counts_services": "{n} service(s) rest on a single contributor",
        "para_counts_decay": "{n} file(s) are decaying critically",
        "para_counts_orphans": "{n} file(s) would become orphans if the top contributor leaves",
        "para_counts_rubber": "{n} file(s) carry rubber-stamp review patterns",
        "para_recommendation": "Top recommended action: {action}",
        "headline_pair": "Pair {owner} on '{service}' — bus factor 1 across {n} files",
        "headline_orphan": "Establish a successor for {owner}'s work — {n} files would orphan without them",
        "headline_review": "Add review depth requirement for '{file}' — {pct}% of approvals leave no substantive comment",
        "headline_decay": "Knowledge transfer for '{file}' — {pct}% decay, owner away {days} days",
        "headline_velocity": "Deep review of recent work by {author} — output spike paired with elevated quality risk",
        "headline_healthy": "No critical concentrations detected — maintain current ownership distribution",
        "rationale_decay": "Decay {pct}% — owner last touched {days} days ago, {lines} lines changed by others since.",
        "rationale_bus": "Bus factor 1 over {n} files — {owner} holds {pct}% of effective ownership.",
        "rationale_rubber": "{pct}% of approvals on this file arrived without a substantive review comment ({n} reviews).",
        "rationale_diversity": "Reviewer concentration HHI {pct}% — one reviewer carries most of this file's review load.",
        "rationale_fast": "Median approval latency {minutes} minutes over {n} samples — too short for substantive review.",
        "rationale_velocity": "Recent activity shape shifted sharply versus the author's own baseline, with elevated quality risk.",
        "rationale_codeowners_mismatch": "Declared owner does not include the actual top contributor ({owner} at {pct}% coverage).",
        "rationale_codeowners_stale": "Declared owner has not touched this file recently.",
    },
    "tr": {
        "band_strong": "Güçlü",
        "band_moderate": "Orta",
        "band_fragile": "Kırılgan",
        "band_critical": "Kritik",
        "dim_ownership": "sahiplik yoğunlaşması",
        "dim_decay": "bilgi erozyonu",
        "dim_review": "review hijyeni",
        "dim_activity": "yazar aktivite sinyalleri",
        "verdict_score": "Resilience **{band}** ({score}/100).",
        "verdict_weakest": "En zayıf boyut: {dim}.",
        "para_counts_lead": "Risk envanteri:",
        "para_counts_services": "{n} servis tek kişiye bağlı",
        "para_counts_decay": "{n} dosyada kritik bilgi erozyonu",
        "para_counts_orphans": "Top katkı sağlayan ayrılırsa {n} dosya sahipsiz kalır",
        "para_counts_rubber": "{n} dosyada rubber-stamp review pattern'i",
        "para_recommendation": "En öncelikli aksiyon: {action}",
        "headline_pair": "{owner}'i '{service}' servisinde eşle — bus factor 1, {n} dosya",
        "headline_orphan": "{owner} için halef belirle — ayrılırsa {n} dosya sahipsiz kalır",
        "headline_review": "'{file}' için review derinliği zorunlu kıl — onayların %{pct}'i yorumsuz geçiyor",
        "headline_decay": "'{file}' için bilgi transferi — %{pct} decay, owner {days} gündür dosyaya dokunmamış",
        "headline_velocity": "{author}'un son işlerini derin review'a al — output spike + yükselmiş kalite riski",
        "headline_healthy": "Kritik yoğunlaşma tespit edilmedi — mevcut sahiplik dağılımını koru",
        "rationale_decay": "Decay %{pct} — owner {days} gün önce dokundu, sonra başkaları {lines} satır değiştirdi.",
        "rationale_bus": "{n} dosya üzerinde bus factor 1 — {owner} sahiplik payı %{pct}.",
        "rationale_rubber": "Bu dosyadaki onayların %{pct}'i yorumsuz geçti ({n} review).",
        "rationale_diversity": "Reviewer yoğunlaşma HHI %{pct} — tek bir reviewer review yükünün çoğunu taşıyor.",
        "rationale_fast": "Median onay süresi {minutes} dakika ({n} örnek) — substansiyel review için fazla kısa.",
        "rationale_velocity": "Yazarın yakın aktivite şekli kendi baseline'ından sertçe sapmış, kalite riski yükselmiş.",
        "rationale_codeowners_mismatch": "Bildirilen owner gerçek top katkı sağlayanı içermiyor ({owner} %{pct} sahiplik).",
        "rationale_codeowners_stale": "Bildirilen owner bu dosyaya yakın zamanda dokunmamış.",
    },
}


def _label(language: str, key: str) -> str:
    lang = language if language in _LABELS else "en"
    return _LABELS[lang].get(key, _LABELS["en"].get(key, key))


@dataclass
class RuleBasedNarrator:
    """Generates NarrativeReport entirely from ReportContext.

    No LLM, no network, no model. The HTML report identifies this tier by
    `NarrativeReport.model == "rule-based"` and shows a small upgrade hint.
    """
    language: str = "en"

    def summarize(self, ctx: "ReportContext") -> NarrativeReport:
        headline = self._headline(ctx)
        summary = self._executive_summary(ctx, headline)
        rationales = self._rationales(ctx)
        return NarrativeReport(
            executive_summary=summary,
            headline_action=headline,
            rationales=rationales,
            language=self.language,
            model="rule-based",
        )

    # ------------------------------------------------------------------
    # Headline picker — priority-ordered

    def _headline(self, ctx: "ReportContext") -> str:
        L = self.language

        # 1. Critical service bus factor (≥3 files preferred — meaningful service)
        critical_service = self._worst_single_owner_service(ctx)
        if critical_service is not None:
            service, owner_email, n_files = critical_service
            return _label(L, "headline_pair").format(
                owner=ctx.label(owner_email), service=service, n=n_files,
            )

        # 2. Worst departure scenario with many orphans
        orphan_scenario = self._worst_orphan_departure(ctx)
        if orphan_scenario is not None:
            owner_email, orphan_count = orphan_scenario
            return _label(L, "headline_orphan").format(
                owner=ctx.label(owner_email), n=orphan_count,
            )

        # 3. Worst rubber-stamp file (review-without-scrutiny on important file)
        worst_rubber = self._worst_rubber_stamp(ctx)
        if worst_rubber is not None:
            file, ratio = worst_rubber
            return _label(L, "headline_review").format(
                file=file, pct=int(round(ratio * 100)),
            )

        # 4. Worst decay file
        worst_decay = self._worst_decay(ctx)
        if worst_decay is not None:
            file, score, days = worst_decay
            return _label(L, "headline_decay").format(
                file=file, pct=int(round(score * 100)), days=int(days),
            )

        # 5. Fake-velocity author
        fake_velocity = self._fake_velocity_author(ctx)
        if fake_velocity is not None:
            return _label(L, "headline_velocity").format(author=fake_velocity)

        # 6. Healthy fallback
        return _label(L, "headline_healthy")

    # ------------------------------------------------------------------
    # Executive summary — band + counts + top recommendation

    def _executive_summary(self, ctx: "ReportContext", headline: str) -> str:
        L = self.language
        paragraphs: list[str] = []

        # Para 1: verdict
        if ctx.resilience is not None:
            band_key = "band_" + ctx.resilience.band.lower()
            band_label = _label(L, band_key)
            verdict = _label(L, "verdict_score").format(
                band=band_label, score=ctx.resilience.overall,
            )
            weakest = self._weakest_dimension(ctx)
            if weakest:
                verdict += " " + _label(L, "verdict_weakest").format(dim=weakest)
            paragraphs.append(verdict)

        # Para 2: counts
        counts = self._risk_counts(ctx)
        if counts:
            lead = _label(L, "para_counts_lead")
            paragraphs.append(lead + " " + "; ".join(counts) + ".")

        # Para 3: top recommendation = the headline (which already summarises it)
        paragraphs.append(_label(L, "para_recommendation").format(action=headline))

        return "\n\n".join(paragraphs)

    # ------------------------------------------------------------------
    # Rationales — one line per recommendation target

    def _rationales(self, ctx: "ReportContext") -> dict[str, str]:
        L = self.language
        out: dict[str, str] = {}
        for action in ctx.recommendations:
            line = self._rationale_for(L, action, ctx)
            if line:
                out[action.target] = line
        return out

    def _rationale_for(self, L: str, action, ctx: "ReportContext") -> str | None:
        # Use the recommendation's evidence field to fill a templated line
        # — the evidence text already has the numbers, we just give it
        # human-friendly framing in the chosen language.
        from blindspot.actions.models import ActionCategory, FragilityPattern

        cat = action.category
        ev = action.evidence
        if action.pattern == FragilityPattern.SINGLE_OWNER_CONCENTRATION:
            # evidence: "bus_factor=1, top_owner_coverage=XX%, files=NN"
            pct = _extract_pct(ev, "top_owner_coverage")
            n = _extract_int(ev, "files")
            # Find the actual top owner from services for nicer phrasing
            owner_label = action.target
            for s in ctx.services:
                if s.service == action.target and s.top_owners:
                    owner_label = ctx.label(s.top_owners[0][0])
                    break
            return _label(L, "rationale_bus").format(n=n, owner=owner_label, pct=pct)
        if action.pattern == FragilityPattern.REVIEW_WITHOUT_SCRUTINY:
            if "rubber_stamp_ratio" in ev:
                pct = _extract_pct(ev, "rubber_stamp_ratio")
                n = _extract_int(ev, "reviews")
                return _label(L, "rationale_rubber").format(pct=pct, n=n)
            if "median_approval" in ev:
                minutes = _extract_int(ev, "median_approval")
                n = _extract_int(ev, "samples")
                return _label(L, "rationale_fast").format(minutes=minutes, n=n)
        if action.pattern == FragilityPattern.VELOCITY_WITHOUT_REVIEW:
            return _label(L, "rationale_velocity")
        if cat == ActionCategory.KNOWLEDGE_TRANSFER:
            pct = _extract_pct(ev, "decay")
            days = _extract_int(ev, "days_since_touch")
            lines = _extract_int(ev, "lines_after")
            return _label(L, "rationale_decay").format(pct=pct, days=days, lines=lines)
        if cat == ActionCategory.REVIEW_HYGIENE and "diversity_hhi" in ev:
            pct = _extract_pct(ev, "diversity_hhi")
            return _label(L, "rationale_diversity").format(pct=pct)
        if cat == ActionCategory.CODEOWNERS_UPDATE:
            if "actual_top=" in ev and "coverage=" in ev:
                owner_email = _extract_token(ev, "actual_top")
                pct = _extract_pct(ev, "coverage")
                owner_label = (
                    ctx.label(owner_email) if owner_email and owner_email != "n/a" else "unknown"
                )
                return _label(L, "rationale_codeowners_mismatch").format(
                    owner=owner_label, pct=pct,
                )
            return _label(L, "rationale_codeowners_stale")
        return None

    # ------------------------------------------------------------------
    # Picker helpers

    def _worst_single_owner_service(self, ctx) -> tuple[str, str, int] | None:
        # Service bus factor 1 with the most files, ignoring "(config)" / "(root)" / "(other)"
        candidates = [
            s for s in ctx.services
            if s.bus_factor == 1 and s.top_owners
            and not (s.service.startswith("(") and s.service.endswith(")"))
        ]
        if not candidates:
            return None
        worst = max(candidates, key=lambda s: s.file_count)
        return worst.service, worst.top_owners[0][0], worst.file_count

    def _worst_orphan_departure(self, ctx) -> tuple[str, int] | None:
        # Departure scenario with the most orphan-becoming files
        scenarios = [s for s in ctx.departure_scenarios if s.orphaned_files > 0]
        if not scenarios:
            return None
        worst = max(scenarios, key=lambda s: s.orphaned_files)
        if not worst.departing:
            return None
        return worst.departing[0], worst.orphaned_files

    def _worst_rubber_stamp(self, ctx) -> tuple[str, float] | None:
        rs = sorted(
            (s for s in ctx.top_rubber_stamps if s.rubber_stamp_ratio >= 0.70),
            key=lambda s: -s.rubber_stamp_ratio,
        )
        if not rs:
            return None
        return rs[0].file, rs[0].rubber_stamp_ratio

    def _worst_decay(self, ctx) -> tuple[str, float, float] | None:
        critical = [d for d in ctx.decay_top if d.decay_score >= 0.75]
        if not critical:
            return None
        worst = critical[0]  # decay_top is already sorted desc
        return worst.file, worst.decay_score, worst.days_since_owner_touch

    def _fake_velocity_author(self, ctx) -> str | None:
        from blindspot.ai_signal.models import AuthorProfileType
        for p in ctx.author_profiles:
            if p.profile_type == AuthorProfileType.FAKE_VELOCITY:
                return p.author_name or p.author_email
        return None

    # ------------------------------------------------------------------
    # Risk counts (for executive summary paragraph 2)

    def _risk_counts(self, ctx) -> list[str]:
        L = self.language
        out: list[str] = []
        single_owner = sum(
            1 for s in ctx.services
            if s.bus_factor == 1
            and not (s.service.startswith("(") and s.service.endswith(")"))
        )
        if single_owner:
            out.append(_label(L, "para_counts_services").format(n=single_owner))

        critical_decay = sum(1 for d in ctx.decay_top if d.decay_score >= 0.75)
        if critical_decay:
            out.append(_label(L, "para_counts_decay").format(n=critical_decay))

        worst_scenario_orphans = max(
            (s.orphaned_files for s in ctx.departure_scenarios), default=0
        )
        if worst_scenario_orphans:
            out.append(_label(L, "para_counts_orphans").format(n=worst_scenario_orphans))

        rubber_count = sum(
            1 for s in ctx.top_rubber_stamps if s.rubber_stamp_ratio >= 0.70
        )
        if rubber_count:
            out.append(_label(L, "para_counts_rubber").format(n=rubber_count))

        return out

    def _weakest_dimension(self, ctx) -> str | None:
        if ctx.resilience is None:
            return None
        L = self.language
        subs = {
            "ownership": ctx.resilience.ownership,
            "decay": ctx.resilience.decay,
            "review": ctx.resilience.review,
            "activity": ctx.resilience.activity,
        }
        available = {k: v for k, v in subs.items() if v is not None}
        if not available:
            return None
        weakest = min(available.items(), key=lambda kv: kv[1])[0]
        return _label(L, "dim_" + weakest)


# ----------------------------------------------------------------------
# Tiny parsing helpers — read numbers back from the recommender's
# `evidence` strings without making the recommender expose typed data.

def _extract_pct(text: str, key: str) -> int:
    # Patterns like "key=12%" or "key=0.42" in the evidence string.
    import re
    m = re.search(rf"{re.escape(key)}=([0-9]+(?:\.[0-9]+)?)%?", text)
    if not m:
        return 0
    val = float(m.group(1))
    if val <= 1.0:
        val *= 100
    return int(round(val))


def _extract_int(text: str, key: str) -> int:
    import re
    m = re.search(rf"{re.escape(key)}=([0-9]+)", text)
    return int(m.group(1)) if m else 0


def _extract_token(text: str, key: str) -> str:
    import re
    m = re.search(rf"{re.escape(key)}=([^,\s]+)", text)
    return m.group(1) if m else ""


__all__ = ["RuleBasedNarrator"]
