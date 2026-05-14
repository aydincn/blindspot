"""Bitbucket Cloud credentials configuration.

Precedence (highest first):
1. Explicit CLI flags (--bitbucket-username, --bitbucket-app-password).
2. CWD config file: ./.blindspot.yaml (where you invoke blindspot from).
3. Scanned-repo config file: <repo>/.blindspot.yaml.
4. User config file: ~/.config/blindspot/config.yaml.

Credentials are never read from environment variables — the same
deliberate choice as the narrative API key. Bitbucket's REST API is
effectively closed to anonymous access for private repos, so without a
username + app password `--with-reviews` simply skips Bitbucket.

App passwords are created at Bitbucket → Personal settings → App
passwords, and need the `pullrequest:read` + `repository:read` scopes.

YAML schema:

    bitbucket:
      username: your-bitbucket-username
      app_password: ATBB...
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

PROJECT_CONFIG_NAME = ".blindspot.yaml"
USER_CONFIG_PATH = Path.home() / ".config" / "blindspot" / "config.yaml"


@dataclass(frozen=True, slots=True)
class BitbucketConfig:
    username: str = ""
    app_password: str = ""

    @property
    def is_complete(self) -> bool:
        return bool(self.username and self.app_password)


class BitbucketConfigError(RuntimeError):
    pass


def load_bitbucket_config(
    repo_path: Path | None = None,
    cli_username: str | None = None,
    cli_app_password: str | None = None,
) -> BitbucketConfig:
    """Resolve Bitbucket credentials. Returns an empty config when none
    are found — the caller decides whether that's fatal."""
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
            section = cfg.get("bitbucket") or {}
            val = section.get(key)
            if val:
                return str(val)
        return ""

    return BitbucketConfig(
        username=pick("username", cli_username),
        app_password=pick("app_password", cli_app_password),
    )


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as e:
        raise BitbucketConfigError(f"Invalid YAML in {path}: {e}") from e
    if not isinstance(data, dict):
        raise BitbucketConfigError(
            f"{path} must be a YAML mapping at the top level."
        )
    return data


__all__ = [
    "PROJECT_CONFIG_NAME",
    "USER_CONFIG_PATH",
    "BitbucketConfig",
    "BitbucketConfigError",
    "load_bitbucket_config",
]
