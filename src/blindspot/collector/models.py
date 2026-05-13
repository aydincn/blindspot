from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class FileChange:
    path: str
    additions: int
    deletions: int


@dataclass(frozen=True, slots=True)
class Commit:
    sha: str
    author_email: str
    author_name: str
    authored_at: datetime
    message: str
    is_merge: bool
    files: tuple[FileChange, ...]
