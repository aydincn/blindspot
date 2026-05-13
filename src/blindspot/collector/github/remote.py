"""Parse a git remote URL to identify the GitHub owner/repo."""

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

_PATTERNS = (
    # https://github.com/owner/repo[.git]
    re.compile(r"^https?://github\.com/(?P<owner>[^/]+)/(?P<repo>[^/.]+?)(?:\.git)?/?$"),
    # git@github.com:owner/repo[.git]
    re.compile(r"^git@github\.com:(?P<owner>[^/]+)/(?P<repo>[^/.]+?)(?:\.git)?$"),
    # ssh://git@github.com/owner/repo[.git]
    re.compile(r"^ssh://git@github\.com/(?P<owner>[^/]+)/(?P<repo>[^/.]+?)(?:\.git)?/?$"),
)


@dataclass(frozen=True, slots=True)
class GitHubRemote:
    owner: str
    repo: str
    url: str

    @property
    def slug(self) -> str:
        return f"{self.owner}/{self.repo}"


def parse_remote_url(url: str) -> GitHubRemote | None:
    url = url.strip()
    for pattern in _PATTERNS:
        m = pattern.match(url)
        if m:
            return GitHubRemote(owner=m.group("owner"), repo=m.group("repo"), url=url)
    return None


def detect_github_remote(repo_path: Path, remote: str = "origin") -> GitHubRemote | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_path), "remote", "get-url", remote],
            check=True,
            capture_output=True,
            text=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    return parse_remote_url(result.stdout.strip())


__all__ = ["GitHubRemote", "detect_github_remote", "parse_remote_url"]
