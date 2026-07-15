#!/usr/bin/env python3
# tests/exporter/test_excel_exporter.py
"""Integration tests for :class:`~trajcenter.exporter.excel_exporter.ExcelExporter`.

Author: Clement RACINET

Verifies the structure of the produced ``.xlsx`` file and the import/export
symmetry with :class:`~trajcenter.converter.excel_converter.ExcelConverter`.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from trajcenter.converter.excel_converter import ExcelConverter
from trajcenter.core.trajectory import Trajectory
from trajcenter.exporter.excel_exporter import ExcelExporter
from trajcenter.exporter.options import ExportOptions


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _export(
    traj: Trajectory,
    dest: Path,
    options: ExportOptions | None = None,
) -> Path:
    """Run ``ExcelExporter.export()`` and return the produced file path.

    Args:
        traj: Source trajectory to export.
        dest: Destination directory.
        options: Optional export options. Uses defaults when ``None``.

    Returns:
        Absolute path to the exported ``.xlsx`` file.
    """
    return ExcelExporter(options).export(traj, dest)


def _sheets(path: Path) -> dict[str, pd.DataFrame]:
    """Load all sheets from an Excel workbook.

    Args:
        path: Path to the ``.xlsx`` file.

    Returns:
        Dict mapping sheet name to its ``DataFrame``.
    """
    return pd.read_excel(path, sheet_name=None, engine="openpyxl")


# ---------------------------------------------------------------------------
# Produced file
# ---------------------------------------------------------------------------


class TestExcelExporterOutput:
    """Tests verifying that the expected output file is created."""

    def test_produces_xlsx_file(self, traj_basic: Trajectory, tmp_path: Path) -> None:
        """An ``.xlsx`` file is created at the destination."""
        path = _export(traj_basic, tmp_path)
        assert path.exists()
        assert path.suffix == ".xlsx"

    def test_filename_matches_traj_name(
        self, traj_basic: Trajectory, tmp_path: Path
    ) -> None:
        """The file stem matches the trajectory name."""
        path = _export(traj_basic, tmp_path)
        assert path.stem == traj_basic.meta.name

    def test_dest_dir_created_if_absent(
        self, traj_basic: Trajectory, tmp_path: Path
    ) -> None:
        """The destination directory is created when it does not exist."""
        dest = tmp_path / "nested" / "output"
        path = _export(traj_basic, dest)
        assert path.exists()

    def test_returns_absolute_path(
        self, traj_basic: Trajectory, tmp_path: Path
    ) -> None:
        """``export()`` returns an absolute path."""
        path = _export(traj_basic, tmp_path)
        assert path.is_absolute()


# ---------------------------------------------------------------------------
# Sheets present
# ---------------------------------------------------------------------------


class TestExcelExporterSheets:
    """Tests verifying which sheets are present in the workbook."""

    def test_traj_sheet_present(self, traj_basic: Trajectory, tmp_path: Path) -> None:
        """The ``traj`` sheet is present."""
        sheets = _sheets(_export(traj_basic, tmp_path))
        assert "traj" in sheets

    def test_tools_sheet_present(self, traj_basic: Trajectory, tmp_path: Path) -> None:
        """The ``tools`` sheet is present."""
        sheets = _sheets(_export(traj_basic, tmp_path))
        assert "tools" in sheets

    def test_wobjs_sheet_present(self, traj_basic: Trajectory, tmp_path: Path) -> None:
        """The ``wobjs`` sheet is present."""
        sheets = _sheets(_export(traj_basic, tmp_path))
        assert "wobjs" in sheets

    def test_meta_sheet_present_by_default(
        self, traj_basic: Trajectory, tmp_path: Path
    ) -> None:
        """The ``meta`` sheet is present by default."""
        sheets = _sheets(_export(traj_basic, tmp_path))
        assert "meta" in sheets

    def test_meta_sheet_absent_when_disabled(
        self, traj_basic: Trajectory, tmp_path: Path
    ) -> None:
        """The ``meta`` sheet is absent when ``include_meta=False``."""
        opts = ExportOptions(include_meta=False)
        sheets = _sheets(_export(traj_basic, tmp_path, opts))
        assert "meta" not in sheets


# ---------------------------------------------------------------------------
# traj sheet content
# ---------------------------------------------------------------------------


class TestExcelExporterTrajSheet:
    """Tests verifying the content of the ``traj`` sheet."""

    def test_row_count(self, traj_basic: Trajectory, tmp_path: Path) -> None:
        """The ``traj`` sheet contains the same number of rows as the trajectory."""
        df = _sheets(_export(traj_basic, tmp_path))["traj"]
        assert len(df) == len(traj_basic.points)

    def test_xyz_columns_present(self, traj_basic: Trajectory, tmp_path: Path) -> None:
        """The x, y, z columns are present in the ``traj`` sheet."""
        df = _sheets(_export(traj_basic, tmp_path))["traj"]
        for col in ["x", "y", "z"]:
            assert col in df.columns

    def test_tool_column_resolved(self, traj_basic: Trajectory, tmp_path: Path) -> None:
        """The ``tool`` column contains string names, not integer indices."""
        df = _sheets(_export(traj_basic, tmp_path))["traj"]
        assert "tool" in df.columns
        # StringDtype (pandas 2.x) or object (pandas 1.x) — both are strings
        assert not pd.api.types.is_integer_dtype(df["tool"])
        assert df["tool"].iloc[0] == "tool0"

    def test_wobj_column_resolved(self, traj_basic: Trajectory, tmp_path: Path) -> None:
        """The ``wobj`` column is present in the ``traj`` sheet."""
        df = _sheets(_export(traj_basic, tmp_path))["traj"]
        assert "wobj" in df.columns

    def test_tool_index_not_in_traj_sheet(
        self, traj_basic: Trajectory, tmp_path: Path
    ) -> None:
        """The raw ``tool_index`` column is not present in the ``traj`` sheet."""
        df = _sheets(_export(traj_basic, tmp_path))["traj"]
        assert "tool_index" not in df.columns

    def test_wobj_index_not_in_traj_sheet(
        self, traj_basic: Trajectory, tmp_path: Path
    ) -> None:
        """The raw ``wobj_index`` column is not present in the ``traj`` sheet."""
        df = _sheets(_export(traj_basic, tmp_path))["traj"]
        assert "wobj_index" not in df.columns

    def test_multi_tools_names_in_traj(
        self, traj_multi_tools: Trajectory, tmp_path: Path
    ) -> None:
        """All tool names appear in the ``traj`` sheet when multiple tools are used."""
        df = _sheets(_export(traj_multi_tools, tmp_path))["traj"]
        assert set(df["tool"].unique()) == {"Tool_A", "Tool_B"}


# ---------------------------------------------------------------------------
# tools / wobjs sheets content
# ---------------------------------------------------------------------------


class TestExcelExporterToolsWobjsSheets:
    """Tests verifying the content of the ``tools`` and ``wobjs`` sheets."""

    def test_tools_sheet_name_column(
        self, traj_basic: Trajectory, tmp_path: Path
    ) -> None:
        """The ``tools`` sheet contains a ``name`` column."""
        df = _sheets(_export(traj_basic, tmp_path))["tools"]
        assert "name" in df.columns

    def test_tools_sheet_single_tool(
        self, traj_basic: Trajectory, tmp_path: Path
    ) -> None:
        """The ``tools`` sheet lists the single tool name correctly."""
        df = _sheets(_export(traj_basic, tmp_path))["tools"]
        assert df["name"].tolist() == ["tool0"]

    def test_tools_sheet_multi_tools(
        self, traj_multi_tools: Trajectory, tmp_path: Path
    ) -> None:
        """The ``tools`` sheet lists all tool names in order."""
        df = _sheets(_export(traj_multi_tools, tmp_path))["tools"]
        assert df["name"].tolist() == ["Tool_A", "Tool_B"]

    def test_wobjs_sheet_single_wobj(
        self, traj_basic: Trajectory, tmp_path: Path
    ) -> None:
        """The ``wobjs`` sheet lists the single wobj name correctly."""
        df = _sheets(_export(traj_basic, tmp_path))["wobjs"]
        assert df["name"].tolist() == ["wobj0"]

    def test_wobjs_sheet_multi_wobjs(
        self, traj_multi_tools: Trajectory, tmp_path: Path
    ) -> None:
        """The ``wobjs`` sheet lists all wobj names in order."""
        df = _sheets(_export(traj_multi_tools, tmp_path))["wobjs"]
        assert df["name"].tolist() == ["Wobj_A", "Wobj_B"]


# ---------------------------------------------------------------------------
# meta sheet content
# ---------------------------------------------------------------------------


class TestExcelExporterMetaSheet:
    """Tests verifying the content of the ``meta`` sheet."""

    def test_meta_has_key_value_columns(
        self, traj_with_meta: Trajectory, tmp_path: Path
    ) -> None:
        """The ``meta`` sheet contains ``key`` and ``value`` columns."""
        df = _sheets(_export(traj_with_meta, tmp_path))["meta"]
        assert "key" in df.columns
        assert "value" in df.columns

    def test_meta_name_present(
        self, traj_with_meta: Trajectory, tmp_path: Path
    ) -> None:
        """The trajectory name is present in the ``meta`` sheet."""
        df = _sheets(_export(traj_with_meta, tmp_path))["meta"]
        assert "name" in df["key"].values

    def test_meta_robot_model_value(
        self, traj_with_meta: Trajectory, tmp_path: Path
    ) -> None:
        """The ``robot_model`` value is correctly written to the ``meta`` sheet."""
        df = _sheets(_export(traj_with_meta, tmp_path))["meta"]
        row = df[df["key"] == "robot_model"]
        assert row["value"].iloc[0] == "IRB6700-205/2.80"

    def test_meta_extra_fields_present(
        self, traj_with_meta: Trajectory, tmp_path: Path
    ) -> None:
        """Extra metadata fields are present in the ``meta`` sheet."""
        df = _sheets(_export(traj_with_meta, tmp_path))["meta"]
        assert "author" in df["key"].values


# ---------------------------------------------------------------------------
# Export → import symmetry (roundtrip)
# ---------------------------------------------------------------------------


class TestExcelExporterRoundtrip:
    """Tests verifying the export → import roundtrip symmetry."""

    def test_roundtrip_point_count(
        self, traj_basic: Trajectory, tmp_path: Path
    ) -> None:
        """Reloading the exported workbook produces the same number of points."""
        path = _export(traj_basic, tmp_path)
        reloaded = ExcelConverter().convert(path)
        assert len(reloaded.points) == len(traj_basic.points)

    def test_roundtrip_xyz_values(self, traj_basic: Trajectory, tmp_path: Path) -> None:
        """x, y, z values are preserved after export → import."""
        path = _export(traj_basic, tmp_path)
        reloaded = ExcelConverter().convert(path)
        for col in ["x", "y", "z"]:
            pd.testing.assert_series_equal(
                reloaded.points[col].reset_index(drop=True),
                traj_basic.points[col].reset_index(drop=True),
                check_names=False,
                atol=1e-4,
            )

    def test_roundtrip_tools(
        self, traj_multi_tools: Trajectory, tmp_path: Path
    ) -> None:
        """The tool list is preserved after export → import."""
        path = _export(traj_multi_tools, tmp_path)
        reloaded = ExcelConverter().convert(path)
        assert reloaded.tools == traj_multi_tools.tools

    def test_roundtrip_wobjs(
        self, traj_multi_tools: Trajectory, tmp_path: Path
    ) -> None:
        """The wobj list is preserved after export → import."""
        path = _export(traj_multi_tools, tmp_path)
        reloaded = ExcelConverter().convert(path)
        assert reloaded.wobjs == traj_multi_tools.wobjs

    def test_roundtrip_meta_name(
        self, traj_with_meta: Trajectory, tmp_path: Path
    ) -> None:
        """The trajectory name is preserved after export → import."""
        path = _export(traj_with_meta, tmp_path)
        reloaded = ExcelConverter().convert(path)
        assert reloaded.meta.name == traj_with_meta.meta.name

    def test_roundtrip_robot_model(
        self, traj_with_meta: Trajectory, tmp_path: Path
    ) -> None:
        """The ``robot_model`` value is preserved after export → import."""
        path = _export(traj_with_meta, tmp_path)
        reloaded = ExcelConverter().convert(path)
        assert reloaded.meta.robot_model == traj_with_meta.meta.robot_model
