"""Tests for rehash.config."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from rehash import __main__ as cli
from rehash.config import ConfigError, load_config

VALID_MINIMUM = "seiscomp: {}\n"


def write(tmp_path, text):
    path = tmp_path / "config.yaml"
    path.write_text(text)
    return path


@pytest.mark.parametrize(
    "text",
    [
        "false",
        "[]",
        "seiscomp: false",
        "seiscomp: []",
        "seiscomp: null",
        "seiscomp: {wait_time: true}",
        "seiscomp: {wait_time: -1}",
        "seiscomp: {reprocess: 'false'}",
        "logging: {level: nonsense}",
        "skhash: {timeout: .nan}",
        "logging: [",
    ],
)
def test_invalid_config_rejected(tmp_path, text):
    with pytest.raises(ConfigError):
        load_config(write(tmp_path, text))


def test_release_example():
    config = load_config(Path(__file__).resolve().parents[1] / "config.example.yaml")
    assert config.logging.level == "DEBUG"


@pytest.mark.parametrize("option", ["--help", "--version"])
def test_informational_cli_needs_no_config(monkeypatch, option):
    monkeypatch.setattr(cli.sys, "argv", ["rehash", option, "--config", "/missing.yaml"])
    with pytest.raises(SystemExit) as result:
        cli.main()
    assert result.value.code == 0


@pytest.mark.parametrize("args", [["--wait-time", "-1"], ["-w-1"], ["--config"]])
def test_invalid_cli_rejected(args):
    with pytest.raises(SystemExit) as result:
        cli._config_path_from_argv(["rehash", *args])
    assert result.value.code == 2


def test_cli_precedence(tmp_path):
    config = load_config(write(tmp_path, "seiscomp: {host: yaml-host, database: yaml-db}"))
    for arguments in (
        ["-H", "cli-host", "-d", "cli-db"],
        ["-Hcli-host", "-dcli-db"],
        ["--host=cli-host", "--database=cli-db"],
    ):
        argv = ["rehash", *arguments]
        assert cli._inject_connection_args(argv, config) == argv


def test_worker_failure_stops_before_listener(monkeypatch, tmp_path, caplog):
    monkeypatch.setattr(cli.sys, "argv", ["rehash", "--config", str(write(tmp_path, ""))])
    monkeypatch.setattr(cli.faulthandler, "register", Mock())
    executor = Mock()
    executor.submit.return_value.result.side_effect = RuntimeError("failed")
    monkeypatch.setattr(cli, "ProcessPoolExecutor", Mock(return_value=executor))
    listener = Mock()
    monkeypatch.setitem(
        cli.sys.modules, "rehash.app", SimpleNamespace(make_dispatch=Mock(), make_finalize=Mock())
    )
    monkeypatch.setitem(
        cli.sys.modules, "rehash.worker", SimpleNamespace(init_worker=Mock(), run_batch=Mock())
    )
    monkeypatch.setitem(
        cli.sys.modules, "rehash.scclient.listener", SimpleNamespace(EventListenerApp=listener)
    )
    assert cli.main() == 1
    listener.assert_not_called()
    executor.shutdown.assert_called_once_with(wait=True, cancel_futures=True)
    assert "Worker initialization failed" in caplog.text
    assert "Worker process ready" not in caplog.text


def test_defaults(tmp_path):
    config = load_config(write(tmp_path, VALID_MINIMUM))
    assert config.seiscomp.wait_time == 300
    assert config.logging.level == "DEBUG"
    assert config.skhash.npolmin == 8
    assert config.skhash.use_fortran is True
    assert config.skhash.recompute_lookup_table is True


def test_partial_override(tmp_path):
    config = load_config(write(tmp_path, "seiscomp:\n  wait_time: 60\nskhash:\n  npolmin: 10\n"))
    assert config.seiscomp.wait_time == 60
    assert config.skhash.npolmin == 10
    # untouched sections keep defaults
    assert config.skhash.nmc == 30


def test_empty_config_is_valid(tmp_path):
    config = load_config(write(tmp_path, ""))
    assert config.skhash.velocity_models == ["velocity_models/CRL.forhash.txt"]


@pytest.mark.parametrize(
    "key", ["bogus", "subscriptions", "pick_group", "focmech_group", "load_inventory"]
)
def test_unknown_key_rejected(tmp_path, key):
    with pytest.raises(ConfigError, match="Unknown keys"):
        load_config(write(tmp_path, f"seiscomp:\n  {key}: 1\n"))


def test_unknown_section_rejected(tmp_path):
    with pytest.raises(ConfigError, match="Unknown top-level"):
        load_config(write(tmp_path, "bogus:\n  a: 1\n"))


def test_empty_velocity_models_rejected(tmp_path):
    with pytest.raises(ConfigError, match="velocity_models"):
        load_config(write(tmp_path, VALID_MINIMUM + "skhash:\n  velocity_models: []\n"))


def test_invalid_timeout_rejected(tmp_path):
    with pytest.raises(ConfigError, match="timeout"):
        load_config(write(tmp_path, VALID_MINIMUM + "skhash:\n  timeout: 0\n"))


def test_missing_file_rejected(tmp_path):
    with pytest.raises(ConfigError, match="not found"):
        load_config(tmp_path / "nope.yaml")
