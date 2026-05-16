"""Build the LLM prompt from a ReportContext.

Critical invariant: we send only aggregate metrics and recommendation titles —
**never raw commit content, file contents, or PR bodies**. This keeps the LLM
call privacy-clean and token-cheap (typical payload ~2K tokens).
"""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from blindspot.report.context import ReportContext
    from blindspot.risk_models.departure import DepartureReport


SYSTEM_PROMPT_EN = """\
You are an engineering resilience advisor writing for a VP of Engineering.
The user gives you a structured snapshot of a repository's knowledge-risk metrics.
You synthesize them into a short executive summary and concrete next steps.

Rules:
- Plain, direct English. No buzzwords, no marketing language.
- Be specific: name files, services, owners. Quote numbers from the input.
- Action-oriented: every paragraph in the summary should imply a next step.
- Never fabricate metrics or names. Only reference what's in the input.
- Never describe individuals in evaluative terms ("good engineer", "underperformer").
  Frame everything as system-level risk and verification, not judgement.
- Output strict JSON matching the schema in the user's instructions.
"""

SYSTEM_PROMPT_TR = """\
Bir mühendislik dayanıklılığı danışmanısın; Mühendislik Direktörü/VP'ye yazıyorsun.
Kullanıcı sana bir reponun bilgi-riski metriklerinin yapılandırılmış bir özetini veriyor.
Bunu kısa bir yönetici özeti ve somut sonraki adımlara dönüştürüyorsun.

Kurallar:
- Sade, doğrudan Türkçe. Pazarlama dilinden ve klinşelerden kaçın.
- Spesifik ol: dosya, servis, sahip isimlerini geçir. Girdideki sayıları alıntıla.
- Aksiyon odaklı: özetteki her paragraf bir sonraki adımı ima etmeli.
- Metrik veya isim uydurma. Sadece girdide olanı referans al.
- Bireyleri değerlendirici ifadelerle tanımlama ("iyi mühendis", "düşük performans gibi).
  Her şeyi sistem-düzeyi risk ve doğrulama olarak çerçevele, yargı olarak değil.
- Çıktıyı kullanıcı talimatındaki JSON şemasına bire bir uygun ver.
"""


def build_user_prompt(ctx: "ReportContext", language: str) -> str:
    payload = _structured_payload(ctx)
    instructions_en = """\
Below is a JSON snapshot. Produce a JSON response with this exact schema:

{
  "executive_summary": "2-3 short paragraphs of plain prose. Mention the score,
     the band, the weakest sub-score, and the most material risk. Mention trend
     direction if a trend object is present.",
  "headline_action": "One sentence: the single most important thing to do this
     week. Reference a specific file/service/owner from the input.",
  "rationales": {
     "<recommendation_target>": "One sentence: why this matters in business terms,
        2-25 words.",
     ...
  }
}

Output JSON only. No surrounding markdown fences, no commentary.

Snapshot:
"""
    instructions_tr = """\
Aşağıda JSON formatlı bir özet var. Şu şema ile JSON cevap üret:

{
  "executive_summary": "2-3 kısa paragraf, sade düzyazı. Skoru, bandı,
     en zayıf sub-score'u ve en kritik riski an. Trend objesi varsa yönünü belirt.",
  "headline_action": "Tek cümle: bu hafta yapılacak en önemli şey.
     Girdiden somut bir dosya/servis/sahip adı geçir.",
  "rationales": {
     "<recommendation_target>": "Tek cümle: iş açısından neden önemli, 2-25 kelime.",
     ...
  }
}

Sadece JSON çıktısı ver. Markdown bloku, açıklama yok.

Özet:
"""
    instructions = instructions_tr if language == "tr" else instructions_en
    return instructions + _json_dumps(payload)


def system_prompt(language: str) -> str:
    return SYSTEM_PROMPT_TR if language == "tr" else SYSTEM_PROMPT_EN


def _structured_payload(ctx: "ReportContext") -> dict[str, Any]:
    out: dict[str, Any] = {
        "repo_window_days": ctx.since_days,
        "totals": {
            "commits": ctx.commit_count,
            "authors": ctx.author_count,
            "files": ctx.file_count,
        },
    }
    if ctx.resilience is not None:
        out["resilience"] = {
            "overall": ctx.resilience.overall,
            "band": ctx.resilience.band,
            "ownership": ctx.resilience.ownership,
            "decay": ctx.resilience.decay,
            "review": ctx.resilience.review,
            "summary": ctx.resilience.summary,
        }
    # Top services by risk (max 5)
    top_services = sorted(
        ctx.services,
        key=lambda s: (s.risk_level != "critical", s.risk_level != "high", -s.file_count),
    )[:5]
    out["top_services"] = [
        {
            "service": s.service,
            "files": s.file_count,
            "bus_factor": s.bus_factor,
            "risk": s.risk_level,
            "top_owner": ctx.label(s.top_owners[0][0]) if s.top_owners else None,
            "top_owner_coverage_pct": int(s.top_owners[0][1] * 100) if s.top_owners else None,
        }
        for s in top_services
    ]
    # Top decays (max 5)
    out["top_decays"] = [
        {
            "file": d.file,
            "decay_pct": int(d.decay_score * 100),
            "days_since_owner_touch": int(d.days_since_owner_touch),
            "top_owner": ctx.label(d.top_owner),
            "risk": d.risk_level,
        }
        for d in ctx.decay_top[:5]
    ]
    # Recommendations (max 8 — sorted High → Low already)
    out["recommendations"] = [
        {
            "priority": a.priority.value,
            "category": a.category.value,
            "title": a.title,
            "target": a.target,
            "description": a.description,
        }
        for a in ctx.recommendations[:8]
    ]
    # Trend
    if ctx.trend and ctx.trend.snapshots:
        out["trend"] = {
            "snapshots": [
                {"days_ago": s.days_ago, "overall": s.score.overall, "band": s.score.band}
                for s in ctx.trend.snapshots
            ],
            "delta_overall": ctx.trend.delta_overall,
        }
    # CODEOWNERS
    if ctx.codeowners and ctx.codeowners.findings:
        out["codeowners"] = {
            "aligned": len(ctx.codeowners.aligned),
            "mismatch": len(ctx.codeowners.mismatches),
            "stale": len(ctx.codeowners.stale),
            "orphan": len(ctx.codeowners.orphans),
            "team_only": len(ctx.codeowners.team_only),
        }
    # Structural backbone — top central files (max 5)
    if ctx.top_central_files:
        out["top_central_files"] = [
            {
                "file": cf.file,
                "importance_pct": round(cf.importance * 100, 2),
                "dependents": cf.in_degree,
                "top_owner": ctx.label(cf.top_owner) if cf.top_owner else None,
                "top_owner_coverage_pct": int(cf.top_owner_coverage * 100),
            }
            for cf in ctx.top_central_files[:5]
        ]
    return out


DEPARTURE_SYSTEM_EN = """\
You are an engineering resilience advisor writing for a VP of Engineering.
The user has just simulated the departure of one or more team members.
You synthesize the simulation result into a short, action-oriented briefing.

Rules:
- Plain, direct English. No buzzwords.
- Be specific: name files, services, and the remaining owner if any.
- Action-oriented: the headline must be a concrete step to take this week.
- Never describe individuals in evaluative terms. Frame departures as
  knowledge-continuity events, not blame.
- Do not invent files, services, or numbers. Only reference the input.
- Output strict JSON matching the schema in the user's instructions.
"""

DEPARTURE_SYSTEM_TR = """\
Bir mühendislik dayanıklılığı danışmanısın; Mühendislik Direktörü/VP'ye yazıyorsun.
Kullanıcı bir veya birden çok ekip üyesinin ayrılış senaryosunu simüle etti.
Bunu kısa, aksiyon odaklı bir brifinge çevir.

Kurallar:
- Sade, doğrudan Türkçe. Pazarlama dilinden kaçın.
- Spesifik ol: dosya, servis ve kalan sahip ismini geçir.
- Aksiyon odaklı: başlık, bu hafta atılacak somut bir adım olmalı.
- Bireyleri değerlendirici şekilde tanımlama. Ayrılıkları bilgi-sürekliliği
  olayı olarak çerçevele, suçlama olarak değil.
- Dosya, servis veya sayı uydurma. Sadece girdideki bilgiyi kullan.
- Çıktıyı kullanıcı talimatındaki JSON şemasına bire bir uygun ver.
"""


def build_departure_prompt(
    report: "DepartureReport", names: dict[str, str], language: str
) -> str:
    payload = _departure_payload(report, names)
    instructions_en = """\
Below is a JSON snapshot of a departure simulation. Produce a JSON response
with this exact schema:

{
  "executive_summary": "2-3 short paragraphs. Mention who is departing (by name
     if available), how many files are affected, how many become orphaned,
     and which 1-2 services are most exposed.",
  "headline_action": "One sentence: the single most important step to take this
     week to mitigate the impact. Reference a specific file/service/owner.",
  "mitigations": [
     "3 to 5 bullet items. Each is one concrete step (e.g., 'Pair Carol with
        Bob on payment/billing.py for the next 2 sprints'). Use names from
        the snapshot."
  ]
}

Output JSON only.

Snapshot:
"""
    instructions_tr = """\
Aşağıda bir ayrılış senaryosunun JSON özeti var. Şu şema ile JSON cevap üret:

{
  "executive_summary": "2-3 kısa paragraf. Kim/kimlerin ayrıldığını (isimleriyle
     varsa), kaç dosyanın etkilendiğini, kaçının orphan olduğunu ve en riskli
     1-2 servisi an.",
  "headline_action": "Tek cümle: etkiyi azaltmak için bu hafta atılacak en
     önemli somut adım. Girdiden somut bir dosya/servis/sahip ismi geçir.",
  "mitigations": [
     "3-5 madde. Her biri tek cümlelik somut adım (ör. 'Carol'u 2 sprint
        boyunca payment/billing.py'de Bob ile eşleştir'). Snapshot'taki
        isimleri kullan."
  ]
}

Sadece JSON.

Özet:
"""
    instructions = instructions_tr if language == "tr" else instructions_en
    return instructions + _json_dumps(payload)


def departure_system_prompt(language: str) -> str:
    return DEPARTURE_SYSTEM_TR if language == "tr" else DEPARTURE_SYSTEM_EN


def _departure_payload(
    report: "DepartureReport", names: dict[str, str]
) -> dict[str, Any]:
    def label(email: str) -> str:
        name = names.get(email)
        return f"{name} ({email})" if name and name != email else email

    out: dict[str, Any] = {
        "departing": [label(e) for e in report.departing],
        "totals": {
            "files_in_scope": report.total_files,
            "affected_files": report.affected_files,
            "orphaned_files": report.orphaned_files,
            "avg_coverage_loss_pct": int(report.avg_coverage_loss * 100),
        },
        "services": [
            {
                "service": s.service,
                "files": s.file_count,
                "affected": s.affected_files,
                "orphaned": s.orphaned_files,
                "avg_loss_pct": int(s.avg_coverage_loss * 100),
                "severity": s.severity,
            }
            for s in report.services[:8]
        ],
        "impacted_files": [
            {
                "file": f.file,
                "loss_pct": int(f.coverage_loss * 100),
                "remaining_top_owner": (
                    label(f.remaining_top_owner) if f.remaining_top_owner else None
                ),
                "remaining_top_coverage_pct": int(f.remaining_top_coverage * 100),
                "becomes_orphan": f.becomes_orphan,
                "severity": f.severity,
            }
            for f in report.files
            if f.severity in ("critical", "high")
        ][:10],
    }
    return out


def _json_dumps(obj: Any) -> str:
    import json
    return json.dumps(obj, ensure_ascii=False, indent=2)


__all__ = [
    "build_departure_prompt",
    "build_user_prompt",
    "departure_system_prompt",
    "system_prompt",
]
