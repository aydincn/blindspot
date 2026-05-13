"""Validate declared CODEOWNERS against actual ownership signals.

Categories per file:
- orphan    — file has no CODEOWNERS rule matching it.
- mismatch  — declared owner(s) don't include the actual top owner.
- stale     — declared owner matches but hasn't touched the file in a long time.
- team_only — only team owners (`@org/team`); cannot validate against commit data.
- aligned   — declared owner is the actual top owner with recent activity.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Iterable

from blindspot.codeowners.parser import CodeOwnersFile, CodeOwnersRule
from blindspot.collector.git import Commit
from blindspot.ownership.engine import OwnershipMap

STALE_DAYS_DEFAULT = 90
MIN_COVERAGE_FOR_MISMATCH = 0.4


@dataclass(frozen=True, slots=True)
class CodeOwnersFinding:
    file: str
    category: str  # orphan | mismatch | stale | team_only | aligned
    declared_owners: tuple[str, ...]
    actual_top_owner: str | None
    actual_coverage: float
    days_since_declared_touch: int | None
    rule_pattern: str | None
    rule_line: int | None


@dataclass(frozen=True, slots=True)
class CodeOwnersReport:
    findings: tuple[CodeOwnersFinding, ...]

    @property
    def orphans(self) -> tuple[CodeOwnersFinding, ...]:
        return tuple(f for f in self.findings if f.category == "orphan")

    @property
    def mismatches(self) -> tuple[CodeOwnersFinding, ...]:
        return tuple(f for f in self.findings if f.category == "mismatch")

    @property
    def stale(self) -> tuple[CodeOwnersFinding, ...]:
        return tuple(f for f in self.findings if f.category == "stale")

    @property
    def team_only(self) -> tuple[CodeOwnersFinding, ...]:
        return tuple(f for f in self.findings if f.category == "team_only")

    @property
    def aligned(self) -> tuple[CodeOwnersFinding, ...]:
        return tuple(f for f in self.findings if f.category == "aligned")

    @property
    def coverage_ratio(self) -> float:
        if not self.findings:
            return 0.0
        matched = sum(1 for f in self.findings if f.category != "orphan")
        return matched / len(self.findings)


@dataclass
class CodeOwnersValidator:
    stale_days: int = STALE_DAYS_DEFAULT
    as_of: datetime | None = None

    def __post_init__(self) -> None:
        self.as_of = (self.as_of or datetime.now(UTC)).astimezone(UTC)

    def validate(
        self,
        codeowners: CodeOwnersFile,
        ownership: OwnershipMap,
        commits: Iterable[Commit],
    ) -> CodeOwnersReport:
        commits = tuple(commits)
        # last-touch index: (file, email) → most recent authored_at
        last_touch: dict[tuple[str, str], datetime] = {}
        for c in commits:
            for f in c.files:
                key = (f.path, c.author_email)
                prev = last_touch.get(key)
                if prev is None or c.authored_at > prev:
                    last_touch[key] = c.authored_at

        findings: list[CodeOwnersFinding] = []
        for file_path in ownership.files():
            rule = codeowners.rule_for(file_path)
            file_owners = ownership.for_file(file_path)
            top = file_owners[0] if file_owners else None
            actual_email = top.author_email if top else None
            coverage = top.coverage if top else 0.0

            if rule is None:
                findings.append(CodeOwnersFinding(
                    file=file_path, category="orphan",
                    declared_owners=(), actual_top_owner=actual_email,
                    actual_coverage=coverage,
                    days_since_declared_touch=None,
                    rule_pattern=None, rule_line=None,
                ))
                continue

            individuals, teams = _split_owners(rule.owners)
            if not individuals and teams:
                findings.append(CodeOwnersFinding(
                    file=file_path, category="team_only",
                    declared_owners=rule.owners, actual_top_owner=actual_email,
                    actual_coverage=coverage,
                    days_since_declared_touch=None,
                    rule_pattern=rule.pattern, rule_line=rule.line_number,
                ))
                continue

            declared_match = _find_declared_in_actual(
                individuals, ownership, file_path
            )
            if declared_match is None:
                findings.append(CodeOwnersFinding(
                    file=file_path, category="mismatch",
                    declared_owners=rule.owners, actual_top_owner=actual_email,
                    actual_coverage=coverage,
                    days_since_declared_touch=None,
                    rule_pattern=rule.pattern, rule_line=rule.line_number,
                ))
                continue

            declared_email, declared_is_top = declared_match
            last = last_touch.get((file_path, declared_email))
            days_since = (
                int((self.as_of - last).total_seconds() / 86400.0) if last else None
            )
            if not declared_is_top and coverage >= MIN_COVERAGE_FOR_MISMATCH:
                findings.append(CodeOwnersFinding(
                    file=file_path, category="mismatch",
                    declared_owners=rule.owners, actual_top_owner=actual_email,
                    actual_coverage=coverage,
                    days_since_declared_touch=days_since,
                    rule_pattern=rule.pattern, rule_line=rule.line_number,
                ))
                continue
            if days_since is None or days_since > self.stale_days:
                findings.append(CodeOwnersFinding(
                    file=file_path, category="stale",
                    declared_owners=rule.owners, actual_top_owner=actual_email,
                    actual_coverage=coverage,
                    days_since_declared_touch=days_since,
                    rule_pattern=rule.pattern, rule_line=rule.line_number,
                ))
                continue
            findings.append(CodeOwnersFinding(
                file=file_path, category="aligned",
                declared_owners=rule.owners, actual_top_owner=actual_email,
                actual_coverage=coverage,
                days_since_declared_touch=days_since,
                rule_pattern=rule.pattern, rule_line=rule.line_number,
            ))

        return CodeOwnersReport(findings=tuple(findings))


def _split_owners(owners: tuple[str, ...]) -> tuple[tuple[str, ...], tuple[str, ...]]:
    individuals: list[str] = []
    teams: list[str] = []
    for o in owners:
        if "/" in o:  # `@org/team`
            teams.append(o)
        else:
            individuals.append(o)
    return tuple(individuals), tuple(teams)


def _find_declared_in_actual(
    declared: tuple[str, ...],
    ownership: OwnershipMap,
    file_path: str,
) -> tuple[str, bool] | None:
    """Return (email, is_top_owner) for the first declared owner found among actual owners.

    Matches `@username` against `username@*` or `*+username@users.noreply.github.com`.
    Matches plain emails directly.
    """
    actual = ownership.for_file(file_path)
    if not actual:
        return None
    actual_emails = [a.author_email for a in actual]
    top = actual[0].author_email

    for d in declared:
        candidates = _email_candidates(d)
        for email in actual_emails:
            if any(_email_matches(email, cand) for cand in candidates):
                return (email, email == top)
    return None


def _email_candidates(declared: str) -> tuple[str, ...]:
    if "@" in declared and "/" not in declared:
        # Treat `@user` (GitHub) vs `user@host` (email).
        if declared.startswith("@"):
            return (declared[1:],)
        return (declared,)
    if declared.startswith("@"):
        return (declared[1:],)
    return (declared,)


def _email_matches(actual_email: str, declared: str) -> bool:
    if "@" in declared:
        return actual_email.lower() == declared.lower()
    # GitHub username — match `username@…` or `…+username@users.noreply.github.com`
    local = actual_email.split("@", 1)[0].lower()
    handle = declared.lower()
    if local == handle:
        return True
    if "+" in local and local.split("+", 1)[1] == handle:
        return True
    if actual_email.lower().endswith(f"+{handle}@users.noreply.github.com"):
        return True
    return False
