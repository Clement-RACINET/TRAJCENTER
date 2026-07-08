# tests/test_excel_converter.py

"""
Tests unitaires pour :mod:`trajcenter.converter.column_mapper`
et :mod:`trajcenter.converter.excel_converter`.

Couvre :
- :func:`~trajcenter.converter.column_mapper.canonical_name`
- :func:`~trajcenter.converter.column_mapper.resolve_columns`
- :class:`~trajcenter.converter.excel_converter.ExcelConverter`
"""

from __future__ import annotations

import warnings
from pathlib import Path

import pandas as pd
import pytest

from trajcenter.converter.column_mapper import COLUMN_ALIASES, canonical_name, resolve_columns
from trajcenter.converter.defaults import ConversionDefaults
from trajcenter.converter.excel_converter import ExcelConverter
from trajcenter.core.trajectory import SourceFormat, Trajectory


# ---------------------------------------------------------------------------
# Tests — canonical_name
# ---------------------------------------------------------------------------


class TestCanonicalName:
    """Tests de la fonction canonical_name."""

    def test_exact_lowercase(self) -> None:
        """Un alias exact minuscule est reconnu."""
        assert canonical_name("x") == "x"
        assert canonical_name("vitesse") == "speed"
        assert canonical_name("repere") == "wobj"

    def test_uppercase(self) -> None:
        """Les majuscules sont ignorées."""
        assert canonical_name("X") == "x"
        assert canonical_name("VITESSE") == "speed"
        assert canonical_name("PosX") == "x"

    def test_accents(self) -> None:
        """Les accents sont supprimés avant comparaison."""
        assert canonical_name("Répère") == "wobj"
        assert canonical_name("REPÈRE") == "wobj"

    def test_unknown_returns_none(self) -> None:
        """Un nom inconnu retourne None."""
        assert canonical_name("foobar") is None
        assert canonical_name("colonne_inconnue") is None

    def test_all_canonical_names_resolve_to_themselves(self) -> None:
        """Chaque nom canonique se résout vers lui-même."""
        for canon in COLUMN_ALIASES:
            assert canonical_name(canon) == canon

    def test_quaternion_aliases(self) -> None:
        """Les alias de quaternions sont correctement résolus."""
        assert canonical_name("qw") == "q1"
        assert canonical_name("qi") == "q2"
        assert canonical_name("qj") == "q3"
        assert canonical_name("qk") == "q4"


# ---------------------------------------------------------------------------
# Tests — resolve_columns
# ---------------------------------------------------------------------------


class TestResolveColumns:
    """Tests de la fonction resolve_columns."""

    def test_canonical_columns_unchanged(self) -> None:
        """Des colonnes déjà canoniques ne sont pas modifiées."""
        df = pd.DataFrame(columns=["x", "y", "z"])
        df_out, unknown = resolve_columns(df)
        assert list(df_out.columns) == ["x", "y", "z"]
        assert unknown == []

    def test_alias_resolved(self) -> None:
        """Les alias sont correctement renommés."""
        df = pd.DataFrame(columns=["PosX", "PosY", "PosZ"])
        df_out, unknown = resolve_columns(df)
        assert "x" in df_out.columns
        assert "y" in df_out.columns
        assert "z" in df_out.columns

    def test_unknown_columns_returned(self) -> None:
        """Les colonnes inconnues sont retournées dans la liste et laissées intactes."""
        df = pd.DataFrame(columns=["x", "y", "z", "custom_col"])
        df_out, unknown = resolve_columns(df)
        assert "custom_col" in unknown
        assert "custom_col" in df_out.columns

    def test_duplicate_canonical_warns(self) -> None:
        """Un doublon de canonique émet un UserWarning et conserve la première colonne."""
        df = pd.DataFrame(columns=["x", "pos_x", "y", "z"])
        with pytest.warns(UserWarning, match="pos_x"):
            df_out, _ = resolve_columns(df)
        assert df_out.columns.tolist().count("x") == 1

    def test_accent_and_case_resolved(self) -> None:
        """Accents et casse mixte sont résolus correctement."""
        df = pd.DataFrame(columns=["Répère", "VITESSE", "PosX", "PosY", "PosZ"])
        df_out, unknown = resolve_columns(df)
        assert "wobj" in df_out.columns
        assert "speed" in df_out.columns
        assert unknown == []


# ---------------------------------------------------------------------------
# Tests — ExcelConverter
# ---------------------------------------------------------------------------


class TestExcelConverter:
    """Tests du convertisseur ExcelConverter."""

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
        """Un classeur simple produit le bon nombre de points."""
        assert ExcelConverter().convert(xlsx_simple).point_count == 2

    def test_source_format(self, xlsx_simple: Path) -> None:
        """source_format est EXCEL."""
        assert ExcelConverter().convert(xlsx_simple).meta.source_format == SourceFormat.EXCEL

    def test_source_file(self, xlsx_simple: Path) -> None:
        """source_file contient le nom du fichier."""
        assert ExcelConverter().convert(xlsx_simple).meta.source_file == "simple.xlsx"

    def test_name(self, xlsx_simple: Path) -> None:
        """name est le stem du fichier pour une feuille par défaut."""
        assert ExcelConverter().convert(xlsx_simple).meta.name == "simple"

    def test_coordinates(self, xlsx_simple: Path) -> None:
        """Les coordonnées x, y, z sont correctement lues."""
        traj = ExcelConverter().convert(xlsx_simple)
        assert traj.points["x"].iloc[0] == pytest.approx(100.0)
        assert traj.points["y"].iloc[0] == pytest.approx(200.0)
        assert traj.points["z"].iloc[0] == pytest.approx(300.0)

    def test_quaternions(self, xlsx_simple: Path) -> None:
        """Les quaternions sont correctement lus."""
        traj = ExcelConverter().convert(xlsx_simple)
        assert traj.points["q1"].iloc[0] == pytest.approx(1.0)
        assert traj.points["q2"].iloc[0] == pytest.approx(0.0)

    def test_is_complete(self, xlsx_simple: Path) -> None:
        """La trajectoire produite est complète."""
        assert ExcelConverter().convert(xlsx_simple).is_complete is True

    # --- XYZ-only → quaternion identité ---

    def test_xyz_only_quaternion_identity(self, xlsx_xyz_only: Path) -> None:
        """Sans quaternions, l'orientation identité est appliquée."""
        traj = ExcelConverter().convert(xlsx_xyz_only)
        assert traj.points["q1"].iloc[0] == pytest.approx(1.0)
        assert traj.points["q2"].iloc[0] == pytest.approx(0.0)
        assert traj.points["q3"].iloc[0] == pytest.approx(0.0)
        assert traj.points["q4"].iloc[0] == pytest.approx(0.0)

    def test_xyz_only_quaternion_autocompleted(self, xlsx_xyz_only: Path) -> None:
        """Les colonnes quaternion sont listées dans autocompleted."""
        traj = ExcelConverter().convert(xlsx_xyz_only)
        for col in ("q1", "q2", "q3", "q4"):
            assert col in traj.meta.autocompleted

    # --- Alias et accents ---

    def test_aliases_resolved(self, xlsx_aliases: Path) -> None:
        """Les alias de colonnes (casse, accents) sont correctement résolus."""
        traj = ExcelConverter().convert(xlsx_aliases)
        assert traj.points["x"].iloc[0] == pytest.approx(1.0)
        assert traj.points["speed"].iloc[0] == "v500"

    def test_aliases_no_spurious_warning(self, xlsx_aliases: Path) -> None:
        """Les colonnes reconnues via alias n'émettent pas de warning 'non reconnues'."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            ExcelConverter().convert(xlsx_aliases)
        unknown_warnings = [x for x in w if "non reconnues" in str(x.message)]
        assert len(unknown_warnings) == 0

    # --- Multi-feuilles ---

    def test_multi_traj_count(self, xlsx_multi_traj: Path) -> None:
        """convert_all() retourne autant de trajectoires que de feuilles traj."""
        assert len(ExcelConverter().convert_all(xlsx_multi_traj)) == 2

    def test_multi_traj_names(self, xlsx_multi_traj: Path) -> None:
        """Les noms incluent le nom de feuille quand il est non-défaut."""
        names = {t.meta.name for t in ExcelConverter().convert_all(xlsx_multi_traj)}
        assert "multi_traj_traj_A" in names
        assert "multi_traj_traj_B" in names

    def test_multi_traj_point_counts(self, xlsx_multi_traj: Path) -> None:
        """Chaque trajectoire a le bon nombre de points."""
        counts = {
            t.meta.name: t.point_count
            for t in ExcelConverter().convert_all(xlsx_multi_traj)
        }
        assert counts["multi_traj_traj_A"] == 1
        assert counts["multi_traj_traj_B"] == 2

    # --- Feuilles tools / wobjs ---

    def test_tools_sheet_loaded(self, xlsx_with_tools_sheet: Path) -> None:
        """La feuille tools est chargée et utilisée."""
        traj = ExcelConverter().convert(xlsx_with_tools_sheet)
        assert "Tool_A" in traj.tools
        assert "Tool_B" in traj.tools

    def test_wobjs_sheet_loaded(self, xlsx_with_tools_sheet: Path) -> None:
        """La feuille wobjs est chargée et utilisée."""
        assert "Wobj_A" in ExcelConverter().convert(xlsx_with_tools_sheet).wobjs

    def test_tool_index_consistency(self, xlsx_with_tools_sheet: Path) -> None:
        """tool_index pointe vers le bon outil."""
        traj = ExcelConverter().convert(xlsx_with_tools_sheet)
        for _, row in traj.points.iterrows():
            assert traj.tools[int(row["tool_index"])] in ("Tool_A", "Tool_B")

    # --- Feuille meta ignorée ---

    def test_meta_sheet_ignored(self, xlsx_with_meta_sheet: Path) -> None:
        """La feuille meta est ignorée silencieusement."""
        assert ExcelConverter().convert(xlsx_with_meta_sheet).point_count == 1

    # --- Lignes vides ---

    def test_empty_rows_dropped(self, xlsx_empty_rows: Path) -> None:
        """Les lignes entièrement vides sont supprimées."""
        assert ExcelConverter().convert(xlsx_empty_rows).point_count == 2

    # --- Defaults personnalisés ---

    def test_custom_default_move_type(self, xlsx_xyz_only: Path) -> None:
        """Le move_type par défaut personnalisé est appliqué."""
        traj = ExcelConverter(
            defaults=ConversionDefaults(move_type="MoveL")
        ).convert(xlsx_xyz_only)
        assert traj.points["move_type"].iloc[0] == "MoveL"

    def test_custom_default_speed(self, xlsx_xyz_only: Path) -> None:
        """La vitesse par défaut personnalisée est appliquée."""
        traj = ExcelConverter(
            defaults=ConversionDefaults(speed="v250")
        ).convert(xlsx_xyz_only)
        assert traj.points["speed"].iloc[0] == "v250"

    # --- Roundtrip ---

    def test_full_roundtrip(self, tmp_path: Path, xlsx_simple: Path) -> None:
        """convert → save → load produit une trajectoire identique."""
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
