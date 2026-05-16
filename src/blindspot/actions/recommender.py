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
    # service name → highest-importance code file in that service. Used by the
    # service-level diversification rule to add a concrete "start with X"
    # entry point. Built in cli.py from critical_files + importance_map.
    service_top_files: dict[str, str] = field(default_factory=dict)


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
            owner_email, owner_cov = s.top_owners[0]
            owner_label = self._label(ctx, owner_email)
            priority = ActionPriority.HIGH if s.file_count >= 5 else ActionPriority.MEDIUM
            top_file = ctx.service_top_files.get(s.service)
            start_with = (
                f" Start with: {top_file} (highest importance in this service)."
                if top_file else ""
            )
            evidence = (
                f"bus_factor=1, top_owner_coverage={owner_cov:.0%}, files={s.file_count}"
            )
            if top_file:
                evidence += f", top_file={top_file}"
            out.append(
                RecommendedAction(
                    priority=priority,
                    category=ActionCategory.OWNERSHIP_DIVERSIFICATION,
                    title=f"Diversify ownership of '{s.service}' (currently single-owner)",
                    description=(
                        f"Service '{s.service}' has bus factor 1 across {s.file_count} files; "
                        f"{owner_label} holds {owner_cov:.0%} of effective ownership. "
                        "Pair them with at least two additional engineers and rotate code reviews "
                        f"for this area over the next 60 days.{start_with}"
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
        Priority is bumped to MEDIUM when the service also has bus factor ≤ 1
        — there, the gap compounds with knowledge concentration."""
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
        for c in candidates:
            bus = bus_factor_by_service.get(c.target)
            critical = bus is not None and bus <= 1
            priority = ActionPriority.MEDIUM if critical else ActionPriority.LOW
            missing = []
            if not c.agent_rules:
                missing.append("agent rules (CLAUDE.md, .cursor/, copilot-instructions)")
            if not c.specs:
                missing.append("specs/")
            if not c.prompts:
                missing.append("prompts/")
            if not c.architecture:
                missing.append("architecture notes / ADRs")
            if not c.skills:
                missing.append("skills/")
            bus_note = (
                f" Bus factor is {bus} — the gap compounds with knowledge concentration."
                if critical else ""
            )
            out.append(
                RecommendedAction(
                    priority=priority,
                    category=ActionCategory.KNOWLEDGE_TRANSFER,
                    title=f"Add AI-readable operational context for '{c.target}'",
                    description=(
                        f"Service '{c.target}' has {c.coverage_count}/5 AI-native "
                        f"context coverage. Missing: {', '.join(missing)}. "
                        "Adding any of these lets new contributors (human or AI) "
                        "load context without spelunking through code."
                        + bus_note
                    ),
                    target=c.target,
                    evidence=(
                        f"coverage={c.coverage_count}/5, "
                        f"bus_factor={bus if bus is not None else 'n/a'}"
                    ),
                )
            )
        return out[: self.max_per_rule]

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
