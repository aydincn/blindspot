"""AI Readiness — coverage of AI-native operational artifacts per service.

The premise: in AI-accelerated teams, organizational knowledge no longer lives
only in code. It also lives in operational artifacts that humans *and AI
agents* read — agent rules (`CLAUDE.md`, `.cursor/rules`, copilot
instructions), specs, prompts, architecture decisions. A service with no
such artifacts has weaker continuity than its line count suggests: a new
contributor (human or AI) has nothing to load.

This module is **not** an AI-generated-code detector. It does not look at
content style, statistical patterns, or "AI-ness" of commits. It only
checks whether documented operational context exists.

MVP: boolean per-category coverage for the repo root and each top-level
service directory, derived from the tracked file list.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass

from blindspot.risk_models.bus_factor import top_level_dir


_CATEGORIES = ("agent_rules", "specs", "prompts", "architecture", "skills")

# Patterns are matched against the path *relative to its scan root*. For repo-
# level scan the root is the repo; for per-service scan, the service prefix
# is stripped before matching.
_PATTERNS: dict[str, tuple[re.Pattern[str], ...]] = {
    "agent_rules": (
        re.compile(r"^(claude|agents?|gemini|copilot-instructions)\.md$", re.IGNORECASE),
        re.compile(r"^\.claude/", re.IGNORECASE),
        re.compile(r"^\.cursor/", re.IGNORECASE),
        re.compile(r"^\.clinerules", re.IGNORECASE),
        re.compile(r"^\.gemini/", re.IGNORECASE),
        re.compile(r"^\.continue/", re.IGNORECASE),
        re.compile(r"^\.github/(copilot-instructions\.md|agents/)", re.IGNORECASE),
        re.compile(r"^\.aider", re.IGNORECASE),
        re.compile(r"^\.windsurf", re.IGNORECASE),
        re.compile(r"^\.codex", re.IGNORECASE),
        re.compile(r"^\.cody", re.IGNORECASE),
        re.compile(r"^\.roo", re.IGNORECASE),
        re.compile(r"^\.kilocode", re.IGNORECASE),
        re.compile(r"^\.junie", re.IGNORECASE),
    ),
    "specs": (
        re.compile(r"^specs?/", re.IGNORECASE),
        re.compile(r"^specifications/", re.IGNORECASE),
    ),
    "prompts": (
        re.compile(r"^prompts?/", re.IGNORECASE),
    ),
    "architecture": (
        re.compile(r"^adrs?/", re.IGNORECASE),
        re.compile(r"^architecture/", re.IGNORECASE),
        re.compile(r"^docs/(architecture|decisions|adrs?)", re.IGNORECASE),
        re.compile(r"^architecture\.md$", re.IGNORECASE),
    ),
    "skills": (
        re.compile(r"^skills/", re.IGNORECASE),
        re.compile(r"^agents/", re.IGNORECASE),
        re.compile(r"^\.claude/(skills|commands|agents)/", re.IGNORECASE),
    ),
}


@dataclass(frozen=True, slots=True)
class AIReadinessCoverage:
    target: str  # "(repo)" or service name
    agent_rules: bool
    specs: bool
    prompts: bool
    architecture: bool
    skills: bool

    @property
    def coverage_count(self) -> int:
        return sum(
            (
                self.agent_rules,
                self.specs,
                self.prompts,
                self.architecture,
                self.skills,
            )
        )

    @property
    def coverage_ratio(self) -> float:
        return self.coverage_count / len(_CATEGORIES)


@dataclass(frozen=True, slots=True)
class AIReadinessReport:
    repo: AIReadinessCoverage
    services: tuple[AIReadinessCoverage, ...]

    @property
    def avg_service_coverage(self) -> float:
        if not self.services:
            return 0.0
        return sum(s.coverage_ratio for s in self.services) / len(self.services)


def _match_categories(paths: Iterable[str]) -> dict[str, bool]:
    found = {cat: False for cat in _CATEGORIES}
    for p in paths:
        for cat, patterns in _PATTERNS.items():
            if found[cat]:
                continue
            for pat in patterns:
                if pat.search(p):
                    found[cat] = True
                    break
    return found


def _strip_service_prefix(path: str, service: str) -> str | None:
    """Return path relative to the service root, or None if not under it."""
    prefix = service.rstrip("/") + "/"
    if path.startswith(prefix):
        return path[len(prefix) :]
    return None


@dataclass
class AIReadinessEngine:
    def detect(
        self,
        files: Iterable[str],
        *,
        service_of: Callable[[str], str] = top_level_dir,
    ) -> AIReadinessReport:
        files = tuple(files)

        # Repo-level: match against full paths.
        repo_found = _match_categories(files)
        repo_cov = AIReadinessCoverage(target="(repo)", **repo_found)

        # Per-service: group by service_of(file), then strip the appropriate
        # prefix. When the caller passes a code-root-aware factory (cli.py),
        # services become the directories *inside* the package, not the
        # source root.
        services: dict[str, list[str]] = {}
        for f in files:
            svc = service_of(f)
            if svc.startswith("(") and svc.endswith(")"):
                continue
            # If the factory stripped a prefix already, find which prefix
            # by checking what's at the start of the path.
            relative = _strip_service_prefix(f, svc)
            if relative is None:
                # Path doesn't start with the service segment directly —
                # the factory must have stripped a code-root prefix. Find
                # the segment that matches the resolved service in the
                # path tail.
                marker = f"/{svc}/"
                idx = f.find(marker)
                if idx >= 0:
                    relative = f[idx + len(marker):]
                else:
                    continue
            services.setdefault(svc, []).append(relative)

        per_service = tuple(
            sorted(
                (
                    AIReadinessCoverage(
                        target=svc,
                        **_match_categories(paths),
                    )
                    for svc, paths in services.items()
                ),
                key=lambda c: (-c.coverage_count, c.target),
            )
        )

        return AIReadinessReport(repo=repo_cov, services=per_service)


__all__ = [
    "AIReadinessCoverage",
    "AIReadinessEngine",
    "AIReadinessReport",
]
