from dataclasses import dataclass, field

from blindspot.actions.models import (
    PRIORITY_ORDER,
    ActionCategory,
    ActionPriority,
    FragilityPattern,
    RecommendedAction,
)
from blindspot.codeowners import CodeOwnersReport
from blindspot.diff_analysis.classifier import classify_file
from blindspot.review_graph.engine import FileReviewStats
from blindspot.resilience.silos import SilosReport
from blindspot.risk_models.ai_readiness import AIReadinessReport
from blindspot.risk_models.bus_factor import FileBusFactor, ServiceBusFactor
from blindspot.risk_models.correction_load import (
    AuthorCorrectionLoad,
    FileCorrectionLoad,
)
from blindspot.risk_models.knowledge_decay import FileDecay


@dataclass
class RecommendationContext:
    services: tuple[ServiceBusFactor, ...] = ()
    critical_files: tuple[FileBusFactor, ...] = ()
    decays: tuple[FileDecay, ...] = ()
    review_stats: dict[str, FileReviewStats] = field(default_factory=dict)
    ownership_names: dict[str, str] = field(default_factory=dict)
    codeowners_report: CodeOwnersReport | None = None
    importance_map: dict[str, float] = field(default_factory=dict)
    correction_load_authors: tuple[AuthorCorrectionLoad, ...] = ()
    correction_load_files: tuple[FileCorrectionLoad, ...] = ()
    ai_readiness: AIReadinessReport | None = None
    # service name → up to 3 highest-importance code files in that service,
    # ordered most important first. Lets the diversification rule turn a
    # giant "1589 files" number into a concrete "start with these 3" list
    # plus a cadence hint. Built in cli.py from critical_files +
    # importance_map.
    service_top_files: dict[str, tuple[str, ...]] = field(default_factory=dict)
    silos: SilosReport | None = None


# Top-level directories that are operationally important but rarely benefit
# from "diversify ownership" advice — they're typically maintained by 1-2
# release/infra engineers by design (CI workflows, docs, fixtures, vendored
# code). Recommendation rules treat these as support surfaces: the service
# still appears in the bus-factor / risk tables for awareness, but no action
# is emitted against them.
SUPPORT_SERVICES: frozenset[str] = frozenset({
    "(root)",
    "(config)",
    "(other)",
    ".github",
    "docs",
    "documentation",
    "docs_src",
    "docs-src",
    "site",
    "website",
    "tests",
    "test",
    "__tests__",
    "scripts",
    "script",
    "examples",
    "example",
    "samples",
    "hack",
    "vendor",
    "vendored",
    "third_party",
    "third-party",
    "build",
    "dist",
})


@dataclass
class RecommendationEngine:
    decay_critical_threshold: float = 0.75
    decay_high_threshold: float = 0.50
    rubber_stamp_threshold: float = 0.70
    diversity_floor: float = 0.20
    fast_approval_seconds: float = 30 * 60
    min_reviews_for_rubber_stamp: int = 2
    min_reviews_for_diversity: int = 3
    min_approvals_for_latency: int = 3
    max_per_rule: int = 5
    importance_threshold: float = 0.005
    correction_load_high_threshold: float = 0.35
    ai_readiness_min_coverage: int = 2
    support_services: frozenset[str] = SUPPORT_SERVICES
    # Services with fewer files than this don't generate a diversification
    # recommendation — "pair on bus factor 1 across 1 files" is meaningless.
    min_service_files_for_action: int = 3

    def _passes_importance(self, ctx: RecommendationContext, file: str) -> bool:
        """Filter out files structurally unimportant to the codebase.

        When no importance_map is provided (or it's empty), behaviour is
        unchanged — every file passes. With a map, files below the
        threshold (default 0.5% PageRank weight) are filtered.
        """
        if not ctx.importance_map:
            return True
        return ctx.importance_map.get(file, 0.0) >= self.importance_threshold

    def recommend(self, ctx: RecommendationContext) -> list[RecommendedAction]:
        actions: list[RecommendedAction] = []
        actions.extend(self._service_bus_factor(ctx))
        actions.extend(self._file_decay(ctx))
        actions.extend(self._rubber_stamp(ctx))
        actions.extend(self._reviewer_diversity(ctx))
        actions.extend(self._fast_approval(ctx))
        actions.extend(self._correction_load(ctx))
        actions.extend(self._ai_readiness_gap(ctx))
        actions.extend(self._hidden_silos(ctx))
        actions.extend(self._codeowners(ctx))
        actions.sort(key=lambda a: (PRIORITY_ORDER[a.priority], a.category.value, a.target))
        return actions

    def _label(self, ctx: RecommendationContext, email: str) -> str:
        name = ctx.ownership_names.get(email)
        if name and name != email:
            return f"{name} ({email})"
        return email

    def _service_bus_factor(self, ctx: RecommendationContext) -> list[RecommendedAction]:
        out: list[RecommendedAction] = []
        for s in ctx.services:
            if s.bus_factor > 1 or not s.top_owners:
                continue
            if s.service in self.support_services:
                continue  # CI/docs/tests/scripts — single-owner by design
            if s.file_count < self.min_service_files_for_action:
                continue  # "Diversify across 1 file" is meaningless
            owner_email, owner_cov = s.top_owners[0]
            owner_label = self._label(ctx, owner_email)
            priority = ActionPriority.HIGH if s.file_count >= 5 else ActionPriority.MEDIUM
            top_files = ctx.service_top_files.get(s.service, ())
            if top_files:
                if len(top_files) == 1:
                    start_with = (
                        f" Start with: {top_files[0]} (highest importance in this service)."
                    )
                else:
                    listed = ", ".join(top_files)
                    start_with = f" Start with these {len(top_files)} files: {listed}."
            else:
                start_with = ""
            # Effort hint: large services need a cadence to be realistic.
            if s.file_count >= 50:
                effort_hint = " Cadence: one file per sprint to keep the load reviewable."
            elif s.file_count >= 15:
                effort_hint = " Cadence: aim to cover the top files this quarter."
            else:
                effort_hint = ""
            evidence = (
                f"bus_factor=1, top_owner_coverage={owner_cov:.0%}, files={s.file_count}"
            )
            if top_files:
                evidence += f", top_files={top_files[0]}"
                if len(top_files) > 1:
                    evidence += f"+{len(top_files) - 1}"
            out.append(
                RecommendedAction(
                    priority=priority,
                    category=ActionCategory.OWNERSHIP_DIVERSIFICATION,
                    title=f"Diversify ownership of '{s.service}' (currently single-owner)",
                    description=(
                        f"Service '{s.service}' has bus factor 1 across {s.file_count} files; "
                        f"{owner_label} holds {owner_cov:.0%} of effective ownership. "
                        "Pair them with at least two additional engineers and rotate code reviews "
                        f"for this area over the next 60 days.{start_with}{effort_hint}"
                    ),
                    target=s.service,
                    evidence=evidence,
                    pattern=FragilityPattern.SINGLE_OWNER_CONCENTRATION,
                )
            )
        return out[: self.max_per_rule]

    def _file_decay(self, ctx: RecommendationContext) -> list[RecommendedAction]:
        out: list[RecommendedAction] = []
        for d in ctx.decays:
            if d.decay_score < self.decay_high_threshold:
                continue
            if not self._passes_importance(ctx, d.file):
                continue
            owner_label = self._label(ctx, d.top_owner)
            critical = d.decay_score >= self.decay_critical_threshold
            priority = ActionPriority.HIGH if critical else ActionPriority.MEDIUM
            urgency = "critical" if critical else "elevated"
            out.append(
                RecommendedAction(
                    priority=priority,
                    category=ActionCategory.KNOWLEDGE_TRANSFER,
                    title=f"Knowledge transfer for {d.file}",
                    description=(
                        f"Decay is {urgency} ({d.decay_score:.0%}). "
                        f"{owner_label} last touched this file {d.days_since_owner_touch:.0f} days ago, "
                        f"and {d.lines_changed_after} lines have been changed since by others. "
                        "Schedule a transfer session and designate a secondary owner before the next "
                        "non-trivial change."
                    ),
                    target=d.file,
                    evidence=(
                        f"decay={d.decay_score:.0%}, days_since_touch={d.days_since_owner_touch:.0f}, "
                        f"lines_after={d.lines_changed_after}"
                    ),
                )
            )
        return out[: self.max_per_rule]

    def _rubber_stamp(self, ctx: RecommendationContext) -> list[RecommendedAction]:
        out: list[RecommendedAction] = []
        candidates = sorted(
            (
                s for s in ctx.review_stats.values()
                if s.total_reviews >= self.min_reviews_for_rubber_stamp
                and s.rubber_stamp_ratio >= self.rubber_stamp_threshold
                and classify_file(s.file) == "code"
                and self._passes_importance(ctx, s.file)
            ),
            key=lambda s: (-s.rubber_stamp_ratio, -s.total_reviews),
        )
        for s in candidates:
            out.append(
                RecommendedAction(
                    priority=ActionPriority.MEDIUM,
                    category=ActionCategory.REVIEW_HYGIENE,
                    title=f"Add review depth requirement for {s.file}",
                    description=(
                        f"{s.rubber_stamp_ratio:.0%} of approvals on this file arrived without a "
                        f"substantive review comment (across {s.total_reviews} reviews). "
                        "Introduce a review checklist or require at least one substantive comment "
                        "before approval is allowed."
                    ),
                    target=s.file,
                    evidence=(
                        f"rubber_stamp_ratio={s.rubber_stamp_ratio:.0%}, reviews={s.total_reviews}"
                    ),
                    pattern=FragilityPattern.REVIEW_WITHOUT_SCRUTINY,
                )
            )
        return out[: self.max_per_rule]

    def _reviewer_diversity(self, ctx: RecommendationContext) -> list[RecommendedAction]:
        out: list[RecommendedAction] = []
        candidates = sorted(
            (
                s for s in ctx.review_stats.values()
                if s.total_reviews >= self.min_reviews_for_diversity
                and s.diversity_hhi < self.diversity_floor
                and classify_file(s.file) == "code"
                and self._passes_importance(ctx, s.file)
            ),
            key=lambda s: s.diversity_hhi,
        )
        for s in candidates:
            out.append(
                RecommendedAction(
                    priority=ActionPriority.LOW,
                    category=ActionCategory.REVIEW_HYGIENE,
                    title=f"Rotate reviewers for {s.file}",
                    description=(
                        f"Reviewer diversity for this file is {s.diversity_hhi:.0%}, "
                        "meaning a single reviewer is carrying most of the review burden. "
                        "Add the file to a CODEOWNERS group or require a second reviewer to spread "
                        "knowledge of the area."
                    ),
                    target=s.file,
                    evidence=(
                        f"diversity_hhi={s.diversity_hhi:.0%}, unique_reviewers={s.unique_reviewers}"
                    ),
                )
            )
        return out[: self.max_per_rule]

    def _fast_approval(self, ctx: RecommendationContext) -> list[RecommendedAction]:
        out: list[RecommendedAction] = []
        candidates = sorted(
            (
                s for s in ctx.review_stats.values()
                if s.median_approval_latency_seconds is not None
                and s.approval_sample_size >= self.min_approvals_for_latency
                and s.median_approval_latency_seconds < self.fast_approval_seconds
                and classify_file(s.file) == "code"
                and self._passes_importance(ctx, s.file)
            ),
            key=lambda s: s.median_approval_latency_seconds or 0,
        )
        for s in candidates:
            minutes = (s.median_approval_latency_seconds or 0) / 60
            out.append(
                RecommendedAction(
                    priority=ActionPriority.MEDIUM,
                    category=ActionCategory.REVIEW_HYGIENE,
                    title=f"Slow down fast approvals on {s.file}",
                    description=(
                        f"Median time from PR open to first approval is "
                        f"{minutes:.0f} minutes across {s.approval_sample_size} approvals — "
                        "too short for meaningful review of non-trivial code. "
                        "Add a minimum review time, CODEOWNERS review requirement, "
                        "or required checklist."
                    ),
                    target=s.file,
                    evidence=(
                        f"median_approval={minutes:.0f}min, samples={s.approval_sample_size}"
                    ),
                    pattern=FragilityPattern.REVIEW_WITHOUT_SCRUTINY,
                )
            )
        return out[: self.max_per_rule]

    def _correction_load(self, ctx: RecommendationContext) -> list[RecommendedAction]:
        """Flag work surfaces where the correction-to-feature ratio suggests
        fragile velocity. We target files (work surface), not people."""
        out: list[RecommendedAction] = []
        candidates = sorted(
            (
                f for f in ctx.correction_load_files
                if f.correction_ratio >= self.correction_load_high_threshold
                and classify_file(f.file) == "code"
                and self._passes_importance(ctx, f.file)
            ),
            key=lambda f: -f.correction_ratio,
        )
        for f in candidates:
            critical = f.risk_level == "critical"
            priority = ActionPriority.MEDIUM if not critical else ActionPriority.HIGH
            out.append(
                RecommendedAction(
                    priority=priority,
                    category=ActionCategory.QUALITY_GUARDRAIL,
                    title=f"Stabilize delivery on {f.file}",
                    description=(
                        f"{f.correction_ratio:.0%} of recent commits to this file are "
                        f"follow-up fixes or reverts ({f.fix_commits + f.revert_commits} "
                        f"of {f.total_commits}). Consider tightening review depth, adding "
                        "regression tests, or pairing on the next non-trivial change to "
                        "this surface."
                    ),
                    target=f.file,
                    evidence=(
                        f"correction_ratio={f.correction_ratio:.0%}, "
                        f"fixes={f.fix_commits}, reverts={f.revert_commits}, "
                        f"total={f.total_commits}"
                    ),
                    pattern=FragilityPattern.FRAGILE_VELOCITY,
                )
            )
        return out[: self.max_per_rule]

    def _ai_readiness_gap(self, ctx: RecommendationContext) -> list[RecommendedAction]:
        """Flag services that lack AI-readable operational context.

        Critical gaps (low coverage + bus factor ≤ 1) emit individual MEDIUM
        recommendations — there, the gap compounds with knowledge
        concentration and deserves its own punch-list line.

        Non-critical gaps are *aggregated* into a single LOW
        recommendation so repos with many bare services don't spam the
        table with repetitive lines. The names are listed in the
        description and evidence.
        """
        if ctx.ai_readiness is None:
            return []
        bus_factor_by_service = {s.service: s.bus_factor for s in ctx.services}
        candidates = sorted(
            (
                c for c in ctx.ai_readiness.services
                if c.coverage_count < self.ai_readiness_min_coverage
                and c.target not in self.support_services
            ),
            key=lambda c: (c.coverage_count, c.target),
        )
        out: list[RecommendedAction] = []
        regular: list = []

        def _missing(c) -> list[str]:
            m = []
            if not c.agent_rules:
                m.append("agent rules (CLAUDE.md, .cursor/, copilot-instructions)")
            if not c.specs:
                m.append("specs/")
            if not c.prompts:
                m.append("prompts/")
            if not c.architecture:
                m.append("architecture notes / ADRs")
            if not c.skills:
                m.append("skills/")
            return m

        for c in candidates:
            bus = bus_factor_by_service.get(c.target)
            if bus is not None and bus <= 1:
                # Compound risk — keep it as its own MEDIUM line
                missing = _missing(c)
                out.append(
                    RecommendedAction(
                        priority=ActionPriority.MEDIUM,
                        category=ActionCategory.KNOWLEDGE_TRANSFER,
                        title=f"Add AI-readable operational context for '{c.target}'",
                        description=(
                            f"Service '{c.target}' has {c.coverage_count}/5 "
                            f"AI-native context coverage. Missing: "
                            f"{', '.join(missing)}. Bus factor is {bus} — the "
                            "gap compounds with knowledge concentration, so "
                            "AI-assisted onboarding can't soften an owner "
                            "departure either."
                        ),
                        target=c.target,
                        evidence=(
                            f"coverage={c.coverage_count}/5, bus_factor={bus}"
                        ),
                    )
                )
            else:
                regular.append(c)

        # Aggregate the non-compound gaps into a single LOW line.
        if regular:
            if len(regular) == 1:
                c = regular[0]
                missing = _missing(c)
                out.append(
                    RecommendedAction(
                        priority=ActionPriority.LOW,
                        category=ActionCategory.KNOWLEDGE_TRANSFER,
                        title=f"Add AI-readable operational context for '{c.target}'",
                        description=(
                            f"Service '{c.target}' has {c.coverage_count}/5 "
                            f"AI-native context coverage. Missing: "
                            f"{', '.join(missing)}. Adding any of these lets "
                            "new contributors (human or AI) load context "
                            "without spelunking through code."
                        ),
                        target=c.target,
                        evidence=f"coverage={c.coverage_count}/5",
                    )
                )
            else:
                names = [c.target for c in regular]
                preview = ", ".join(names[:5])
                if len(names) > 5:
                    preview += f", … (+{len(names) - 5} more)"
                out.append(
                    RecommendedAction(
                        priority=ActionPriority.LOW,
                        category=ActionCategory.KNOWLEDGE_TRANSFER,
                        title=(
                            f"Add AI-readable operational context across "
                            f"{len(regular)} services"
                        ),
                        description=(
                            f"{len(regular)} services carry fewer than "
                            f"{self.ai_readiness_min_coverage}/5 AI-native "
                            f"context categories: {preview}. Bulk-adding "
                            "CLAUDE.md / specs / ADRs across these surfaces "
                            "lets new contributors (human or AI) load context "
                            "without spelunking through code."
                        ),
                        target=f"{len(regular)} services",
                        evidence=(
                            f"services={len(regular)}, "
                            f"max_coverage={max(c.coverage_count for c in regular)}/5"
                        ),
                    )
                )
        return out[: self.max_per_rule]

    def _hidden_silos(self, ctx: RecommendationContext) -> list[RecommendedAction]:
        """Flag services whose reviewer set is disjoint from every other
        service. Tribal-knowledge clusters waiting for an exit interview."""
        if ctx.silos is None or not ctx.silos.findings:
            return []
        out: list[RecommendedAction] = []
        for f in ctx.silos.findings[: self.max_per_rule]:
            reviewer_preview = ", ".join(f.reviewers[:3])
            if len(f.reviewers) > 3:
                reviewer_preview += f", … (+{len(f.reviewers) - 3})"
            out.append(
                RecommendedAction(
                    priority=ActionPriority.MEDIUM,
                    category=ActionCategory.REVIEW_HYGIENE,
                    title=f"Cross-pollinate reviewers for '{f.service}'",
                    description=(
                        f"Service '{f.service}' is reviewed exclusively by "
                        f"{len(f.reviewers)} people ({reviewer_preview}) and "
                        "none of them appear as reviewers on any other "
                        "service in this scan. That's a tribal-knowledge "
                        "cluster — pull in a reviewer from another area to "
                        "create cross-service literacy before someone leaves."
                    ),
                    target=f.service,
                    evidence=(
                        f"unique_reviewers={len(f.reviewers)}, "
                        f"reviews={f.review_count}, cross_service_overlap=0"
                    ),
                )
            )
        return out

    def _codeowners(self, ctx: RecommendationContext) -> list[RecommendedAction]:
        report = ctx.codeowners_report
        if report is None:
            return []
        out: list[RecommendedAction] = []

        # Mismatches: highest signal — declared owner is wrong.
        for f in report.mismatches[: self.max_per_rule]:
            actual_label = (
                self._label(ctx, f.actual_top_owner) if f.actual_top_owner else "(unknown)"
            )
            declared = ", ".join(f.declared_owners) if f.declared_owners else "(none)"
            out.append(RecommendedAction(
                priority=ActionPriority.MEDIUM,
                category=ActionCategory.CODEOWNERS_UPDATE,
                title=f"Update CODEOWNERS for {f.file}",
                description=(
                    f"Declared owners ({declared}) do not include the current top contributor. "
                    f"{actual_label} holds {f.actual_coverage:.0%} of effective ownership. "
                    "Either add them to the CODEOWNERS rule or assign explicit cross-coverage."
                ),
                target=f.file,
                evidence=(
                    f"declared={declared}, actual_top={f.actual_top_owner or 'n/a'}, "
                    f"coverage={f.actual_coverage:.0%}, line={f.rule_line}"
                ),
            ))

        # Stale: declared owner hasn't touched it in a long time.
        for f in report.stale[: self.max_per_rule]:
            declared = ", ".join(f.declared_owners) if f.declared_owners else "(none)"
            days = f.days_since_declared_touch
            days_txt = f"{days}" if days is not None else "no record"
            out.append(RecommendedAction(
                priority=ActionPriority.LOW,
                category=ActionCategory.CODEOWNERS_UPDATE,
                title=f"Refresh stale CODEOWNERS entry for {f.file}",
                description=(
                    f"Declared owner ({declared}) has not touched this file in {days_txt} days. "
                    "Confirm the assignment is still accurate; if not, rotate to a recent contributor."
                ),
                target=f.file,
                evidence=(
                    f"declared={declared}, days_since_touch={days_txt}, line={f.rule_line}"
                ),
            ))
        return out


__all__ = ["RecommendationContext", "RecommendationEngine"]
