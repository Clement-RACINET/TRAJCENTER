#!/usr/bin/env python3
# tests/cli/test_main.py
"""Tests for the TrajCenter command line interface."""

from __future__ import annotations

from argparse import Namespace
from pathlib import Path
from unittest.mock import MagicMock, patch

from trajcenter.cli.main import (
    build_parser,
    handle_convert_command,
    handle_export_command,
    infer_converter,
    infer_exporter,
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
