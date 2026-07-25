#!/usr/bin/env python3
# tests/exporter/test_excel_exporter.py
"""Integration tests for :class:`trajcenter.exporter.excel_exporter.ExcelExporter`.

> **Author**: Clément RACINET
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from trajcenter.converter.excel_converter import ExcelConverter
from trajcenter.core.trajectory import Trajectory
from trajcenter.exporter.excel_exporter import ExcelExporter
from trajcenter.exporter.options import ExportOptions


def _export(
    traj: Trajectory,
    dest: Path,
    options: ExportOptions | None = None,
) -> Path:
    """Export a trajectory to Excel.

    ABB Route:
        N/A — test helper.

    ABB Constraints:
        No ABB controller access.

    Args:
        traj: Source trajectory.
        dest: Destination directory.
        options: Optional export options.

    Returns:
        Exported workbook path.

    Raises:
        OSError: If export fails.

    Example:
        ::

            path = _export(traj, tmp_path)
    """
    return ExcelExporter(options).export(traj, dest)


def _sheets(path: Path) -> dict[str, pd.DataFrame]:
    """Read all sheets from an Excel workbook.

    ABB Route:
        N/A — test helper.

    ABB Constraints:
        No ABB controller access.

    Args:
        path: Workbook path.

    Returns:
        Mapping of sheet name to DataFrame.

    Raises:
        ValueError: If the workbook cannot be parsed.

    Example:
        ::

            sheets = _sheets(path)
    """
    return pd.read_excel(path, sheet_name=None, engine="openpyxl")


class TestExcelExporterOutput:
    """Tests for produced Excel workbook."""

    def test_produces_xlsx_file(self, traj_basic: Trajectory, tmp_path: Path) -> None:
        """An .xlsx file is created."""
        path = _export(traj_basic, tmp_path)
        assert path.exists()
        assert path.suffix == ".xlsx"

    def test_filename_matches_traj_name(
        self,
        traj_basic: Trajectory,
        tmp_path: Path,
    ) -> None:
        """The workbook stem matches the trajectory name."""
        path = _export(traj_basic, tmp_path)
        assert path.stem == traj_basic.meta.name

    def test_dest_dir_created_if_absent(
        self,
        traj_basic: Trajectory,
        tmp_path: Path,
    ) -> None:
        """The destination directory is created when absent."""
        path = _export(traj_basic, tmp_path / "nested" / "output")
        assert path.exists()

    def test_returns_absolute_path(
        self,
        traj_basic: Trajectory,
        tmp_path: Path,
    ) -> None:
        """export returns an absolute path."""
        path = _export(traj_basic, tmp_path)
        assert path.is_absolute()


class TestExcelExporterSheets:
    """Tests for workbook sheet structure."""

    def test_traj_sheet_present(self, traj_basic: Trajectory, tmp_path: Path) -> None:
        """The traj sheet is present."""
        assert "traj" in _sheets(_export(traj_basic, tmp_path))

    def test_meta_sheet_present_by_default(
        self,
        traj_basic: Trajectory,
        tmp_path: Path,
    ) -> None:
        """The meta sheet is present by default."""
        assert "meta" in _sheets(_export(traj_basic, tmp_path))

    def test_meta_sheet_absent_when_disabled(
        self,
        traj_basic: Trajectory,
        tmp_path: Path,
    ) -> None:
        """The meta sheet is absent when include_meta is False."""
        sheets = _sheets(
            _export(traj_basic, tmp_path, ExportOptions(include_meta=False))
        )
        assert "meta" not in sheets

    def test_tools_sheet_not_present(
        self,
        traj_basic: Trajectory,
        tmp_path: Path,
    ) -> None:
        """Legacy tools sheet is not produced."""
        assert "tools" not in _sheets(_export(traj_basic, tmp_path))

    def test_wobjs_sheet_not_present(
        self,
        traj_basic: Trajectory,
        tmp_path: Path,
    ) -> None:
        """Legacy wobjs sheet is not produced."""
        assert "wobjs" not in _sheets(_export(traj_basic, tmp_path))


class TestExcelExporterTrajSheet:
    """Tests for traj sheet content."""

    def test_row_count(self, traj_basic: Trajectory, tmp_path: Path) -> None:
        """The traj sheet has the same number of rows as the trajectory."""
        df = _sheets(_export(traj_basic, tmp_path))["traj"]
        assert len(df) == len(traj_basic.points)

    def test_v2_columns_present(self, traj_basic: Trajectory, tmp_path: Path) -> None:
        """Canonical v2 columns are present."""
        df = _sheets(_export(traj_basic, tmp_path))["traj"]
        for col in ["x", "y", "z", "tcp_speed", "zone_type", "tool_name", "wobj_name"]:
            assert col in df.columns

    def test_legacy_columns_absent(
        self,
        traj_basic: Trajectory,
        tmp_path: Path,
    ) -> None:
        """Legacy v1 columns are absent."""
        df = _sheets(_export(traj_basic, tmp_path))["traj"]
        for col in ["speed", "zone", "tool_index", "wobj_index"]:
            assert col not in df.columns

    def test_tcp_speed_numeric_without_v(
        self,
        traj_basic: Trajectory,
        tmp_path: Path,
    ) -> None:
        """tcp_speed is exported as numeric without RAPID v prefix."""
        df = _sheets(_export(traj_basic, tmp_path))["traj"]
        assert pd.api.types.is_numeric_dtype(df["tcp_speed"])
        assert df["tcp_speed"].iloc[1] == 250.5

    def test_zone_type_numeric(
        self,
        traj_basic: Trajectory,
        tmp_path: Path,
    ) -> None:
        """zone_type is exported as numeric and preserves 255."""
        df = _sheets(_export(traj_basic, tmp_path))["traj"]
        assert pd.api.types.is_numeric_dtype(df["zone_type"])
        assert df["zone_type"].tolist() == [10, 5, 255]

    def test_multi_names_inline(
        self,
        traj_multi_names: Trajectory,
        tmp_path: Path,
    ) -> None:
        """Multiple tool and wobj names are preserved inline."""
        df = _sheets(_export(traj_multi_names, tmp_path))["traj"]
        assert df["tool_name"].tolist() == ["Tool_A", "Tool_B"]
        assert df["wobj_name"].tolist() == ["Wobj_A", "Wobj_B"]

    def test_minimal_no_optional_columns(
        self,
        traj_minimal: Trajectory,
        tmp_path: Path,
    ) -> None:
        """Optional columns are not invented during export."""
        df = _sheets(_export(traj_minimal, tmp_path))["traj"]
        assert df.columns.tolist() == ["x", "y", "z", "q1", "q2", "q3", "q4"]


class TestExcelExporterMetaSheet:
    """Tests for meta sheet content."""

    def test_meta_has_key_value_columns(
        self,
        traj_with_meta: Trajectory,
        tmp_path: Path,
    ) -> None:
        """The meta sheet contains key/value columns."""
        df = _sheets(_export(traj_with_meta, tmp_path))["meta"]
        assert list(df.columns) == ["key", "value"]

    def test_meta_robot_model_value(
        self,
        traj_with_meta: Trajectory,
        tmp_path: Path,
    ) -> None:
        """The robot model is exported to the meta sheet."""
        df = _sheets(_export(traj_with_meta, tmp_path))["meta"]
        row = df[df["key"] == "robot_model"]
        assert row["value"].iloc[0] == "IRB6700-205/2.80"

    def test_meta_extra_fields_present(
        self,
        traj_with_meta: Trajectory,
        tmp_path: Path,
    ) -> None:
        """Extra metadata fields are exported to the meta sheet."""
        df = _sheets(_export(traj_with_meta, tmp_path))["meta"]
        assert "author" in df["key"].values
        assert "project" in df["key"].values


class TestExcelExporterRoundtrip:
    """Tests for Excel export/import roundtrip."""

    def test_roundtrip_point_count(
        self,
        traj_basic: Trajectory,
        tmp_path: Path,
    ) -> None:
        """Reloading the exported workbook preserves point count."""
        reloaded = ExcelConverter().convert(_export(traj_basic, tmp_path))
        assert len(reloaded.points) == len(traj_basic.points)

    def test_roundtrip_xyz_values(
        self,
        traj_basic: Trajectory,
        tmp_path: Path,
    ) -> None:
        """XYZ values are preserved after roundtrip."""
        reloaded = ExcelConverter().convert(_export(traj_basic, tmp_path))
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
        reloaded = ExcelConverter().convert(_export(traj_basic, tmp_path))
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
        reloaded = ExcelConverter().convert(_export(traj_multi_names, tmp_path))
        assert reloaded.points["tool_name"].tolist() == ["Tool_A", "Tool_B"]

    def test_roundtrip_meta_name(
        self,
        traj_with_meta: Trajectory,
        tmp_path: Path,
    ) -> None:
        """The trajectory name is preserved after roundtrip."""
        reloaded = ExcelConverter().convert(_export(traj_with_meta, tmp_path))
        assert reloaded.meta.name == traj_with_meta.meta.name

    def test_roundtrip_robot_model(
        self,
        traj_with_meta: Trajectory,
        tmp_path: Path,
    ) -> None:
        """The robot model is preserved after roundtrip."""
        reloaded = ExcelConverter().convert(_export(traj_with_meta, tmp_path))
        assert reloaded.meta.robot_model == traj_with_meta.meta.robot_model
