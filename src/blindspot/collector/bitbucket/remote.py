"""Parse a git remote URL to identify the Bitbucket Cloud workspace/repo.

Only bitbucket.org (Cloud) is recognised. Self-hosted Bitbucket
Server/Data Center uses a different API and is intentionally not matched
here — those URLs fall through and return None.
"""

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

_PATTERNS = (
    # https://bitbucket.org/workspace/repo[.git]
    # also matches https://user@bitbucket.org/workspace/repo.git
    re.compile(
        r"^https?://(?:[^@/]+@)?bitbucket\.org/"
        r"(?P<workspace>[^/]+)/(?P<repo>[^/.]+?)(?:\.git)?/?$"
    ),
    # git@bitbucket.org:workspace/repo[.git]
    re.compile(
        r"^git@bitbucket\.org:(?P<workspace>[^/]+)/(?P<repo>[^/.]+?)(?:\.git)?$"
    ),
    # ssh://git@bitbucket.org/workspace/repo[.git]
    re.compile(
        r"^ssh://git@bitbucket\.org/"
        r"(?P<workspace>[^/]+)/(?P<repo>[^/.]+?)(?:\.git)?/?$"
    ),
)


@dataclass(frozen=True, slots=True)
class BitbucketRemote:
    workspace: str
    repo: str
    url: str

    @property
    def slug(self) -> str:
        return f"{self.workspace}/{self.repo}"


def parse_remote_url(url: str) -> BitbucketRemote | None:
    url = url.strip()
    for pattern in _PATTERNS:
        m = pattern.match(url)
        if m:
            return BitbucketRemote(
                workspace=m.group("workspace"),
                repo=m.group("repo"),
                url=url,
            )
    return None


def detect_bitbucket_remote(
    repo_path: Path, remote: str = "origin"
) -> BitbucketRemote | None:
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


__all__ = ["BitbucketRemote", "detect_bitbucket_remote", "parse_remote_url"]
