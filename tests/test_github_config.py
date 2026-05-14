from pathlib import Path

import pytest

from blindspot.collector.github.config import load_github_config


def test_cli_token_wins_over_yaml(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "blindspot.collector.github.config.USER_CONFIG_PATH",
        tmp_path / "absent.yaml",
    )
    cwd_dir = tmp_path / "cwd"
    cwd_dir.mkdir()
    monkeypatch.chdir(cwd_dir)
    (tmp_path / ".blindspot.yaml").write_text("github:\n  token: from-yaml\n")
    cfg = load_github_config(repo_path=tmp_path, cli_token="from-cli")
    assert cfg.token == "from-cli"
    assert cfg.has_token


def test_reads_cwd_blindspot_yaml(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "blindspot.collector.github.config.USER_CONFIG_PATH",
        tmp_path / "absent.yaml",
    )
    cwd_dir = tmp_path / "cwd"
    cwd_dir.mkdir()
    (cwd_dir / ".blindspot.yaml").write_text("github:\n  token: cwd-token\n")
    monkeypatch.chdir(cwd_dir)
    cfg = load_github_config()
    assert cfg.token == "cwd-token"
    assert cfg.has_token


def test_returns_empty_when_nothing_configured(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(
        "blindspot.collector.github.config.USER_CONFIG_PATH",
        tmp_path / "absent.yaml",
    )
    cwd_dir = tmp_path / "cwd"
    cwd_dir.mkdir()
    monkeypatch.chdir(cwd_dir)
    cfg = load_github_config(repo_path=tmp_path)
    assert cfg.token == ""
    assert not cfg.has_token
