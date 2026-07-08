# tests/test_tabular_converter.py

"""
Tests unitaires pour :mod:`trajcenter.converter.column_mapper`
et la logique commune de :mod:`trajcenter.converter.tabular_converter`.

Couvre :
- :func:`~trajcenter.converter.column_mapper.canonical_name`
- :func:`~trajcenter.converter.column_mapper.resolve_columns`
- Logique partagée de :class:`~trajcenter.converter.tabular_converter._TabularConverter`
  (résolution colonnes, tables tools/wobjs, quaternion identité, autocomplétion)
  testée via :class:`~trajcenter.converter.csv_converter.CsvConverter`
  comme proxy concret minimal.
"""

from __future__ import annotations

import warnings
from pathlib import Path

import pandas as pd
import pytest

from trajcenter.converter.column_mapper import COLUMN_ALIASES, canonical_name, resolve_columns
from trajcenter.converter.csv_converter import CsvConverter
from trajcenter.converter.defaults import ConversionDefaults
from trajcenter.core.trajectory import SourceFormat


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_csv(tmp_path: Path, name: str, content: str, encoding: str = "utf-8") -> Path:
    p = tmp_path / name
    p.write_text(content, encoding=encoding)
    return p


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
# Tests — logique commune _TabularConverter (via CsvConverter)
# ---------------------------------------------------------------------------


class TestTabularConverterLogic:
    """Tests de la logique commune via CsvConverter comme proxy concret."""

    # --- Erreurs de base ---

    def test_file_not_found_raises(self, tmp_path: Path) -> None:
        """convert() lève FileNotFoundError si le fichier n'existe pas."""
        with pytest.raises(FileNotFoundError, match="introuvable"):
            CsvConverter().convert(tmp_path / "inexistant.csv")

    def test_missing_xyz_raises(self, tmp_path: Path) -> None:
        """convert() lève ValueError si les colonnes XYZ sont absentes."""
        csv = _write_csv(tmp_path, "bad.csv", "q1,q2,q3,q4\n1,0,0,0\n")
        with pytest.raises(ValueError, match="obligatoires manquantes"):
            CsvConverter().convert(csv)

    # --- Quaternion identité ---

    def test_xyz_only_quaternion_identity(self, tmp_path: Path) -> None:
        """Sans quaternions, l'orientation identité est appliquée."""
        csv = _write_csv(tmp_path, "xyz.csv", "x,y,z\n1.0,2.0,3.0\n")
        traj = CsvConverter().convert(csv)
        assert traj.points["q1"].iloc[0] == pytest.approx(1.0)
        assert traj.points["q2"].iloc[0] == pytest.approx(0.0)
        assert traj.points["q3"].iloc[0] == pytest.approx(0.0)
        assert traj.points["q4"].iloc[0] == pytest.approx(0.0)

    def test_xyz_only_quaternion_autocompleted(self, tmp_path: Path) -> None:
        """Les colonnes quaternion sont listées dans autocompleted."""
        csv = _write_csv(tmp_path, "xyz.csv", "x,y,z\n1.0,2.0,3.0\n")
        traj = CsvConverter().convert(csv)
        for col in ("q1", "q2", "q3", "q4"):
            assert col in traj.meta.autocompleted

    # --- Autocomplétion ---

    def test_speed_autocompleted(self, tmp_path: Path) -> None:
        """speed est autocomplétée si absente."""
        csv = _write_csv(tmp_path, "xyz.csv", "x,y,z\n1.0,2.0,3.0\n")
        traj = CsvConverter().convert(csv)
        assert "speed" in traj.meta.autocompleted

    def test_custom_default_speed(self, tmp_path: Path) -> None:
        """La vitesse par défaut personnalisée est appliquée."""
        csv = _write_csv(tmp_path, "xyz.csv", "x,y,z\n1.0,2.0,3.0\n")
        traj = CsvConverter(defaults=ConversionDefaults(speed="v250")).convert(csv)
        assert traj.points["speed"].iloc[0] == "v250"

    def test_move_type_not_autocompleted_when_present(self, tmp_path: Path) -> None:
        """move_type présent dans la source n'est pas autocomplété."""
        csv = _write_csv(
            tmp_path, "full.csv",
            "x,y,z,move_type\n1.0,2.0,3.0,MoveL\n"
        )
        traj = CsvConverter().convert(csv)
        assert "move_type" not in traj.meta.autocompleted
        assert traj.points["move_type"].iloc[0] == "MoveL"

    # --- Alias colonnes ---

    def test_alias_columns_resolved(self, tmp_path: Path) -> None:
        """Les alias de colonnes sont correctement résolus."""
        csv = _write_csv(
            tmp_path, "alias.csv",
            "PosX,PosY,PosZ,VITESSE\n1.0,2.0,3.0,v500\n"
        )
        traj = CsvConverter().convert(csv)
        assert traj.points["x"].iloc[0] == pytest.approx(1.0)
        assert traj.points["speed"].iloc[0] == "v500"

    def test_unknown_columns_warned(self, tmp_path: Path) -> None:
        """Les colonnes inconnues émettent un UserWarning."""
        csv = _write_csv(
            tmp_path, "unknown.csv",
            "x,y,z,colonne_inconnue\n1.0,2.0,3.0,foo\n"
        )
        with pytest.warns(UserWarning, match="non reconnues"):
            CsvConverter().convert(csv)

    # --- Tables tools / wobjs ---

    def test_tool_column_extracted(self, tmp_path: Path) -> None:
        """La colonne tool est extraite et convertie en tool_index."""
        csv = _write_csv(
            tmp_path, "tools.csv",
            "x,y,z,tool\n1.0,2.0,3.0,Tool_A\n4.0,5.0,6.0,Tool_B\n"
        )
        traj = CsvConverter().convert(csv)
        assert "Tool_A" in traj.tools
        assert "Tool_B" in traj.tools
        assert "tool" not in traj.points.columns
        assert "tool_index" in traj.points.columns

    def test_wobj_column_extracted(self, tmp_path: Path) -> None:
        """La colonne wobj est extraite et convertie en wobj_index."""
        csv = _write_csv(
            tmp_path, "wobj.csv",
            "x,y,z,wobj\n1.0,2.0,3.0,Wobj_A\n"
        )
        traj = CsvConverter().convert(csv)
        assert "Wobj_A" in traj.wobjs

    # --- Feuilles de meta ---

    def test_no_meta_overrides_name_is_stem(self, tmp_path: Path) -> None:
        """Sans feuille meta, le nom est le stem du fichier source."""
        csv = _write_csv(tmp_path, "ma_traj.csv", "x,y,z\n1.0,2.0,3.0\n")
        traj = CsvConverter().convert(csv)
        assert traj.meta.name == "ma_traj"

    def test_no_meta_overrides_robot_model_is_none(self, tmp_path: Path) -> None:
        """Sans feuille meta, robot_model est None."""
        csv = _write_csv(tmp_path, "xyz.csv", "x,y,z\n1.0,2.0,3.0\n")
        assert CsvConverter().convert(csv).meta.robot_model is None

    def test_no_meta_overrides_extra_is_empty(self, tmp_path: Path) -> None:
        """Sans feuille meta, extra{} est vide."""
        csv = _write_csv(tmp_path, "xyz.csv", "x,y,z\n1.0,2.0,3.0\n")
        assert CsvConverter().convert(csv).meta.extra == {}

    # --- Lignes vides ---

    def test_empty_rows_dropped(self, tmp_path: Path) -> None:
        """Les lignes entièrement vides sont supprimées."""
        csv = _write_csv(
            tmp_path, "empty_rows.csv",
            "x,y,z\n1.0,2.0,3.0\n,,\n4.0,5.0,6.0\n"
        )
        traj = CsvConverter().convert(csv)
        assert traj.point_count == 2

    # --- is_complete ---

    def test_is_complete(self, tmp_path: Path) -> None:
        """La trajectoire produite est toujours complète."""
        csv = _write_csv(tmp_path, "xyz.csv", "x,y,z\n1.0,2.0,3.0\n")
        assert CsvConverter().convert(csv).is_complete is True
