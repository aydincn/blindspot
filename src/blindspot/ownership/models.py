from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True, slots=True)
class FileOwnership:
    file: str
    author_email: str
    commit_count: int
    additions: int
    deletions: int
    last_authored_at: datetime
    days_since_last: float
    raw_score: float
    coverage: float


@dataclass(frozen=True, slots=True)
class OwnershipMap:
    scores: tuple[FileOwnership, ...]
    names: dict[str, str] = field(default_factory=dict)

    def for_file(self, path: str) -> list[FileOwnership]:
        return sorted(
            (s for s in self.scores if s.file == path),
            key=lambda s: s.coverage,
            reverse=True,
        )

    def for_person(self, email: str) -> list[FileOwnership]:
        return [s for s in self.scores if s.author_email == email]

    def files(self) -> list[str]:
        return sorted({s.file for s in self.scores})

    def people(self) -> list[str]:
        return sorted({s.author_email for s in self.scores})

    def name_for(self, email: str) -> str:
        return self.names.get(email) or email

    def label_for(self, email: str) -> str:
        name = self.names.get(email)
        if name and name != email:
            return f"{name} ({email})"
        return email

    def top_concentration(self, limit: int = 10) -> list[FileOwnership]:
        """Files where one author holds the largest share of ownership."""
        per_file_top: dict[str, FileOwnership] = {}
        for s in self.scores:
            current = per_file_top.get(s.file)
            if current is None or s.coverage > current.coverage:
                per_file_top[s.file] = s
        return sorted(per_file_top.values(), key=lambda s: s.coverage, reverse=True)[:limit]
