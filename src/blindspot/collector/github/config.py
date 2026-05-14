"""GitHub token configuration.

Precedence (highest first):
1. Explicit CLI flag (--github-token).
2. CWD config file: ./.blindspot.yaml (where you invoke blindspot from).
3. Scanned-repo config file: <repo>/.blindspot.yaml.
4. User config file: ~/.config/blindspot/config.yaml.

A token is never read from environment variables — the same deliberate
choice as the narrative API key and the Bitbucket app password. Without
a token, blindspot falls back to the `gh` CLI's own credentials (if
installed and authenticated), then to anonymous access. Anonymous works
for public repos only; private repos need either `gh` or a token.

A classic PAT needs the `repo` scope; a fine-grained PAT needs
"Pull requests: read" + "Contents: read" on the target repos.

YAML schema:

    github:
      token: ghp_...
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

PROJECT_CONFIG_NAME = ".blindspot.yaml"
USER_CONFIG_PATH = Path.home() / ".config" / "blindspot" / "config.yaml"


@dataclass(frozen=True, slots=True)
class GitHubConfig:
    token: str = ""

    @property
    def has_token(self) -> bool:
        return bool(self.token)


class GitHubConfigError(RuntimeError):
    pass


def load_github_config(
    repo_path: Path | None = None,
    cli_token: str | None = None,
) -> GitHubConfig:
    """Resolve a GitHub token. Returns an empty config when none is
    found — the caller falls back to `gh` CLI / anonymous."""
    cwd_cfg = _load_yaml(Path.cwd() / PROJECT_CONFIG_NAME)
    repo_cfg = (
        _load_yaml(repo_path / PROJECT_CONFIG_NAME)
        if repo_path and repo_path.resolve() != Path.cwd().resolve()
        else {}
    )
    user_cfg = _load_yaml(USER_CONFIG_PATH)

    def pick(key: str, cli_value: str | None) -> str:
        if cli_value:
            return cli_value
        for cfg in (cwd_cfg, repo_cfg, user_cfg):
            section = cfg.get("github") or {}
            val = section.get(key)
            if val:
                return str(val)
        return ""

    return GitHubConfig(token=pick("token", cli_token))


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as e:
        raise GitHubConfigError(f"Invalid YAML in {path}: {e}") from e
    if not isinstance(data, dict):
        raise GitHubConfigError(
            f"{path} must be a YAML mapping at the top level."
        )
    return data


__all__ = [
    "PROJECT_CONFIG_NAME",
    "USER_CONFIG_PATH",
    "GitHubConfig",
    "GitHubConfigError",
    "load_github_config",
]
