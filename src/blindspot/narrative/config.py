"""Narrative provider/model configuration.

Precedence (highest first):
1. Explicit CLI flags (--api-key, --model, --provider).
2. CWD config file: ./.blindspot.yaml (where you invoke blindspot from).
3. Scanned-repo config file: <repo>/.blindspot.yaml.
4. User config file: ~/.config/blindspot/config.yaml.

We never read API keys from environment variables — this is a deliberate choice
so reports can't pick up unrelated keys lying in a shell. Set them in the YAML
or pass on the command line.

YAML schema:

    narrative:
      provider: anthropic
      model: claude-haiku-4-5-20251001
      api_key: sk-ant-...
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

PROJECT_CONFIG_NAME = ".blindspot.yaml"
USER_CONFIG_PATH = Path.home() / ".config" / "blindspot" / "config.yaml"


@dataclass(frozen=True, slots=True)
class NarrativeConfig:
    provider: str = "anthropic"
    model: str = ""
    api_key: str = ""


class NarrativeConfigError(RuntimeError):
    pass


def load_narrative_config(
    repo_path: Path | None = None,
    cli_api_key: str | None = None,
    cli_model: str | None = None,
    cli_provider: str | None = None,
) -> NarrativeConfig:
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
            section = cfg.get("narrative") or {}
            val = section.get(key)
            if val:
                return str(val)
        return ""

    provider = pick("provider", cli_provider) or "anthropic"
    model = pick("model", cli_model)
    api_key = pick("api_key", cli_api_key)

    if not api_key:
        raise NarrativeConfigError(
            "No API key found. Add it to ./.blindspot.yaml (CWD), "
            "<scanned-repo>/.blindspot.yaml, "
            f"{USER_CONFIG_PATH}, or pass --api-key on the command line."
        )

    return NarrativeConfig(provider=provider, model=model, api_key=api_key)


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as e:
        raise NarrativeConfigError(f"Invalid YAML in {path}: {e}") from e
    if not isinstance(data, dict):
        raise NarrativeConfigError(f"{path} must be a YAML mapping at the top level.")
    return data


__all__ = [
    "NarrativeConfig",
    "NarrativeConfigError",
    "PROJECT_CONFIG_NAME",
    "USER_CONFIG_PATH",
    "load_narrative_config",
]
