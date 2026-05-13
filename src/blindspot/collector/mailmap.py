"""
.mailmap parser — Git's standard mechanism for canonicalising author identity.

Format reference: https://git-scm.com/docs/gitmailmap
Supported line forms:
    Proper Name <commit@email>
    <proper@email> <commit@email>
    Proper Name <proper@email> <commit@email>
    Proper Name <proper@email> Commit Name <commit@email>
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

_PAIR = re.compile(r"([^<]*)<([^>]+)>")


@dataclass
class _Entry:
    proper_name: str | None
    proper_email: str
    commit_name: str | None
    commit_email: str


@dataclass
class MailMap:
    by_name_email: dict[tuple[str, str], tuple[str, str]] = field(default_factory=dict)
    by_email: dict[str, tuple[str, str]] = field(default_factory=dict)

    @classmethod
    def from_repo(cls, repo_path: Path) -> "MailMap":
        path = repo_path / ".mailmap"
        if not path.exists():
            return cls()
        return cls.from_text(path.read_text(errors="ignore"))

    @classmethod
    def from_text(cls, text: str) -> "MailMap":
        by_name_email: dict[tuple[str, str], tuple[str, str]] = {}
        by_email: dict[str, tuple[str, str]] = {}
        for raw in text.splitlines():
            entry = _parse_line(raw)
            if entry is None:
                continue
            canonical_name = entry.proper_name or ""
            canonical = (canonical_name, entry.proper_email)
            if entry.commit_name is not None:
                by_name_email[(entry.commit_name, entry.commit_email)] = canonical
            else:
                by_email[entry.commit_email] = canonical
            # Git mailmap: declaring a proper name also assigns it to the proper email itself,
            # so subsequent commits made directly with the proper email also pick up the name.
            if entry.proper_name and entry.proper_email != entry.commit_email:
                by_email.setdefault(entry.proper_email, canonical)
        return cls(by_name_email=by_name_email, by_email=by_email)

    def resolve(self, name: str, email: str) -> tuple[str, str]:
        name = (name or "").strip()
        email = (email or "").strip().lower()

        keyed = self.by_name_email.get((name, email))
        if keyed is not None:
            resolved_name, resolved_email = keyed
            return (resolved_name or name, resolved_email)

        keyed = self.by_email.get(email)
        if keyed is not None:
            resolved_name, resolved_email = keyed
            return (resolved_name or name, resolved_email)

        return (name, email)


def _parse_line(raw: str) -> _Entry | None:
    line = raw.split("#", 1)[0].strip()
    if not line:
        return None

    pairs = _PAIR.findall(line)
    if not pairs:
        return None

    if len(pairs) == 1:
        name = pairs[0][0].strip()
        email = pairs[0][1].strip().lower()
        if not name:
            return None
        return _Entry(proper_name=name, proper_email=email, commit_name=None, commit_email=email)

    if len(pairs) == 2:
        first_name = pairs[0][0].strip() or None
        first_email = pairs[0][1].strip().lower()
        second_name = pairs[1][0].strip() or None
        second_email = pairs[1][1].strip().lower()

        if first_name is None and second_name is None:
            return _Entry(
                proper_name=None,
                proper_email=first_email,
                commit_name=None,
                commit_email=second_email,
            )
        if first_name is not None and second_name is None:
            return _Entry(
                proper_name=first_name,
                proper_email=first_email,
                commit_name=None,
                commit_email=second_email,
            )
        if first_name is not None and second_name is not None:
            return _Entry(
                proper_name=first_name,
                proper_email=first_email,
                commit_name=second_name,
                commit_email=second_email,
            )

    return None


__all__ = ["MailMap"]
