"""Business implication mapper — turn signals into CTO-language.

The structured signals (resilience score, departure orphans, correction
load, AI-readiness gaps) are accurate but not how an executive reads
risk. They read it in *delivery, confidence, velocity, risk* terms.

This mapper is a deterministic translator: given the relevant signal
counts from a ReportContext, it picks the single most resonant
"business implication" sentence. Returns ``None`` when no signal is
strong enough to claim — better silence than a hedged sentence.

Profile-aware: founder-led and single-maintainer profiles get softer
language (concentration is structural there, not surprising).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from blindspot.report.context import ReportContext


_DELIVERY_THRESHOLD_ORPHANS = 25
_DELIVERY_THRESHOLD_BUS_FACTOR_SERVICES = 3
_CORRECTION_LOAD_THRESHOLD_FILES = 5
_REVIEW_RUBBER_THRESHOLD = 3


_EN = {
    "delivery_orphans_founder": (
        "An unexpected departure of the dominant contributor would orphan "
        "{n} critical files — this is structural for a single-maintainer "
        "project, but it is what successor planning must address first."
    ),
    "delivery_orphans_team": (
        "An unexpected departure of the top contributor would orphan {n} "
        "critical files and likely slow feature delivery by 3–5 weeks "
        "while the team learns the surface."
    ),
    "delivery_services": (
        "{n} services rest on a single contributor — if one of them "
        "leaves, the cost lands as delivery slowdown plus knowledge "
        "rebuild time on whichever service was theirs."
    ),
    "stability_correction": (
        "Operational confidence is likely decreasing despite shipping "
        "velocity: {n} files carry high correction load (≥ 35% of recent "
        "commits are fixes or reverts)."
    ),
    "review_theatre": (
        "Code review on {n} files is happening on paper but not in "
        "substance (rubber-stamp pattern), so quality is held by the "
        "author rather than the team."
    ),
    "ai_onboarding_gap": (
        "AI-assisted onboarding cannot soften a departure here — {n} "
        "services lack the operational context (CLAUDE.md, specs, ADRs) "
        "a new contributor or agent would load first."
    ),
    "doc_only_caveat": (
        "Code surface is too small for confident structural claims; "
        "treat any concentration signal as informational only."
    ),
}

_TR = {
    "delivery_orphans_founder": (
        "Dominant katkı sağlayanın beklenmedik ayrılışı {n} kritik "
        "dosyayı sahipsiz bırakır — tek-maintainer projeleri için "
        "yapısal, ama halef planlamasının ilk gündem maddesi."
    ),
    "delivery_orphans_team": (
        "Top katkı sağlayanın beklenmedik ayrılışı {n} kritik dosyayı "
        "sahipsiz bırakır ve ekibin yüzeyi öğrenmesi sürerken feature "
        "teslimatı 3–5 hafta yavaşlayabilir."
    ),
    "delivery_services": (
        "{n} servis tek katkı sağlayana bağlı — biri ayrılırsa maliyet "
        "kendi servisinde teslimat yavaşlaması + bilgi yeniden inşa "
        "süresi olarak ortaya çıkar."
    ),
    "stability_correction": (
        "Velocity'ye rağmen operasyonel güven muhtemelen düşüyor: {n} "
        "dosyaya gelen son commitlerin ≥ %35'i fix veya revert."
    ),
    "review_theatre": (
        "{n} dosyada code review kağıt üstünde yapılıyor ama özde değil "
        "(rubber-stamp); kalite ekipte değil, yazarda tutulu."
    ),
    "ai_onboarding_gap": (
        "AI destekli onboarding burada ayrılışı yumuşatamaz — {n} "
        "servis yeni bir katkı sağlayanın (veya agent'ın) ilk "
        "yükleyeceği operasyonel context'i (CLAUDE.md, specs, ADR) "
        "taşımıyor."
    ),
    "doc_only_caveat": (
        "Kod yüzeyi yapısal iddialar için fazla küçük; yoğunlaşma "
        "sinyallerini sadece bilgilendirici kabul et."
    ),
}


def _labels(language: str) -> dict[str, str]:
    return _TR if language == "tr" else _EN


def business_implication(ctx: "ReportContext", *, language: str = "en") -> str | None:
    """Pick the strongest single business-implication sentence for this
    context. Returns ``None`` if no signal is strong enough.

    Priority order (highest first):
      1. Delivery cost from departure orphans (profile-aware language)
      2. Multiple single-owner services
      3. Stability debt from correction load
      4. Review theatre
      5. AI-onboarding gap as the lone hit

    Doc-only repos get the caveat sentence regardless.
    """
    L = _labels(language)
    profile = ctx.repo_profile

    if profile == "doc-only":
        return L["doc_only_caveat"]

    # 1. Departure orphans — the loudest delivery-language signal.
    worst_orphans = max(
        (s.orphaned_files for s in ctx.departure_scenarios), default=0
    )
    if worst_orphans >= _DELIVERY_THRESHOLD_ORPHANS:
        if profile in ("single-maintainer", "founder-led"):
            return L["delivery_orphans_founder"].format(n=worst_orphans)
        return L["delivery_orphans_team"].format(n=worst_orphans)

    # 2. Multiple single-owner services
    single_owner_services = sum(
        1 for s in ctx.services
        if s.bus_factor == 1
        and not (s.service.startswith("(") and s.service.endswith(")"))
        and s.file_count >= 3
    )
    if single_owner_services >= _DELIVERY_THRESHOLD_BUS_FACTOR_SERVICES:
        return L["delivery_services"].format(n=single_owner_services)

    # 3. Stability debt
    correction_files = sum(
        1 for f in ctx.correction_load_files if f.correction_ratio >= 0.35
    )
    if correction_files >= _CORRECTION_LOAD_THRESHOLD_FILES:
        return L["stability_correction"].format(n=correction_files)

    # 4. Review theatre
    rubber_files = sum(
        1 for s in ctx.top_rubber_stamps if s.rubber_stamp_ratio >= 0.70
    )
    if rubber_files >= _REVIEW_RUBBER_THRESHOLD:
        return L["review_theatre"].format(n=rubber_files)

    # 5. AI-onboarding gap as the lone hit
    if ctx.ai_readiness is not None:
        ai_gap_count = sum(
            1 for c in ctx.ai_readiness.services if c.coverage_count < 2
        )
        if ai_gap_count >= 3:
            return L["ai_onboarding_gap"].format(n=ai_gap_count)

    return None


__all__ = ["business_implication"]
