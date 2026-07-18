#!/usr/bin/env python3
# tests/exporter/test_csv_exporter.py
"""Integration tests for :class:`trajcenter.exporter.csv_exporter.CsvExporter`.

Author: Clement RACINET
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from trajcenter.converter.csv_converter import CsvConverter
from trajcenter.core.trajectory import Trajectory
from trajcenter.exporter.csv_exporter import CsvExporter
from trajcenter.exporter.options import ExportOptions


def _export(
    traj: Trajectory,
    dest: Path,
    options: ExportOptions | None = None,
) -> Path:
    """Export a trajectory to CSV.

    ABB Route:
        N/A — test helper.

    ABB Constraints:
        No ABB controller access.

    Args:
        traj: Source trajectory.
        dest: Destination directory.
        options: Optional export options.

    Returns:
        Main exported CSV path.

    Raises:
        OSError: If export fails.

    Example:
        ::

            path = _export(traj, tmp_path)
    """
    return CsvExporter(options).export(traj, dest)


class TestCsvExporterOutput:
    """Tests for produced CSV files."""

    def test_main_csv_exists(self, traj_basic: Trajectory, tmp_path: Path) -> None:
        """The main CSV file is created."""
        path = _export(traj_basic, tmp_path)
        assert path.exists()

    def test_main_csv_suffix(self, traj_basic: Trajectory, tmp_path: Path) -> None:
        """The main file has a .csv extension."""
        path = _export(traj_basic, tmp_path)
        assert path.suffix == ".csv"

    def test_main_filename_matches_traj_name(
        self,
        traj_basic: Trajectory,
        tmp_path: Path,
    ) -> None:
        """The main file stem matches the trajectory name."""
        path = _export(traj_basic, tmp_path)
        assert path.stem == traj_basic.meta.name

    def test_meta_csv_exists_by_default(
        self,
        traj_basic: Trajectory,
        tmp_path: Path,
    ) -> None:
        """The metadata CSV file is created by default."""
        _export(traj_basic, tmp_path)
        assert (tmp_path / f"{traj_basic.meta.name}_meta.csv").exists()

    def test_meta_csv_absent_when_disabled(
        self,
        traj_basic: Trajectory,
        tmp_path: Path,
    ) -> None:
        """The metadata CSV file is absent when include_meta is False."""
        _export(traj_basic, tmp_path, ExportOptions(include_meta=False))
        assert not (tmp_path / f"{traj_basic.meta.name}_meta.csv").exists()

    def test_tools_csv_not_created(
        self,
        traj_basic: Trajectory,
        tmp_path: Path,
    ) -> None:
        """Legacy tools CSV is not created."""
        _export(traj_basic, tmp_path)
        assert not (tmp_path / f"{traj_basic.meta.name}_tools.csv").exists()

    def test_wobjs_csv_not_created(
        self,
        traj_basic: Trajectory,
        tmp_path: Path,
    ) -> None:
        """Legacy wobjs CSV is not created."""
        _export(traj_basic, tmp_path)
        assert not (tmp_path / f"{traj_basic.meta.name}_wobjs.csv").exists()

    def test_dest_dir_created_if_absent(
        self,
        traj_basic: Trajectory,
        tmp_path: Path,
    ) -> None:
        """The destination directory is created when absent."""
        dest = tmp_path / "nested" / "output"
        path = _export(traj_basic, dest)
        assert path.exists()

    def test_returns_absolute_path(
        self,
        traj_basic: Trajectory,
        tmp_path: Path,
    ) -> None:
        """export returns an absolute path."""
        path = _export(traj_basic, tmp_path)
        assert path.is_absolute()


class TestCsvExporterMainFile:
    """Tests for main CSV content."""

    def test_row_count(self, traj_basic: Trajectory, tmp_path: Path) -> None:
        """The exported file has the same number of rows as the trajectory."""
        df = pd.read_csv(_export(traj_basic, tmp_path), encoding="utf-8-sig")
        assert len(df) == len(traj_basic.points)

    def test_v2_columns_present(self, traj_basic: Trajectory, tmp_path: Path) -> None:
        """Canonical v2 columns are present."""
        df = pd.read_csv(_export(traj_basic, tmp_path), encoding="utf-8-sig")
        for col in ["x", "y", "z", "tcp_speed", "zone_type", "tool_name", "wobj_name"]:
            assert col in df.columns

    def test_legacy_columns_absent(
        self,
        traj_basic: Trajectory,
        tmp_path: Path,
    ) -> None:
        """Legacy v1 columns are absent."""
        df = pd.read_csv(_export(traj_basic, tmp_path), encoding="utf-8-sig")
        for col in ["speed", "zone", "tool_index", "wobj_index"]:
            assert col not in df.columns

    def test_tcp_speed_numeric_without_v(
        self,
        traj_basic: Trajectory,
        tmp_path: Path,
    ) -> None:
        """tcp_speed is numeric and not a RAPID literal."""
        df = pd.read_csv(_export(traj_basic, tmp_path), encoding="utf-8-sig")
        assert pd.api.types.is_numeric_dtype(df["tcp_speed"])
        assert df["tcp_speed"].iloc[1] == 250.5

    def test_zone_type_numeric(
        self,
        traj_basic: Trajectory,
        tmp_path: Path,
    ) -> None:
        """zone_type is numeric and preserves 255 for fine."""
        df = pd.read_csv(_export(traj_basic, tmp_path), encoding="utf-8-sig")
        assert pd.api.types.is_numeric_dtype(df["zone_type"])
        assert df["zone_type"].tolist() == [10, 5, 255]

    def test_multi_tool_names_inline(
        self,
        traj_multi_names: Trajectory,
        tmp_path: Path,
    ) -> None:
        """Multiple tool names are preserved inline."""
        df = pd.read_csv(_export(traj_multi_names, tmp_path), encoding="utf-8-sig")
        assert df["tool_name"].tolist() == ["Tool_A", "Tool_B"]

    def test_minimal_no_optional_columns(
        self,
        traj_minimal: Trajectory,
        tmp_path: Path,
    ) -> None:
        """Optional columns are not invented during export."""
        df = pd.read_csv(_export(traj_minimal, tmp_path), encoding="utf-8-sig")
        assert df.columns.tolist() == ["x", "y", "z", "q1", "q2", "q3", "q4"]


class TestCsvExporterEncoding:
    """Tests for CSV encoding and separator options."""

    def test_default_encoding_utf8_sig(
        self,
        traj_basic: Trajectory,
        tmp_path: Path,
    ) -> None:
        """The default CSV encoding includes a UTF-8 BOM."""
        path = _export(traj_basic, tmp_path)
        assert path.read_bytes()[:3] == b"\xef\xbb\xbf"

    def test_custom_separator_semicolon(
        self,
        traj_basic: Trajectory,
        tmp_path: Path,
    ) -> None:
        """A semicolon separator produces a readable CSV."""
        path = _export(traj_basic, tmp_path, ExportOptions(csv_separator=";"))
        df = pd.read_csv(path, sep=";", encoding="utf-8-sig")
        assert "x" in df.columns

    def test_custom_encoding_utf8(
        self,
        traj_basic: Trajectory,
        tmp_path: Path,
    ) -> None:
        """UTF-8 encoding without BOM is supported."""
        path = _export(traj_basic, tmp_path, ExportOptions(csv_encoding="utf-8"))
        assert path.read_bytes()[:3] != b"\xef\xbb\xbf"


class TestCsvExporterMetaFile:
    """Tests for metadata CSV content."""

    def test_meta_has_key_value_columns(
        self,
        traj_with_meta: Trajectory,
        tmp_path: Path,
    ) -> None:
        """The metadata file contains key/value columns."""
        _export(traj_with_meta, tmp_path)
        df = pd.read_csv(
            tmp_path / f"{traj_with_meta.meta.name}_meta.csv",
            encoding="utf-8-sig",
        )
        assert list(df.columns) == ["key", "value"]

    def test_meta_robot_model_value(
        self,
        traj_with_meta: Trajectory,
        tmp_path: Path,
    ) -> None:
        """The robot model is exported to metadata."""
        _export(traj_with_meta, tmp_path)
        df = pd.read_csv(
            tmp_path / f"{traj_with_meta.meta.name}_meta.csv",
            encoding="utf-8-sig",
        )
        row = df[df["key"] == "robot_model"]
        assert row["value"].iloc[0] == "IRB6700-205/2.80"

    def test_meta_extra_author(
        self,
        traj_with_meta: Trajectory,
        tmp_path: Path,
    ) -> None:
        """Extra metadata is exported to metadata CSV."""
        _export(traj_with_meta, tmp_path)
        df = pd.read_csv(
            tmp_path / f"{traj_with_meta.meta.name}_meta.csv",
            encoding="utf-8-sig",
        )
        row = df[df["key"] == "author"]
        assert row["value"].iloc[0] == "Jean Dupont"


class TestCsvExporterRoundtrip:
    """Tests for CSV export/import roundtrip."""

    def test_roundtrip_point_count(
        self,
        traj_basic: Trajectory,
        tmp_path: Path,
    ) -> None:
        """Reloading the exported CSV preserves point count."""
        reloaded = CsvConverter().convert(_export(traj_basic, tmp_path))
        assert len(reloaded.points) == len(traj_basic.points)

    def test_roundtrip_xyz_values(
        self,
        traj_basic: Trajectory,
        tmp_path: Path,
    ) -> None:
        """XYZ values are preserved after roundtrip."""
        reloaded = CsvConverter().convert(_export(traj_basic, tmp_path))
        for col in ["x", "y", "z"]:
            pd.testing.assert_series_equal(
                reloaded.points[col].reset_index(drop=True),
                traj_basic.points[col].reset_index(drop=True),
                check_names=False,
                atol=1e-4,
            )

    def test_roundtrip_tcp_speed(
        self,
        traj_basic: Trajectory,
        tmp_path: Path,
    ) -> None:
        """tcp_speed values are preserved after roundtrip."""
        reloaded = CsvConverter().convert(_export(traj_basic, tmp_path))
        pd.testing.assert_series_equal(
            reloaded.points["tcp_speed"].reset_index(drop=True),
            traj_basic.points["tcp_speed"].reset_index(drop=True),
            check_names=False,
        )

    def test_roundtrip_tool_names(
        self,
        traj_multi_names: Trajectory,
        tmp_path: Path,
    ) -> None:
        """tool_name values are preserved after roundtrip."""
        reloaded = CsvConverter().convert(_export(traj_multi_names, tmp_path))
        assert reloaded.points["tool_name"].tolist() == ["Tool_A", "Tool_B"]
