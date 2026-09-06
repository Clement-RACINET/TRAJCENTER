#!/usr/bin/env python3
"""Tests for the TrajCenter export Textual screen."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from textual.widgets import Select

from trajcenter.ui.config import UIConfig
from trajcenter.ui.screens.export import (
    ExportScreen,
    build_export_error_text,
    build_export_success_text,
    normalize_export_format,
)


def test_export_screen_uses_provided_config(tmp_path: Path) -> None:
    """ExportScreen should keep the provided UI configuration."""
    config = UIConfig(store=tmp_path)

    screen = ExportScreen(config)

    assert screen.config is config


def test_normalize_export_format_blank_values() -> None:
    """normalize_export_format should default to csv for blank values."""
    assert normalize_export_format(None) == "csv"
    assert normalize_export_format(Select.BLANK) == "csv"


def test_normalize_export_format_explicit_value() -> None:
    """normalize_export_format should return explicit format strings."""
    assert normalize_export_format("csv") == "csv"
    assert normalize_export_format("excel") == "excel"


def test_build_export_success_text(tmp_path: Path) -> None:
    """build_export_success_text should include the output path."""
    output = tmp_path / "demo.xlsx"

    text = build_export_success_text(output)

    assert "OK" in text.plain
    assert str(output) in text.plain


def test_build_export_error_text() -> None:
    """build_export_error_text should include the error message."""
    text = build_export_error_text(ValueError("bad export"))

    assert "Erreur" in text.plain
    assert "bad export" in text.plain


def test_export_screen_export_file(monkeypatch, tmp_path: Path) -> None:
    """ExportScreen.export_file should load a trajectory and export it."""
    source = tmp_path / "input.trajcenter"
    dest_dir = tmp_path / "exports"
    output = dest_dir / "input.csv"
    fake_trajectory = object()
    calls: dict[str, Any] = {}

    class FakeExporter:
        def export(self, trajectory: object, dest_dir: Path) -> Path:
            calls["trajectory"] = trajectory
            calls["dest_dir"] = dest_dir
            return output

    def fake_load(source_arg: Path) -> object:
        calls["source"] = source_arg
        return fake_trajectory

    def fake_infer_exporter(format_name: str) -> FakeExporter:
        calls["format_name"] = format_name
        return FakeExporter()

    monkeypatch.setattr(
        "trajcenter.ui.screens.export.Trajectory.load",
        fake_load,
    )
    monkeypatch.setattr(
        "trajcenter.ui.screens.export.infer_exporter",
        fake_infer_exporter,
    )

    screen = ExportScreen(UIConfig(store=tmp_path))

    result = screen.export_file(
        source=source,
        dest_dir=dest_dir,
        format_name="csv",
    )

    assert result == output
    assert calls == {
        "source": source,
        "format_name": "csv",
        "trajectory": fake_trajectory,
        "dest_dir": dest_dir,
    }
