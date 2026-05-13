from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from git import Commit as GitCommit
from git import Repo

from blindspot.collector.filters import FileFilter, canonical_email
from blindspot.collector.mailmap import MailMap
from blindspot.collector.models import Commit, FileChange


class GitCollector:
    def __init__(
        self,
        repo_path: Path,
        since_days: int = 180,
        include_merges: bool = False,
        file_filter: FileFilter | None = None,
        mailmap: MailMap | None = None,
    ) -> None:
        repo_path = Path(repo_path).resolve()
        self.repo = Repo(str(repo_path))
        self.since_days = since_days
        self.include_merges = include_merges
        self.file_filter = (
            file_filter if file_filter is not None else FileFilter.from_repo(repo_path)
        )
        self.mailmap = mailmap if mailmap is not None else MailMap.from_repo(repo_path)

    def collect(self) -> Iterator[Commit]:
        if not self._has_commits():
            return

        cutoff = datetime.now(UTC) - timedelta(days=self.since_days)
        kwargs: dict[str, Any] = {"since": cutoff.isoformat()}
        if not self.include_merges:
            kwargs["no_merges"] = True

        for c in self.repo.iter_commits(**kwargs):
            commit = _to_commit(c, self.file_filter, self.mailmap)
            if commit.files:
                yield commit

    def _has_commits(self) -> bool:
        try:
            return self.repo.head.is_valid()
        except (ValueError, TypeError):
            return False


def _to_commit(c: GitCommit, file_filter: FileFilter, mailmap: MailMap) -> Commit:
    stats = c.stats.files
    files = tuple(
        FileChange(
            path=str(path),
            additions=int(info["insertions"]),
            deletions=int(info["deletions"]),
        )
        for path, info in stats.items()
        if not file_filter.should_skip(str(path))
    )
    msg = c.message
    if isinstance(msg, bytes):
        msg = msg.decode("utf-8", errors="replace")

    raw_name = c.author.name or ""
    raw_email = c.author.email or ""
    resolved_name, resolved_email = mailmap.resolve(raw_name, raw_email)
    canonical = canonical_email(resolved_email)

    return Commit(
        sha=c.hexsha,
        author_email=canonical,
        author_name=resolved_name,
        authored_at=c.authored_datetime.astimezone(UTC),
        message=msg.strip(),
        is_merge=len(c.parents) > 1,
        files=files,
    )
