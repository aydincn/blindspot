from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from git import Actor, Repo


@dataclass
class CommitSpec:
    author_name: str
    author_email: str
    file: str
    content: str
    days_ago: int
    message: str = "commit"


@pytest.fixture
def make_repo(tmp_path: Path) -> Callable[[list[CommitSpec]], Path]:
    def _make(commits: list[CommitSpec]) -> Path:
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        repo = Repo.init(repo_path)
        with repo.config_writer() as cw:
            cw.set_value("user", "email", "default@example.com")
            cw.set_value("user", "name", "Default")
            cw.set_value("commit", "gpgsign", "false")

        now = datetime.now(UTC)
        for spec in commits:
            file_path = repo_path / spec.file
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(spec.content)
            repo.index.add([str(file_path)])

            actor = Actor(spec.author_name, spec.author_email)
            commit_dt = (now - timedelta(days=spec.days_ago)).replace(microsecond=0)
            commit_date = f"{int(commit_dt.timestamp())} +0000"

            repo.index.commit(
                message=spec.message,
                author=actor,
                committer=actor,
                author_date=commit_date,
                commit_date=commit_date,
            )
        return repo_path

    return _make
