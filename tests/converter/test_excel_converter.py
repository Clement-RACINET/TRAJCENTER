# tests/test_excel_converter.py

"""
Tests unitaires spécifiques à :mod:`trajcenter.converter.excel_converter`.

Couvre uniquement ce qui est propre à Excel :
- Lecture multi-feuilles
- Feuilles tools / wobjs / meta
- Gestion des lignes vides
- Alias de colonnes Excel
- Roundtrip save/load

La logique commune (canonical_name, resolve_columns, quaternion identité,
autocomplétion) est testée dans test_tabular_converter.py.
"""

from __future__ import annotations

import warnings
from pathlib import Path

import pandas as pd
import pytest

from trajcenter.converter.defaults import ConversionDefaults
from trajcenter.converter.excel_converter import ExcelConverter
from trajcenter.core.trajectory import SourceFormat, Trajectory


class TestExcelConverter:
    """Tests spécifiques au convertisseur ExcelConverter."""

    # --- Erreurs de base ---

    def test_file_not_found_raises(self, tmp_path: Path) -> None:
        """convert() lève FileNotFoundError si le fichier n'existe pas."""
        with pytest.raises(FileNotFoundError, match="introuvable"):
            ExcelConverter().convert(tmp_path / "inexistant.xlsx")

    def test_missing_xyz_raises(self, xlsx_missing_xyz: Path) -> None:
        """convert() lève ValueError si les colonnes XYZ sont absentes."""
        with pytest.raises(ValueError, match="obligatoires manquantes"):
            ExcelConverter().convert(xlsx_missing_xyz)

    def test_multi_traj_convert_raises(self, xlsx_multi_traj: Path) -> None:
        """convert() lève ValueError si plusieurs feuilles trajectoire existent."""
        with pytest.raises(ValueError, match="convert_all"):
            ExcelConverter().convert(xlsx_multi_traj)

    # --- Cas nominal ---

    def test_point_count(self, xlsx_simple: Path) -> None:
        assert ExcelConverter().convert(xlsx_simple).point_count == 2

    def test_source_format(self, xlsx_simple: Path) -> None:
        assert ExcelConverter().convert(xlsx_simple).meta.source_format == SourceFormat.EXCEL

    def test_source_file(self, xlsx_simple: Path) -> None:
        assert ExcelConverter().convert(xlsx_simple).meta.source_file == "simple.xlsx"

    def test_name(self, xlsx_simple: Path) -> None:
        """name est le stem du fichier pour une feuille par défaut."""
        assert ExcelConverter().convert(xlsx_simple).meta.name == "simple"

    def test_coordinates(self, xlsx_simple: Path) -> None:
        traj = ExcelConverter().convert(xlsx_simple)
        assert traj.points["x"].iloc[0] == pytest.approx(100.0)
        assert traj.points["y"].iloc[0] == pytest.approx(200.0)
        assert traj.points["z"].iloc[0] == pytest.approx(300.0)

    def test_quaternions(self, xlsx_simple: Path) -> None:
        traj = ExcelConverter().convert(xlsx_simple)
        assert traj.points["q1"].iloc[0] == pytest.approx(1.0)
        assert traj.points["q2"].iloc[0] == pytest.approx(0.0)

    def test_is_complete(self, xlsx_simple: Path) -> None:
        assert ExcelConverter().convert(xlsx_simple).is_complete is True

    # --- XYZ-only → quaternion identité ---

    def test_xyz_only_quaternion_identity(self, xlsx_xyz_only: Path) -> None:
        traj = ExcelConverter().convert(xlsx_xyz_only)
        assert traj.points["q1"].iloc[0] == pytest.approx(1.0)
        assert traj.points["q2"].iloc[0] == pytest.approx(0.0)

    def test_xyz_only_quaternion_autocompleted(self, xlsx_xyz_only: Path) -> None:
        traj = ExcelConverter().convert(xlsx_xyz_only)
        for col in ("q1", "q2", "q3", "q4"):
            assert col in traj.meta.autocompleted

    # --- Alias et accents ---

    def test_aliases_resolved(self, xlsx_aliases: Path) -> None:
        traj = ExcelConverter().convert(xlsx_aliases)
        assert traj.points["x"].iloc[0] == pytest.approx(1.0)
        assert traj.points["speed"].iloc[0] == "v500"

    def test_aliases_no_spurious_warning(self, xlsx_aliases: Path) -> None:
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            ExcelConverter().convert(xlsx_aliases)
        unknown_warnings = [x for x in w if "non reconnues" in str(x.message)]
        assert len(unknown_warnings) == 0

    # --- Multi-feuilles ---

    def test_multi_traj_count(self, xlsx_multi_traj: Path) -> None:
        assert len(ExcelConverter().convert_all(xlsx_multi_traj)) == 2

    def test_multi_traj_names(self, xlsx_multi_traj: Path) -> None:
        names = {t.meta.name for t in ExcelConverter().convert_all(xlsx_multi_traj)}
        assert "multi_traj_traj_A" in names
        assert "multi_traj_traj_B" in names

    def test_multi_traj_point_counts(self, xlsx_multi_traj: Path) -> None:
        counts = {
            t.meta.name: t.point_count
            for t in ExcelConverter().convert_all(xlsx_multi_traj)
        }
        assert counts["multi_traj_traj_A"] == 1
        assert counts["multi_traj_traj_B"] == 2

    # --- Feuilles tools / wobjs ---

    def test_tools_sheet_loaded(self, xlsx_with_tools_sheet: Path) -> None:
        traj = ExcelConverter().convert(xlsx_with_tools_sheet)
        assert "Tool_A" in traj.tools
        assert "Tool_B" in traj.tools

    def test_wobjs_sheet_loaded(self, xlsx_with_tools_sheet: Path) -> None:
        assert "Wobj_A" in ExcelConverter().convert(xlsx_with_tools_sheet).wobjs

    def test_tool_index_consistency(self, xlsx_with_tools_sheet: Path) -> None:
        traj = ExcelConverter().convert(xlsx_with_tools_sheet)
        for _, row in traj.points.iterrows():
            assert traj.tools[int(row["tool_index"])] in ("Tool_A", "Tool_B")

    # --- Feuille meta ---

    def test_meta_sheet_not_a_traj_sheet(self, xlsx_with_meta_sheet: Path) -> None:
        """La feuille meta n'est pas traitée comme une feuille trajectoire."""
        assert ExcelConverter().convert(xlsx_with_meta_sheet).point_count == 1

    def test_meta_sheet_name_override(self, xlsx_with_full_meta: Path) -> None:
        """La feuille meta surcharge le nom de la trajectoire."""
        traj = ExcelConverter().convert(xlsx_with_full_meta)
        assert traj.meta.name == "Trajectoire_Soudure"

    def test_meta_sheet_robot_model(self, xlsx_with_full_meta: Path) -> None:
        """La feuille meta alimente robot_model."""
        traj = ExcelConverter().convert(xlsx_with_full_meta)
        assert traj.meta.robot_model == "IRB6700-205/2.80"

    def test_meta_sheet_extra_fields(self, xlsx_with_full_meta: Path) -> None:
        """Les champs inconnus de la feuille meta vont dans extra{}."""
        traj = ExcelConverter().convert(xlsx_with_full_meta)
        assert traj.meta.extra.get("author") == "Jean Dupont"


    # --- Lignes vides ---

    def test_empty_rows_dropped(self, xlsx_empty_rows: Path) -> None:
        assert ExcelConverter().convert(xlsx_empty_rows).point_count == 2

    # --- Defaults personnalisés ---

    def test_custom_default_move_type(self, xlsx_xyz_only: Path) -> None:
        traj = ExcelConverter(
            defaults=ConversionDefaults(move_type="MoveL")
        ).convert(xlsx_xyz_only)
        assert traj.points["move_type"].iloc[0] == "MoveL"

    def test_custom_default_speed(self, xlsx_xyz_only: Path) -> None:
        traj = ExcelConverter(
            defaults=ConversionDefaults(speed="v250")
        ).convert(xlsx_xyz_only)
        assert traj.points["speed"].iloc[0] == "v250"

    # --- Roundtrip ---

    def test_full_roundtrip(self, tmp_path: Path, xlsx_simple: Path) -> None:
        traj = ExcelConverter().convert(xlsx_simple)
        dest = tmp_path / "simple.trajcenter"
        traj.save(dest)
        loaded = Trajectory.load(dest)
        assert loaded.point_count == traj.point_count
        assert loaded.tools == traj.tools
        assert loaded.wobjs == traj.wobjs
        assert loaded.is_complete is True
        pd.testing.assert_series_equal(
            loaded.points["x"].reset_index(drop=True),
            traj.points["x"].reset_index(drop=True),
            check_names=False,
        )

    def test_convert_and_save(self, tmp_path: Path, xlsx_simple: Path) -> None:
        result = ExcelConverter().convert_and_save(
            source=xlsx_simple, dest_dir=tmp_path
        )
        assert result.exists()
        assert result.name == "simple.trajcenter"
