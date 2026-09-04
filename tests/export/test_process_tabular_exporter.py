#!/usr/bin/env python3
# tests/export/test_process_tabular_exporter.py
"""Process export tests for tabular exporters.

> **Author**: Clément RACINET

These tests validate process-aware exports to Excel and CSV:

- ``process_param_index`` in trajectory outputs;
- ``process_type`` and ``process_param_names`` in metadata outputs;
- ``process_params`` sheet/sidecar;
- process roundtrip through tabular converters.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import pytest

from trajcenter.convert.csv_converter import CsvConverter
from trajcenter.convert.excel_converter import ExcelConverter
from trajcenter.core.trajectory import (
    SourceFormat,
    Trajectory,
    TrajectoryMeta,
    TrajectoryProcess,
)
from trajcenter.export.csv_exporter import CsvExporter
from trajcenter.export.excel_exporter import ExcelExporter
from trajcenter.export.options import ExportOptions
from trajcenter.export.tabular_exporter import _TabularExporter


def _make_process_trajectory() -> Trajectory:
    """Build a valid process trajectory for exporter tests.

    ABB Route:
        N/A — test fixture helper.

    ABB Constraints:
        No ABB controller access.

    Args:
        None.

    Returns:
        Valid process trajectory.

    Raises:
        pydantic.ValidationError: If metadata is invalid.
        ValueError: If trajectory process consistency is invalid.

    Example:
        ::

            traj = _make_process_trajectory()
    """
    points = pd.DataFrame(
        {
            "x": [100.0, 200.0, 300.0],
            "y": [10.0, 20.0, 30.0],
            "z": [1.0, 2.0, 3.0],
            "q1": [1.0, 1.0, 1.0],
            "q2": [0.0, 0.0, 0.0],
            "q3": [0.0, 0.0, 0.0],
            "q4": [0.0, 0.0, 0.0],
            "move_type": ["MoveL", "MoveL", "MoveJ"],
            "tcp_speed": [500.0, 500.0, 250.0],
            "zone_type": [10, 10, 255],
            "tool_name": ["tool0", "tool0", "tool0"],
            "wobj_name": ["wobj0", "wobj0", "wobj0"],
            "process_param_index": [1, 2, 0],
        }
    )
    process_params = pd.DataFrame(
        {
            "process_param_index": [1, 2],
            "force": [120.0, 150.0],
            "travel_speed": [35.0, 40.0],
        }
    )
    meta = TrajectoryMeta(
        name="process_export",
        source_file="process_export.trajcenter",
        source_format=SourceFormat.TRAJCENTER,
        created_at=datetime(2026, 7, 8, 12, 0, 0, tzinfo=UTC),
        process=TrajectoryProcess(
            process_type=1,
            process_param_names=["force", "travel_speed"],
        ),
        extra={"author": "Clément RACINET"},
    )
    return Trajectory(meta=meta, points=points, process_params=process_params)


def _meta_as_dict(meta_df: pd.DataFrame) -> dict[str, str]:
    """Convert an exported key/value metadata DataFrame to a dictionary.

    ABB Route:
        N/A — test helper.

    ABB Constraints:
        No ABB controller access.

    Args:
        meta_df: Exported metadata DataFrame.

    Returns:
        Metadata as string dictionary.

    Raises:
        KeyError: If ``key`` or ``value`` columns are missing.

    Example:
        ::

            data = _meta_as_dict(meta_df)
    """
    return {
        str(key): str(value)
        for key, value in zip(meta_df["key"], meta_df["value"], strict=False)
    }


class TestTabularProcessDataFrames:
    """Tests for process DataFrames built by the abstract tabular exporter."""

    def test_build_traj_df_exports_process_param_index_by_default(self) -> None:
        """process_param_index is part of the default export schema."""
        traj = _make_process_trajectory()
        df = ExcelExporter()._build_traj_df(traj)

        assert "process_param_index" in df.columns
        assert df["process_param_index"].tolist() == [1, 2, 0]

    def test_build_meta_df_exports_process_metadata(self) -> None:
        """process_type and process_param_names are exported to metadata."""
        traj = _make_process_trajectory()
        meta_df = _TabularExporter._build_meta_df(traj)
        meta = _meta_as_dict(meta_df)

        assert meta["process_type"] == "1"
        assert meta["process_param_names"] == "force;travel_speed"

    def test_build_meta_df_exports_extra_metadata(self) -> None:
        """Extra metadata remains exported alongside process metadata."""
        traj = _make_process_trajectory()
        meta_df = _TabularExporter._build_meta_df(traj)
        meta = _meta_as_dict(meta_df)

        assert meta["author"] == "Clément RACINET"


class TestExcelProcessExport:
    """Tests for Excel process export."""

    def test_excel_export_writes_process_params_sheet(self, tmp_path: Path) -> None:
        """A process trajectory exports a process_params sheet."""
        traj = _make_process_trajectory()
        path = ExcelExporter().export(traj, tmp_path)

        sheets = pd.read_excel(path, sheet_name=None, engine="openpyxl")

        assert "traj" in sheets
        assert "meta" in sheets
        assert "process_params" in sheets

    def test_excel_export_traj_contains_process_param_index(
        self,
        tmp_path: Path,
    ) -> None:
        """The Excel traj sheet contains process_param_index."""
        traj = _make_process_trajectory()
        path = ExcelExporter().export(traj, tmp_path)

        traj_df = pd.read_excel(path, sheet_name="traj", engine="openpyxl")

        assert "process_param_index" in traj_df.columns
        assert traj_df["process_param_index"].tolist() == [1, 2, 0]

    def test_excel_export_meta_contains_process_fields(
        self,
        tmp_path: Path,
    ) -> None:
        """The Excel meta sheet contains process metadata."""
        traj = _make_process_trajectory()
        path = ExcelExporter().export(traj, tmp_path)

        meta_df = pd.read_excel(path, sheet_name="meta", engine="openpyxl")
        meta = _meta_as_dict(meta_df)

        assert meta["process_type"] == "1"
        assert meta["process_param_names"] == "force;travel_speed"

    def test_excel_export_process_params_content(self, tmp_path: Path) -> None:
        """The Excel process_params sheet preserves process parameter values."""
        traj = _make_process_trajectory()
        path = ExcelExporter().export(traj, tmp_path)

        df = pd.read_excel(path, sheet_name="process_params", engine="openpyxl")

        assert df.columns.tolist() == [
            "process_param_index",
            "force",
            "travel_speed",
        ]
        assert df["process_param_index"].tolist() == [1, 2]
        assert df["force"].tolist() == pytest.approx([120.0, 150.0])
        assert df["travel_speed"].tolist() == pytest.approx([35.0, 40.0])

    def test_excel_export_process_roundtrip(self, tmp_path: Path) -> None:
        """Excel process export can be imported back as a process trajectory."""
        traj = _make_process_trajectory()
        path = ExcelExporter().export(traj, tmp_path)

        with pytest.warns(UserWarning, match="force|travel_speed|Unknown|inconnue"):
            reloaded = ExcelConverter().convert(path)

        assert reloaded.has_process is True
        assert reloaded.meta.process.process_type == 1
        assert reloaded.meta.process.process_param_names == ["force", "travel_speed"]
        assert reloaded.process_params is not None
        assert reloaded.points["process_param_index"].tolist() == [1, 2, 0]
        assert reloaded.process_params["force"].tolist() == pytest.approx(
            [120.0, 150.0]
        )

    def test_excel_no_process_params_sheet_when_no_process(
        self,
        traj_minimal: Trajectory,
        tmp_path: Path,
    ) -> None:
        """A non-process trajectory does not export process_params sheet."""
        path = ExcelExporter().export(traj_minimal, tmp_path)
        sheets = pd.read_excel(path, sheet_name=None, engine="openpyxl")

        assert "process_params" not in sheets


class TestCsvProcessExport:
    """Tests for CSV process export."""

    def test_csv_export_writes_process_params_sidecar(self, tmp_path: Path) -> None:
        """A process trajectory exports a process_params CSV sidecar."""
        traj = _make_process_trajectory()
        main = CsvExporter().export(traj, tmp_path)

        assert main.exists()
        assert (tmp_path / "process_export_meta.csv").exists()
        assert (tmp_path / "process_export_process_params.csv").exists()

    def test_csv_export_traj_contains_process_param_index(
        self,
        tmp_path: Path,
    ) -> None:
        """The main CSV contains process_param_index."""
        traj = _make_process_trajectory()
        main = CsvExporter().export(traj, tmp_path)

        df = pd.read_csv(main, encoding="utf-8-sig")

        assert "process_param_index" in df.columns
        assert df["process_param_index"].tolist() == [1, 2, 0]

    def test_csv_export_meta_contains_process_fields(self, tmp_path: Path) -> None:
        """The CSV meta sidecar contains process metadata."""
        traj = _make_process_trajectory()
        CsvExporter().export(traj, tmp_path)

        meta_df = pd.read_csv(
            tmp_path / "process_export_meta.csv",
            encoding="utf-8-sig",
        )
        meta = _meta_as_dict(meta_df)

        assert meta["process_type"] == "1"
        assert meta["process_param_names"] == "force;travel_speed"

    def test_csv_export_process_params_content(self, tmp_path: Path) -> None:
        """The CSV process sidecar preserves process parameter values."""
        traj = _make_process_trajectory()
        CsvExporter().export(traj, tmp_path)

        df = pd.read_csv(
            tmp_path / "process_export_process_params.csv",
            encoding="utf-8-sig",
        )

        assert df.columns.tolist() == [
            "process_param_index",
            "force",
            "travel_speed",
        ]
        assert df["process_param_index"].tolist() == [1, 2]
        assert df["force"].tolist() == pytest.approx([120.0, 150.0])
        assert df["travel_speed"].tolist() == pytest.approx([35.0, 40.0])

    def test_csv_export_process_roundtrip(self, tmp_path: Path) -> None:
        """CSV process export can be imported back as a process trajectory."""
        traj = _make_process_trajectory()
        main = CsvExporter().export(traj, tmp_path)

        with pytest.warns(UserWarning, match="force|travel_speed|Unknown|inconnue"):
            reloaded = CsvConverter().convert(main)

        assert reloaded.has_process is True
        assert reloaded.meta.process.process_type == 1
        assert reloaded.meta.process.process_param_names == ["force", "travel_speed"]
        assert reloaded.process_params is not None
        assert reloaded.points["process_param_index"].tolist() == [1, 2, 0]
        assert reloaded.process_params["force"].tolist() == pytest.approx(
            [120.0, 150.0]
        )

    def test_csv_no_process_params_sidecar_when_no_process(
        self,
        traj_minimal: Trajectory,
        tmp_path: Path,
    ) -> None:
        """A non-process trajectory does not export process_params sidecar."""
        CsvExporter().export(traj_minimal, tmp_path)

        assert not (tmp_path / "traj_minimal_process_params.csv").exists()

    def test_csv_no_meta_but_process_params_still_exported(
        self,
        tmp_path: Path,
    ) -> None:
        """Disabling metadata does not suppress process_params export."""
        traj = _make_process_trajectory()
        CsvExporter(ExportOptions(include_meta=False)).export(traj, tmp_path)

        assert not (tmp_path / "process_export_meta.csv").exists()
        assert (tmp_path / "process_export_process_params.csv").exists()
