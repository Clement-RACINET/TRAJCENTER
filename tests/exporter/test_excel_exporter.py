# tests/exporter/test_excel_exporter.py

"""
Tests d'intégration pour ExcelExporter.

Vérifie la structure du fichier .xlsx produit et la symétrie import/export
avec ExcelConverter.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from trajcenter.core.trajectory import Trajectory
from trajcenter.converter.excel_converter import ExcelConverter
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
    return ExcelExporter(options).export(traj, dest)


def _sheets(path: Path) -> dict[str, pd.DataFrame]:
    """Charge toutes les feuilles d'un classeur Excel."""
    return pd.read_excel(path, sheet_name=None, engine="openpyxl")


# ---------------------------------------------------------------------------
# Fichier produit
# ---------------------------------------------------------------------------


class TestExcelExporterOutput:
    def test_produces_xlsx_file(self, traj_basic: Trajectory, tmp_path: Path) -> None:
        path = _export(traj_basic, tmp_path)
        assert path.exists()
        assert path.suffix == ".xlsx"

    def test_filename_matches_traj_name(self, traj_basic: Trajectory, tmp_path: Path) -> None:
        path = _export(traj_basic, tmp_path)
        assert path.stem == traj_basic.meta.name

    def test_dest_dir_created_if_absent(self, traj_basic: Trajectory, tmp_path: Path) -> None:
        dest = tmp_path / "nested" / "output"
        path = _export(traj_basic, dest)
        assert path.exists()

    def test_returns_absolute_path(self, traj_basic: Trajectory, tmp_path: Path) -> None:
        path = _export(traj_basic, tmp_path)
        assert path.is_absolute()


# ---------------------------------------------------------------------------
# Feuilles présentes
# ---------------------------------------------------------------------------


class TestExcelExporterSheets:
    def test_traj_sheet_present(self, traj_basic: Trajectory, tmp_path: Path) -> None:
        sheets = _sheets(_export(traj_basic, tmp_path))
        assert "traj" in sheets

    def test_tools_sheet_present(self, traj_basic: Trajectory, tmp_path: Path) -> None:
        sheets = _sheets(_export(traj_basic, tmp_path))
        assert "tools" in sheets

    def test_wobjs_sheet_present(self, traj_basic: Trajectory, tmp_path: Path) -> None:
        sheets = _sheets(_export(traj_basic, tmp_path))
        assert "wobjs" in sheets

    def test_meta_sheet_present_by_default(self, traj_basic: Trajectory, tmp_path: Path) -> None:
        sheets = _sheets(_export(traj_basic, tmp_path))
        assert "meta" in sheets

    def test_meta_sheet_absent_when_disabled(
        self, traj_basic: Trajectory, tmp_path: Path
    ) -> None:
        opts = ExportOptions(include_meta=False)
        sheets = _sheets(_export(traj_basic, tmp_path, opts))
        assert "meta" not in sheets


# ---------------------------------------------------------------------------
# Contenu feuille traj
# ---------------------------------------------------------------------------


class TestExcelExporterTrajSheet:
    def test_row_count(self, traj_basic: Trajectory, tmp_path: Path) -> None:
        df = _sheets(_export(traj_basic, tmp_path))["traj"]
        assert len(df) == len(traj_basic.points)

    def test_xyz_columns_present(self, traj_basic: Trajectory, tmp_path: Path) -> None:
        df = _sheets(_export(traj_basic, tmp_path))["traj"]
        for col in ["x", "y", "z"]:
            assert col in df.columns

    def test_tool_column_resolved(self, traj_basic: Trajectory, tmp_path: Path) -> None:
        """La colonne 'tool' contient des noms, pas des indices."""
        df = _sheets(_export(traj_basic, tmp_path))["traj"]
        assert "tool" in df.columns
        # StringDtype (pandas 2.x) ou object (pandas 1.x) — les deux sont des strings
        assert not pd.api.types.is_integer_dtype(df["tool"])
        assert df["tool"].iloc[0] == "tool0"

    def test_wobj_column_resolved(self, traj_basic: Trajectory, tmp_path: Path) -> None:
        df = _sheets(_export(traj_basic, tmp_path))["traj"]
        assert "wobj" in df.columns

    def test_tool_index_not_in_traj_sheet(self, traj_basic: Trajectory, tmp_path: Path) -> None:
        df = _sheets(_export(traj_basic, tmp_path))["traj"]
        assert "tool_index" not in df.columns

    def test_wobj_index_not_in_traj_sheet(self, traj_basic: Trajectory, tmp_path: Path) -> None:
        df = _sheets(_export(traj_basic, tmp_path))["traj"]
        assert "wobj_index" not in df.columns

    def test_multi_tools_names_in_traj(
        self, traj_multi_tools: Trajectory, tmp_path: Path
    ) -> None:
        df = _sheets(_export(traj_multi_tools, tmp_path))["traj"]
        assert set(df["tool"].unique()) == {"Tool_A", "Tool_B"}


# ---------------------------------------------------------------------------
# Contenu feuilles tools / wobjs
# ---------------------------------------------------------------------------


class TestExcelExporterToolsWobjsSheets:
    def test_tools_sheet_name_column(self, traj_basic: Trajectory, tmp_path: Path) -> None:
        df = _sheets(_export(traj_basic, tmp_path))["tools"]
        assert "name" in df.columns

    def test_tools_sheet_single_tool(self, traj_basic: Trajectory, tmp_path: Path) -> None:
        df = _sheets(_export(traj_basic, tmp_path))["tools"]
        assert df["name"].tolist() == ["tool0"]

    def test_tools_sheet_multi_tools(self, traj_multi_tools: Trajectory, tmp_path: Path) -> None:
        df = _sheets(_export(traj_multi_tools, tmp_path))["tools"]
        assert df["name"].tolist() == ["Tool_A", "Tool_B"]

    def test_wobjs_sheet_single_wobj(self, traj_basic: Trajectory, tmp_path: Path) -> None:
        df = _sheets(_export(traj_basic, tmp_path))["wobjs"]
        assert df["name"].tolist() == ["wobj0"]

    def test_wobjs_sheet_multi_wobjs(self, traj_multi_tools: Trajectory, tmp_path: Path) -> None:
        df = _sheets(_export(traj_multi_tools, tmp_path))["wobjs"]
        assert df["name"].tolist() == ["Wobj_A", "Wobj_B"]


# ---------------------------------------------------------------------------
# Contenu feuille meta
# ---------------------------------------------------------------------------


class TestExcelExporterMetaSheet:
    def test_meta_has_key_value_columns(self, traj_with_meta: Trajectory, tmp_path: Path) -> None:
        df = _sheets(_export(traj_with_meta, tmp_path))["meta"]
        assert "key" in df.columns
        assert "value" in df.columns

    def test_meta_name_present(self, traj_with_meta: Trajectory, tmp_path: Path) -> None:
        df = _sheets(_export(traj_with_meta, tmp_path))["meta"]
        assert "name" in df["key"].values

    def test_meta_robot_model_value(self, traj_with_meta: Trajectory, tmp_path: Path) -> None:
        df = _sheets(_export(traj_with_meta, tmp_path))["meta"]
        row = df[df["key"] == "robot_model"]
        assert row["value"].iloc[0] == "IRB6700-205/2.80"

    def test_meta_extra_fields_present(self, traj_with_meta: Trajectory, tmp_path: Path) -> None:
        df = _sheets(_export(traj_with_meta, tmp_path))["meta"]
        assert "author" in df["key"].values


# ---------------------------------------------------------------------------
# Symétrie export → import (roundtrip)
# ---------------------------------------------------------------------------


class TestExcelExporterRoundtrip:
    def test_roundtrip_point_count(self, traj_basic: Trajectory, tmp_path: Path) -> None:
        """Export puis re-import : le nombre de points est identique."""
        path = _export(traj_basic, tmp_path)
        reloaded = ExcelConverter().convert(path)
        assert len(reloaded.points) == len(traj_basic.points)

    def test_roundtrip_xyz_values(self, traj_basic: Trajectory, tmp_path: Path) -> None:
        """Export puis re-import : les coordonnées XYZ sont identiques."""
        path = _export(traj_basic, tmp_path)
        reloaded = ExcelConverter().convert(path)
        for col in ["x", "y", "z"]:
            pd.testing.assert_series_equal(
                reloaded.points[col].reset_index(drop=True),
                traj_basic.points[col].reset_index(drop=True),
                check_names=False,
                atol=1e-4,
            )

    def test_roundtrip_tools(self, traj_multi_tools: Trajectory, tmp_path: Path) -> None:
        """Export puis re-import : la liste des tools est identique."""
        path = _export(traj_multi_tools, tmp_path)
        reloaded = ExcelConverter().convert(path)
        assert reloaded.tools == traj_multi_tools.tools

    def test_roundtrip_wobjs(self, traj_multi_tools: Trajectory, tmp_path: Path) -> None:
        path = _export(traj_multi_tools, tmp_path)
        reloaded = ExcelConverter().convert(path)
        assert reloaded.wobjs == traj_multi_tools.wobjs

    def test_roundtrip_meta_name(self, traj_with_meta: Trajectory, tmp_path: Path) -> None:
        path = _export(traj_with_meta, tmp_path)
        reloaded = ExcelConverter().convert(path)
        assert reloaded.meta.name == traj_with_meta.meta.name

    def test_roundtrip_robot_model(self, traj_with_meta: Trajectory, tmp_path: Path) -> None:
        path = _export(traj_with_meta, tmp_path)
        reloaded = ExcelConverter().convert(path)
        assert reloaded.meta.robot_model == traj_with_meta.meta.robot_model
