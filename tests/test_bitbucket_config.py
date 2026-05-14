from pathlib import Path

import pytest

from blindspot.collector.bitbucket.config import load_bitbucket_config


def test_cli_flags_win_over_yaml(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "blindspot.collector.bitbucket.config.USER_CONFIG_PATH",
        tmp_path / "absent.yaml",
    )
    cwd_dir = tmp_path / "cwd"
    cwd_dir.mkdir()
    monkeypatch.chdir(cwd_dir)
    (tmp_path / ".blindspot.yaml").write_text(
        "bitbucket:\n  username: from-yaml\n  app_password: yaml-pw\n"
    )
    cfg = load_bitbucket_config(
        repo_path=tmp_path,
        cli_username="from-cli",
        cli_app_password="cli-pw",
    )
    assert cfg.username == "from-cli"
    assert cfg.app_password == "cli-pw"
    assert cfg.is_complete


def test_reads_cwd_blindspot_yaml(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "blindspot.collector.bitbucket.config.USER_CONFIG_PATH",
        tmp_path / "absent.yaml",
    )
    cwd_dir = tmp_path / "cwd"
    cwd_dir.mkdir()
    (cwd_dir / ".blindspot.yaml").write_text(
        "bitbucket:\n  username: cwd-user\n  app_password: cwd-pw\n"
    )
    monkeypatch.chdir(cwd_dir)
    cfg = load_bitbucket_config()
    assert cfg.username == "cwd-user"
    assert cfg.app_password == "cwd-pw"
    assert cfg.is_complete


def test_returns_incomplete_when_nothing_configured(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(
        "blindspot.collector.bitbucket.config.USER_CONFIG_PATH",
        tmp_path / "absent.yaml",
    )
    cwd_dir = tmp_path / "cwd"
    cwd_dir.mkdir()
    monkeypatch.chdir(cwd_dir)
    cfg = load_bitbucket_config(repo_path=tmp_path)
    assert cfg.username == ""
    assert cfg.app_password == ""
    assert not cfg.is_complete


def test_partial_config_is_not_complete(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    # Username only, no app password → not usable.
    monkeypatch.setattr(
        "blindspot.collector.bitbucket.config.USER_CONFIG_PATH",
        tmp_path / "absent.yaml",
    )
    cwd_dir = tmp_path / "cwd"
    cwd_dir.mkdir()
    monkeypatch.chdir(cwd_dir)
    cfg = load_bitbucket_config(repo_path=tmp_path, cli_username="alice")
    assert cfg.username == "alice"
    assert not cfg.is_complete
