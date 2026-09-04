#!/usr/bin/env python3
# tests/cli/test_main.py
"""Tests for the TrajCenter command line interface."""

from __future__ import annotations

from argparse import Namespace
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from trajcenter.cli.main import (
    build_parser,
    handle_convert_command,
    handle_export_command,
    infer_converter,
    infer_exporter,
    main,
)
from trajcenter.convert import AptConverter, CsvConverter, ExcelConverter, ModConverter
from trajcenter.export import CsvExporter, ExcelExporter


def test_convert_command_is_registered() -> None:
    """The convert command parses source and destination paths."""
    parser = build_parser()

    args = parser.parse_args(["convert", "input.csv", "trajectory_store"])

    assert args.command == "convert"
    assert args.source == Path("input.csv")
    assert args.dest_dir == Path("trajectory_store")
    assert args.name is None
    assert args.format is None


def test_convert_command_accepts_name_and_format() -> None:
    """The convert command accepts explicit output name and source format."""
    parser = build_parser()

    args = parser.parse_args(
        [
            "convert",
            "input.txt",
            "trajectory_store",
            "--name",
            "demo",
            "--format",
            "csv",
        ]
    )

    assert args.command == "convert"
    assert args.name == "demo"
    assert args.format == "csv"


def test_export_command_is_registered() -> None:
    """The export command parses source, destination and output format."""
    parser = build_parser()

    args = parser.parse_args(
        ["export", "trajectory_store/demo.trajcenter", "exports", "--format", "excel"]
    )

    assert args.command == "export"
    assert args.source == Path("trajectory_store/demo.trajcenter")
    assert args.dest_dir == Path("exports")
    assert args.format == "excel"


def test_infer_converter_from_extension() -> None:
    """Converters are inferred from source file extensions."""
    assert isinstance(infer_converter(Path("input.csv")), CsvConverter)
    assert isinstance(infer_converter(Path("input.xlsx")), ExcelConverter)
    assert isinstance(infer_converter(Path("input.aptsource")), AptConverter)
    assert isinstance(infer_converter(Path("input.mod")), ModConverter)


def test_infer_converter_from_format_override() -> None:
    """Explicit format overrides the source file extension."""
    assert isinstance(infer_converter(Path("input.data"), "csv"), CsvConverter)
    assert isinstance(infer_converter(Path("input.data"), "xlsx"), ExcelConverter)
    assert isinstance(infer_converter(Path("input.data"), "apt"), AptConverter)
    assert isinstance(infer_converter(Path("input.data"), "rapid"), ModConverter)


def test_infer_exporter() -> None:
    """Exporters are selected from the requested output format."""
    assert isinstance(infer_exporter("csv"), CsvExporter)
    assert isinstance(infer_exporter("excel"), ExcelExporter)
    assert isinstance(infer_exporter("xlsx"), ExcelExporter)


def test_handle_convert_command_returns_success() -> None:
    """The convert handler saves the converted trajectory."""
    converter = MagicMock()
    converter.convert_and_save.return_value = Path("trajectory_store/demo.trajcenter")

    args = Namespace(
        source=Path("input.csv"),
        dest_dir=Path("trajectory_store"),
        name="demo",
        format=None,
    )

    with patch("trajcenter.cli.main.infer_converter", return_value=converter):
        assert handle_convert_command(args) == 0

    converter.convert_and_save.assert_called_once_with(
        source=Path("input.csv"),
        dest_dir=Path("trajectory_store"),
        stem="demo",
    )


def test_handle_convert_command_returns_error() -> None:
    """The convert handler returns 1 on conversion errors."""
    args = Namespace(
        source=Path("missing.csv"),
        dest_dir=Path("trajectory_store"),
        name=None,
        format=None,
    )

    with patch(
        "trajcenter.cli.main.infer_converter",
        side_effect=ValueError("bad format"),
    ):
        assert handle_convert_command(args) == 1


def test_handle_export_command_returns_success() -> None:
    """The export handler loads and exports a .trajcenter archive."""
    trajectory = MagicMock()
    exporter = MagicMock()
    exporter.export.return_value = Path("exports/demo.csv")

    args = Namespace(
        source=Path("trajectory_store/demo.trajcenter"),
        dest_dir=Path("exports"),
        format="csv",
    )

    with (
        patch("trajcenter.cli.main.Trajectory.load", return_value=trajectory),
        patch("trajcenter.cli.main.infer_exporter", return_value=exporter),
    ):
        assert handle_export_command(args) == 0

    exporter.export.assert_called_once_with(trajectory, Path("exports"))


def test_handle_export_command_returns_error() -> None:
    """The export handler returns 1 on loading or export errors."""
    args = Namespace(
        source=Path("missing.trajcenter"),
        dest_dir=Path("exports"),
        format="csv",
    )

    with patch(
        "trajcenter.cli.main.Trajectory.load",
        side_effect=FileNotFoundError("missing"),
    ):
        assert handle_export_command(args) == 1


def test_main_robot_help(capsys):
    """The robot command should expose its help."""
    with pytest.raises(SystemExit) as exc_info:
        main(["robot", "--help"])

    captured = capsys.readouterr()

    assert exc_info.value.code == 0
    assert "ABB robot communication commands." in captured.out
    assert "check" in captured.out
    assert "supervise" in captured.out


def test_main_robot_check(capsys):
    """The robot check command should validate ABB API availability."""
    result = main(["robot", "check"])

    captured = capsys.readouterr()

    assert result == 0
    assert "Robot ABB API available." in captured.out


def test_main_robot_missing_subcommand(capsys):
    """The robot command should require a subcommand."""
    result = main(["robot"])

    captured = capsys.readouterr()

    assert result == 2
    assert "Missing robot command. Use: trajcenter robot --help" in captured.out


def test_main_robot_supervise_help(capsys):
    """The robot supervise command should expose its help."""
    with pytest.raises(SystemExit) as exc_info:
        main(["robot", "supervise", "--help"])

    captured = capsys.readouterr()

    assert exc_info.value.code == 0
    assert "Run the ABB robot supervision loop." in captured.out
    assert "--store" in captured.out
    assert "--task" in captured.out
    assert "--module" in captured.out
    assert "--mastership-retries" in captured.out
    assert "--log-level" in captured.out
    assert "--env-file" in captured.out
    assert "--env-override" in captured.out
    assert "--host" in captured.out
    assert "--port" in captured.out
    assert "--username" in captured.out
    assert "--password" in captured.out
    assert "--password-env" in captured.out
    assert "--timeout" in captured.out


def test_main_robot_supervise_calls_app_runner(monkeypatch):
    """The robot supervise command should call the package-level app runner."""
    calls = {}

    async def fake_runner(**kwargs):
        calls.update(kwargs)
        return 0

    monkeypatch.setattr(
        "trajcenter.robot.supervisor.run_rws_subscription_supervisor_app",
        fake_runner,
    )

    result = main(
        [
            "robot",
            "supervise",
            "--store",
            "custom_store",
            "--task",
            "T_ROB2",
            "--module",
            "CUSTOM_MODULE",
            "--mastership-retries",
            "5",
            "--log-level",
            "DEBUG",
            "--env-file",
            ".env.robot",
            "--env-override",
            "--host",
            "192.168.125.1",
            "--port",
            "80",
            "--username",
            "Default User",
            "--password",
            "robotics",
            "--timeout",
            "10.0",
        ]
    )

    assert result == 0
    assert calls["store_root"] == Path("custom_store")
    assert calls["task"] == "T_ROB2"
    assert calls["module"] == "CUSTOM_MODULE"
    assert calls["mastership_retries"] == 5
    assert calls["log_level"] == "DEBUG"
    assert calls["env_file"] == Path(".env.robot")
    assert calls["env_override"] is True
    assert calls["host"] == "192.168.125.1"
    assert calls["port"] == 80
    assert calls["username"] == "Default User"
    assert calls["password"] == "robotics"
    assert calls["timeout"] == 10.0


def test_main_robot_supervise_uses_password_env(monkeypatch):
    """The robot supervise command should resolve password from an environment variable."""
    calls = {}

    async def fake_runner(**kwargs):
        calls.update(kwargs)
        return 0

    monkeypatch.setenv("ABB_TEST_PASSWORD", "secret")

    monkeypatch.setattr(
        "trajcenter.robot.supervisor.run_rws_subscription_supervisor_app",
        fake_runner,
    )

    result = main(
        [
            "robot",
            "supervise",
            "--password-env",
            "ABB_TEST_PASSWORD",
        ]
    )

    assert result == 0
    assert calls["password"] == "secret"


def test_main_robot_supervise_rejects_password_and_password_env(capsys):
    """The robot supervise command should reject duplicate password sources."""
    result = main(
        [
            "robot",
            "supervise",
            "--password",
            "robotics",
            "--password-env",
            "ABB_TEST_PASSWORD",
        ]
    )

    captured = capsys.readouterr()

    assert result == 1
    assert "Use either --password or --password-env, not both." in captured.out


def test_main_robot_supervise_rejects_missing_password_env(capsys):
    """The robot supervise command should reject missing password environment variable."""
    result = main(
        [
            "robot",
            "supervise",
            "--password-env",
            "ABB_TEST_PASSWORD_MISSING",
        ]
    )

    captured = capsys.readouterr()

    assert result == 1
    assert (
        "Password environment variable is not set: ABB_TEST_PASSWORD_MISSING"
        in captured.out
    )


def test_main_tui_quit(monkeypatch, capsys):
    """The tui command should launch and exit cleanly."""
    monkeypatch.setattr("builtins.input", lambda _prompt: "q")

    result = main(["tui"])

    captured = capsys.readouterr()

    assert result == 0
    assert "Main menu" in captured.out
    assert "File conversion / trajectory store" in captured.out
