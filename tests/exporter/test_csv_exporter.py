# tests/exporter/test_csv_exporter.py

"""
Tests d'intégration pour CsvExporter.

Vérifie les 4 fichiers produits et la symétrie import/export avec CsvConverter.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from trajcenter.core.trajectory import Trajectory
from trajcenter.converter.csv_converter import CsvConverter
from trajcenter.exporter.csv_exporter import CsvExporter
from trajcenter.exporter.options import ExportOptions


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _export(
    traj: Trajectory,
    dest: Path,
    options: ExportOptions | None = None,
) -> Path:
    return CsvExporter(options).export(traj, dest)


# ---------------------------------------------------------------------------
# Fichiers produits
# ---------------------------------------------------------------------------


class TestCsvExporterOutput:
    def test_main_csv_exists(self, traj_basic: Trajectory, tmp_path: Path) -> None:
        path = _export(traj_basic, tmp_path)
        assert path.exists()

    def test_main_csv_suffix(self, traj_basic: Trajectory, tmp_path: Path) -> None:
        path = _export(traj_basic, tmp_path)
        assert path.suffix == ".csv"

    def test_main_filename_matches_traj_name(
        self, traj_basic: Trajectory, tmp_path: Path
    ) -> None:
        path = _export(traj_basic, tmp_path)
        assert path.stem == traj_basic.meta.name

    def test_tools_csv_exists(self, traj_basic: Trajectory, tmp_path: Path) -> None:
        _export(traj_basic, tmp_path)
        assert (tmp_path / f"{traj_basic.meta.name}_tools.csv").exists()

    def test_wobjs_csv_exists(self, traj_basic: Trajectory, tmp_path: Path) -> None:
        _export(traj_basic, tmp_path)
        assert (tmp_path / f"{traj_basic.meta.name}_wobjs.csv").exists()

    def test_meta_csv_exists_by_default(self, traj_basic: Trajectory, tmp_path: Path) -> None:
        _export(traj_basic, tmp_path)
        assert (tmp_path / f"{traj_basic.meta.name}_meta.csv").exists()

    def test_meta_csv_absent_when_disabled(
        self, traj_basic: Trajectory, tmp_path: Path
    ) -> None:
        opts = ExportOptions(include_meta=False)
        _export(traj_basic, tmp_path, opts)
        assert not (tmp_path / f"{traj_basic.meta.name}_meta.csv").exists()

    def test_dest_dir_created_if_absent(self, traj_basic: Trajectory, tmp_path: Path) -> None:
        dest = tmp_path / "nested" / "output"
        path = _export(traj_basic, dest)
        assert path.exists()

    def test_returns_absolute_path(self, traj_basic: Trajectory, tmp_path: Path) -> None:
        path = _export(traj_basic, tmp_path)
        assert path.is_absolute()


# ---------------------------------------------------------------------------
# Contenu fichier principal
# ---------------------------------------------------------------------------


class TestCsvExporterMainFile:
    def test_row_count(self, traj_basic: Trajectory, tmp_path: Path) -> None:
        path = _export(traj_basic, tmp_path)
        df = pd.read_csv(path)
        assert len(df) == len(traj_basic.points)

    def test_xyz_columns_present(self, traj_basic: Trajectory, tmp_path: Path) -> None:
        path = _export(traj_basic, tmp_path)
        df = pd.read_csv(path)
        for col in ["x", "y", "z"]:
            assert col in df.columns

    def test_tool_column_resolved(self, traj_basic: Trajectory, tmp_path: Path) -> None:
        path = _export(traj_basic, tmp_path)
        df = pd.read_csv(path)
        assert "tool" in df.columns
        # StringDtype (pandas 2.x) ou object (pandas 1.x) — les deux sont des strings
        assert not pd.api.types.is_integer_dtype(df["tool"])
        assert df["tool"].iloc[0] == "tool0"

    def test_tool_index_not_present(self, traj_basic: Trajectory, tmp_path: Path) -> None:
        path = _export(traj_basic, tmp_path)
        df = pd.read_csv(path)
        assert "tool_index" not in df.columns

    def test_wobj_index_not_present(self, traj_basic: Trajectory, tmp_path: Path) -> None:
        path = _export(traj_basic, tmp_path)
        df = pd.read_csv(path)
        assert "wobj_index" not in df.columns

    def test_multi_tools_names_in_main(
        self, traj_multi_tools: Trajectory, tmp_path: Path
    ) -> None:
        path = _export(traj_multi_tools, tmp_path)
        df = pd.read_csv(path)
        assert set(df["tool"].unique()) == {"Tool_A", "Tool_B"}


# ---------------------------------------------------------------------------
# Encodage et séparateur
# ---------------------------------------------------------------------------


class TestCsvExporterEncoding:
    def test_default_encoding_utf8_sig(self, traj_basic: Trajectory, tmp_path: Path) -> None:
        """Le fichier par défaut est encodé utf-8-sig (BOM présent)."""
        path = _export(traj_basic, tmp_path)
        raw = path.read_bytes()
        assert raw[:3] == b"\xef\xbb\xbf", "BOM UTF-8 attendu"

    def test_custom_separator_semicolon(self, traj_basic: Trajectory, tmp_path: Path) -> None:
        opts = ExportOptions(csv_separator=";")
        path = _export(traj_basic, tmp_path, opts)
        df = pd.read_csv(path, sep=";", encoding="utf-8-sig")
        assert "x" in df.columns

    def test_custom_encoding_utf8(self, traj_basic: Trajectory, tmp_path: Path) -> None:
        opts = ExportOptions(csv_encoding="utf-8")
        path = _export(traj_basic, tmp_path, opts)
        raw = path.read_bytes()
        assert raw[:3] != b"\xef\xbb\xbf", "Pas de BOM attendu avec utf-8"


# ---------------------------------------------------------------------------
# Fichiers tools / wobjs
# ---------------------------------------------------------------------------


class TestCsvExporterToolsWobjsFiles:
    def test_tools_file_name_column(self, traj_basic: Trajectory, tmp_path: Path) -> None:
        _export(traj_basic, tmp_path)
        df = pd.read_csv(
            tmp_path / f"{traj_basic.meta.name}_tools.csv",
            encoding="utf-8-sig",
        )
        assert "name" in df.columns

    def test_tools_file_single_tool(self, traj_basic: Trajectory, tmp_path: Path) -> None:
        _export(traj_basic, tmp_path)
        df = pd.read_csv(
            tmp_path / f"{traj_basic.meta.name}_tools.csv",
            encoding="utf-8-sig",
        )
        assert df["name"].tolist() == ["tool0"]

    def test_tools_file_multi_tools(self, traj_multi_tools: Trajectory, tmp_path: Path) -> None:
        _export(traj_multi_tools, tmp_path)
        df = pd.read_csv(
            tmp_path / f"{traj_multi_tools.meta.name}_tools.csv",
            encoding="utf-8-sig",
        )
        assert df["name"].tolist() == ["Tool_A", "Tool_B"]

    def test_wobjs_file_single_wobj(self, traj_basic: Trajectory, tmp_path: Path) -> None:
        _export(traj_basic, tmp_path)
        df = pd.read_csv(
            tmp_path / f"{traj_basic.meta.name}_wobjs.csv",
            encoding="utf-8-sig",
        )
        assert df["name"].tolist() == ["wobj0"]


# ---------------------------------------------------------------------------
# Fichier meta
# ---------------------------------------------------------------------------


class TestCsvExporterMetaFile:
    def test_meta_has_key_value_columns(self, traj_with_meta: Trajectory, tmp_path: Path) -> None:
        _export(traj_with_meta, tmp_path)
        df = pd.read_csv(
            tmp_path / f"{traj_with_meta.meta.name}_meta.csv",
            encoding="utf-8-sig",
        )
        assert "key" in df.columns
        assert "value" in df.columns

    def test_meta_name_present(self, traj_with_meta: Trajectory, tmp_path: Path) -> None:
        _export(traj_with_meta, tmp_path)
        df = pd.read_csv(
            tmp_path / f"{traj_with_meta.meta.name}_meta.csv",
            encoding="utf-8-sig",
        )
        assert "name" in df["key"].values

    def test_meta_extra_author(self, traj_with_meta: Trajectory, tmp_path: Path) -> None:
        _export(traj_with_meta, tmp_path)
        df = pd.read_csv(
            tmp_path / f"{traj_with_meta.meta.name}_meta.csv",
            encoding="utf-8-sig",
        )
        row = df[df["key"] == "author"]
        assert row["value"].iloc[0] == "Jean Dupont"


# ---------------------------------------------------------------------------
# Symétrie export → import (roundtrip)
# ---------------------------------------------------------------------------


class TestCsvExporterRoundtrip:
    def test_roundtrip_point_count(self, traj_basic: Trajectory, tmp_path: Path) -> None:
        path = _export(traj_basic, tmp_path)
        reloaded = CsvConverter().convert(path)
        assert len(reloaded.points) == len(traj_basic.points)

    def test_roundtrip_xyz_values(self, traj_basic: Trajectory, tmp_path: Path) -> None:
        path = _export(traj_basic, tmp_path)
        reloaded = CsvConverter().convert(path)
        for col in ["x", "y", "z"]:
            pd.testing.assert_series_equal(
                reloaded.points[col].reset_index(drop=True),
                traj_basic.points[col].reset_index(drop=True),
                check_names=False,
                atol=1e-4,
            )

    def test_roundtrip_tool_names(self, traj_multi_tools: Trajectory, tmp_path: Path) -> None:
        """Après roundtrip, les noms de tools dans les points sont préservés."""
        path = _export(traj_multi_tools, tmp_path)
        reloaded = CsvConverter().convert(path)
        assert reloaded.tools == traj_multi_tools.tools

    def test_roundtrip_wobj_names(self, traj_multi_tools: Trajectory, tmp_path: Path) -> None:
        path = _export(traj_multi_tools, tmp_path)
        reloaded = CsvConverter().convert(path)
        assert reloaded.wobjs == traj_multi_tools.wobjs
