#!/usr/bin/env python3
# tests/test_csv_converter.py
"""Unit tests for :mod:`trajcenter.converter.csv_converter`.

> **Author**: Clément RACINET

Covers:

- :func:`~trajcenter.converter.csv_converter._detect_separator`
- :class:`~trajcenter.converter.csv_converter.CsvConverter`

Common logic (``resolve_columns``, identity quaternion, autocompletion,
tools/wobjs tables) is tested in ``test_tabular_converter.py``.
This file focuses on CSV-specific behaviour: separator detection,
BOM encoding, ``source_format``, and roundtrip.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from trajcenter.converter.csv_converter import CsvConverter, _detect_separator
from trajcenter.converter.defaults import ConversionDefaults
from trajcenter.core.trajectory import SourceFormat, Trajectory


# ---------------------------------------------------------------------------
# Tests — _detect_separator
# ---------------------------------------------------------------------------


class TestDetectSeparator:
    """Tests for automatic separator detection."""

    def test_comma_detected(self, csv_simple: Path) -> None:
        """A comma is detected on a standard CSV file."""
        assert _detect_separator(csv_simple) == ","

    def test_semicolon_detected(self, csv_semicolon: Path) -> None:
        """A semicolon is detected on a French Excel export."""
        assert _detect_separator(csv_semicolon) == ";"

    def test_missing_file_returns_default(self, tmp_path: Path) -> None:
        """A non-existent file returns the default comma separator."""
        assert _detect_separator(tmp_path / "inexistant.csv") == ","

    def test_empty_file_returns_default(self, tmp_path: Path) -> None:
        """An empty file returns the default comma separator."""
        p = tmp_path / "empty.csv"
        p.write_text("", encoding="utf-8")
        assert _detect_separator(p) == ","


# ---------------------------------------------------------------------------
# Tests — CsvConverter
# ---------------------------------------------------------------------------


class TestCsvConverter:
    """Tests for the CsvConverter class."""

    # --- Basic errors ---

    def test_file_not_found_raises(self, tmp_path: Path) -> None:
        """``convert()`` raises ``FileNotFoundError`` when the file does not exist."""
        with pytest.raises(FileNotFoundError, match=r"not found|introuvable"):
            CsvConverter().convert(tmp_path / "inexistant.csv")

    def test_missing_xyz_raises(self, csv_missing_xyz: Path) -> None:
        """``convert()`` raises ``ValueError`` when XYZ columns are absent."""
        with pytest.raises(ValueError, match=r"mandatory columns missing"):
            CsvConverter().convert(csv_missing_xyz)

    # --- Metadata ---

    def test_source_format(self, csv_simple: Path) -> None:
        """``source_format`` is ``CSV``."""
        assert CsvConverter().convert(csv_simple).meta.source_format == SourceFormat.CSV

    def test_source_file(self, csv_simple: Path) -> None:
        """``source_file`` contains the file name."""
        assert CsvConverter().convert(csv_simple).meta.source_file == "simple.csv"

    def test_name(self, csv_simple: Path) -> None:
        """``name`` is the file stem."""
        assert CsvConverter().convert(csv_simple).meta.name == "simple"

    # --- Nominal content ---

    def test_point_count(self, csv_simple: Path) -> None:
        """A 2-row CSV produces 2 points."""
        assert CsvConverter().convert(csv_simple).point_count == 2

    def test_coordinates(self, csv_simple: Path) -> None:
        """x, y, z coordinates are correctly read."""
        traj = CsvConverter().convert(csv_simple)
        assert traj.points["x"].iloc[0] == pytest.approx(100.0)
        assert traj.points["y"].iloc[0] == pytest.approx(200.0)
        assert traj.points["z"].iloc[0] == pytest.approx(300.0)

    def test_quaternions(self, csv_simple: Path) -> None:
        """Quaternion values are correctly read."""
        traj = CsvConverter().convert(csv_simple)
        assert traj.points["q1"].iloc[0] == pytest.approx(1.0)
        assert traj.points["q2"].iloc[0] == pytest.approx(0.0)

    def test_required_geometry_columns_present(self, csv_simple: Path) -> None:
        """The produced trajectory contains required geometry columns."""
        traj = CsvConverter().convert(csv_simple)

        for col in ["x", "y", "z", "q1", "q2", "q3", "q4"]:
            assert col in traj.points.columns

    # --- Separator ---

    def test_semicolon_auto_detected(self, csv_semicolon: Path) -> None:
        """The semicolon separator is detected automatically."""
        traj = CsvConverter().convert(csv_semicolon)
        assert traj.point_count == 2
        assert traj.points["x"].iloc[0] == pytest.approx(10.0)

    def test_semicolon_forced(self, csv_semicolon: Path) -> None:
        """A forced semicolon separator works correctly."""
        traj = CsvConverter(separator=";").convert(csv_semicolon)
        assert traj.point_count == 2

    def test_comma_forced(self, csv_simple: Path) -> None:
        """A forced comma separator works correctly."""
        traj = CsvConverter(separator=",").convert(csv_simple)
        assert traj.point_count == 2

    # --- Encoding ---

    def test_bom_utf8_handled(self, csv_with_bom: Path) -> None:
        """A UTF-8 BOM file is correctly read (no ``'\\ufeffx'`` column)."""
        traj = CsvConverter().convert(csv_with_bom)
        assert "x" in traj.points.columns
        assert traj.points["x"].iloc[0] == pytest.approx(1.0)

    def test_custom_encoding(self, tmp_path: Path) -> None:
        """A forced Latin-1 encoding is correctly handled."""
        p = tmp_path / "latin1.csv"
        p.write_text("x,y,z\n1.0,2.0,3.0\n", encoding="latin-1")
        traj = CsvConverter(encoding="latin-1").convert(p)
        assert traj.point_count == 1

    # --- XYZ-only → identity quaternion ---

    def test_xyz_only_quaternion_identity(self, csv_xyz_only: Path) -> None:
        """Without quaternion columns, identity orientation is applied."""
        traj = CsvConverter().convert(csv_xyz_only)
        assert traj.points["q1"].iloc[0] == pytest.approx(1.0)
        assert traj.points["q2"].iloc[0] == pytest.approx(0.0)
        assert traj.points["q3"].iloc[0] == pytest.approx(0.0)
        assert traj.points["q4"].iloc[0] == pytest.approx(0.0)

    def test_xyz_only_quaternion_autocompleted(self, csv_xyz_only: Path) -> None:
        """Quaternion columns are listed in ``autocompleted``."""
        traj = CsvConverter().convert(csv_xyz_only)
        for col in ("q1", "q2", "q3", "q4"):
            assert col in traj.meta.autocompleted

    # --- Column aliases ---

    def test_aliases_resolved(self, csv_aliases: Path) -> None:
        """Column aliases are correctly resolved."""
        traj = CsvConverter().convert(csv_aliases)
        assert traj.points["x"].iloc[0] == pytest.approx(1.0)
        assert traj.points["tcp_speed"].iloc[0] == pytest.approx(500.0)
        assert traj.points["zone_type"].iloc[0] == 10

    # --- Tools / wobjs ---

    def test_tool_wobj_columns_imported_as_names(self, csv_with_tools: Path) -> None:
        """tool and wobj aliases are imported as v2 inline name columns."""
        traj = CsvConverter().convert(csv_with_tools)

        assert "tool_name" in traj.points.columns
        assert "wobj_name" in traj.points.columns
        assert "tool" not in traj.points.columns
        assert "wobj" not in traj.points.columns
        assert "tool_index" not in traj.points.columns
        assert "wobj_index" not in traj.points.columns

        assert traj.points["tool_name"].tolist() == ["Tool_A", "Tool_B"]
        assert traj.points["wobj_name"].tolist() == ["Wobj_A", "Wobj_A"]

    # --- Empty rows ---

    def test_empty_rows_dropped(self, csv_empty_rows: Path) -> None:
        """Fully empty rows are dropped."""
        assert CsvConverter().convert(csv_empty_rows).point_count == 2

    # --- Custom defaults ---

    def test_custom_default_tcp_speed(self, csv_xyz_only: Path) -> None:
        """The requested custom default tcp_speed is applied."""
        traj = CsvConverter(
            defaults=ConversionDefaults(
                autocomplete_columns={"tcp_speed"},
                tcp_speed=250.0,
            )
        ).convert(csv_xyz_only)

        assert traj.points["tcp_speed"].iloc[0] == pytest.approx(250.0)
        assert "tcp_speed" in traj.meta.autocompleted

    def test_custom_default_move_type(self, csv_xyz_only: Path) -> None:
        """The requested custom default move_type is applied."""
        traj = CsvConverter(
            defaults=ConversionDefaults(
                autocomplete_columns={"move_type"},
                move_type="MoveL",
            )
        ).convert(csv_xyz_only)

        assert traj.points["move_type"].iloc[0] == "MoveL"
        assert "move_type" in traj.meta.autocompleted

    # --- Full CSV ---

    def test_full_csv_move_types(self, csv_full: Path) -> None:
        """``MoveL`` and ``MoveJ`` are correctly read from a full CSV."""
        traj = CsvConverter().convert(csv_full)
        assert traj.points["move_type"].iloc[0] == "MoveL"
        assert traj.points["move_type"].iloc[1] == "MoveJ"

    def test_full_csv_tcp_speed_not_autocompleted(self, csv_full: Path) -> None:
        """tcp_speed present through speed alias is not listed in autocompleted."""
        traj = CsvConverter().convert(csv_full)
        assert "tcp_speed" not in traj.meta.autocompleted
        assert traj.points["tcp_speed"].iloc[0] == pytest.approx(500.0)
        assert traj.points["tcp_speed"].iloc[1] == pytest.approx(1000.0)

    def test_full_csv_zone_literals_normalized(self, csv_full: Path) -> None:
        """RAPID zone literals are normalised to integer zone_type."""
        traj = CsvConverter().convert(csv_full)
        assert traj.points["zone_type"].iloc[0] == 10
        assert traj.points["zone_type"].iloc[1] == 255

    # --- Roundtrip ---

    def test_full_roundtrip(self, tmp_path: Path, csv_simple: Path) -> None:
        """convert → save → load produces an equivalent trajectory."""
        traj = CsvConverter().convert(csv_simple)
        dest = tmp_path / "simple.trajcenter"
        traj.save(dest)
        loaded = Trajectory.load(dest)

        assert loaded.point_count == traj.point_count
        assert list(loaded.points.columns) == list(traj.points.columns)
        pd.testing.assert_series_equal(
            loaded.points["x"].reset_index(drop=True),
            traj.points["x"].reset_index(drop=True),
            check_names=False,
        )

    def test_convert_and_save(self, tmp_path: Path, csv_simple: Path) -> None:
        """``convert_and_save()`` creates the ``.trajcenter`` file."""
        result = CsvConverter().convert_and_save(source=csv_simple, dest_dir=tmp_path)
        assert result.exists()
        assert result.name == "simple.trajcenter"

    def test_convert_and_save_custom_stem(
        self, tmp_path: Path, csv_simple: Path
    ) -> None:
        """``convert_and_save()`` uses the custom stem when provided."""
        result = CsvConverter().convert_and_save(
            source=csv_simple, dest_dir=tmp_path, stem="ma_trajectoire"
        )
        assert result.name == "ma_trajectoire.trajcenter"
