# tests/test_csv_converter.py

"""
Tests unitaires pour :mod:`trajcenter.converter.csv_converter`.

Couvre :
- :func:`~trajcenter.converter.csv_converter._detect_separator`
- :class:`~trajcenter.converter.csv_converter.CsvConverter`

La logique commune (resolve_columns, quaternion identité, autocomplétion,
tables tools/wobjs) est testée dans test_tabular_converter.py.
Ce fichier se concentre sur ce qui est spécifique au CSV :
détection du séparateur, encodage BOM, source_format, roundtrip.
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
    """Tests de la détection automatique du séparateur."""

    def test_comma_detected(self, csv_simple: Path) -> None:
        """La virgule est détectée sur un CSV standard."""
        assert _detect_separator(csv_simple) == ","

    def test_semicolon_detected(self, csv_semicolon: Path) -> None:
        """Le point-virgule est détecté sur un export Excel français."""
        assert _detect_separator(csv_semicolon) == ";"

    def test_missing_file_returns_default(self, tmp_path: Path) -> None:
        """Un fichier inexistant retourne la virgule par défaut."""
        assert _detect_separator(tmp_path / "inexistant.csv") == ","

    def test_empty_file_returns_default(self, tmp_path: Path) -> None:
        """Un fichier vide retourne la virgule par défaut."""
        p = tmp_path / "empty.csv"
        p.write_text("", encoding="utf-8")
        assert _detect_separator(p) == ","


# ---------------------------------------------------------------------------
# Tests — CsvConverter
# ---------------------------------------------------------------------------


class TestCsvConverter:
    """Tests du convertisseur CsvConverter."""

    # --- Erreurs de base ---

    def test_file_not_found_raises(self, tmp_path: Path) -> None:
        """convert() lève FileNotFoundError si le fichier n'existe pas."""
        with pytest.raises(FileNotFoundError, match="introuvable"):
            CsvConverter().convert(tmp_path / "inexistant.csv")

    def test_missing_xyz_raises(self, csv_missing_xyz: Path) -> None:
        """convert() lève ValueError si les colonnes XYZ sont absentes."""
        with pytest.raises(ValueError, match="obligatoires manquantes"):
            CsvConverter().convert(csv_missing_xyz)

    # --- Métadonnées ---

    def test_source_format(self, csv_simple: Path) -> None:
        """source_format est CSV."""
        assert CsvConverter().convert(csv_simple).meta.source_format == SourceFormat.CSV

    def test_source_file(self, csv_simple: Path) -> None:
        """source_file contient le nom du fichier."""
        assert CsvConverter().convert(csv_simple).meta.source_file == "simple.csv"

    def test_name(self, csv_simple: Path) -> None:
        """name est le stem du fichier."""
        assert CsvConverter().convert(csv_simple).meta.name == "simple"

    # --- Contenu nominal ---

    def test_point_count(self, csv_simple: Path) -> None:
        """Un CSV à 2 lignes produit 2 points."""
        assert CsvConverter().convert(csv_simple).point_count == 2

    def test_coordinates(self, csv_simple: Path) -> None:
        """Les coordonnées x, y, z sont correctement lues."""
        traj = CsvConverter().convert(csv_simple)
        assert traj.points["x"].iloc[0] == pytest.approx(100.0)
        assert traj.points["y"].iloc[0] == pytest.approx(200.0)
        assert traj.points["z"].iloc[0] == pytest.approx(300.0)

    def test_quaternions(self, csv_simple: Path) -> None:
        """Les quaternions sont correctement lus."""
        traj = CsvConverter().convert(csv_simple)
        assert traj.points["q1"].iloc[0] == pytest.approx(1.0)
        assert traj.points["q2"].iloc[0] == pytest.approx(0.0)

    def test_is_complete(self, csv_simple: Path) -> None:
        """La trajectoire produite est complète."""
        assert CsvConverter().convert(csv_simple).is_complete is True

    # --- Séparateur ---

    def test_semicolon_auto_detected(self, csv_semicolon: Path) -> None:
        """Le séparateur point-virgule est détecté automatiquement."""
        traj = CsvConverter().convert(csv_semicolon)
        assert traj.point_count == 2
        assert traj.points["x"].iloc[0] == pytest.approx(10.0)

    def test_semicolon_forced(self, csv_semicolon: Path) -> None:
        """Le séparateur forcé fonctionne correctement."""
        traj = CsvConverter(separator=";").convert(csv_semicolon)
        assert traj.point_count == 2

    def test_comma_forced(self, csv_simple: Path) -> None:
        """Le séparateur virgule forcé fonctionne correctement."""
        traj = CsvConverter(separator=",").convert(csv_simple)
        assert traj.point_count == 2

    # --- Encodage ---

    def test_bom_utf8_handled(self, csv_with_bom: Path) -> None:
        """Un fichier UTF-8 avec BOM est correctement lu (pas de colonne '\ufeffx')."""
        traj = CsvConverter().convert(csv_with_bom)
        assert "x" in traj.points.columns
        assert traj.points["x"].iloc[0] == pytest.approx(1.0)

    def test_custom_encoding(self, tmp_path: Path) -> None:
        """Un encodage Latin-1 forcé est correctement géré."""
        p = tmp_path / "latin1.csv"
        p.write_text("x,y,z\n1.0,2.0,3.0\n", encoding="latin-1")
        traj = CsvConverter(encoding="latin-1").convert(p)
        assert traj.point_count == 1

    # --- XYZ-only → quaternion identité ---

    def test_xyz_only_quaternion_identity(self, csv_xyz_only: Path) -> None:
        """Sans quaternions, l'orientation identité est appliquée."""
        traj = CsvConverter().convert(csv_xyz_only)
        assert traj.points["q1"].iloc[0] == pytest.approx(1.0)
        assert traj.points["q2"].iloc[0] == pytest.approx(0.0)
        assert traj.points["q3"].iloc[0] == pytest.approx(0.0)
        assert traj.points["q4"].iloc[0] == pytest.approx(0.0)

    def test_xyz_only_quaternion_autocompleted(self, csv_xyz_only: Path) -> None:
        """Les colonnes quaternion sont listées dans autocompleted."""
        traj = CsvConverter().convert(csv_xyz_only)
        for col in ("q1", "q2", "q3", "q4"):
            assert col in traj.meta.autocompleted

    # --- Alias colonnes ---

    def test_aliases_resolved(self, csv_aliases: Path) -> None:
        """Les alias de colonnes sont correctement résolus."""
        traj = CsvConverter().convert(csv_aliases)
        assert traj.points["x"].iloc[0] == pytest.approx(1.0)
        assert traj.points["speed"].iloc[0] == "v500"

    # --- Tools / wobjs ---

    def test_tool_wobj_columns_extracted(self, csv_with_tools: Path) -> None:
        """Les colonnes tool et wobj sont extraites et converties en index."""
        traj = CsvConverter().convert(csv_with_tools)
        assert "Tool_A" in traj.tools
        assert "Tool_B" in traj.tools
        assert "Wobj_A" in traj.wobjs
        assert "tool" not in traj.points.columns
        assert "tool_index" in traj.points.columns

    def test_tool_index_consistency(self, csv_with_tools: Path) -> None:
        """tool_index pointe cohéremment vers la bonne entrée de tools[]."""
        traj = CsvConverter().convert(csv_with_tools)
        for _, row in traj.points.iterrows():
            assert traj.tools[int(row["tool_index"])] in ("Tool_A", "Tool_B")

    # --- Lignes vides ---

    def test_empty_rows_dropped(self, csv_empty_rows: Path) -> None:
        """Les lignes entièrement vides sont supprimées."""
        assert CsvConverter().convert(csv_empty_rows).point_count == 2

    # --- Defaults personnalisés ---

    def test_custom_default_speed(self, csv_xyz_only: Path) -> None:
        """La vitesse par défaut personnalisée est appliquée."""
        traj = CsvConverter(defaults=ConversionDefaults(speed="v250")).convert(csv_xyz_only)
        assert traj.points["speed"].iloc[0] == "v250"

    def test_custom_default_move_type(self, csv_xyz_only: Path) -> None:
        """Le move_type par défaut personnalisé est appliqué."""
        traj = CsvConverter(defaults=ConversionDefaults(move_type="MoveL")).convert(csv_xyz_only)
        assert traj.points["move_type"].iloc[0] == "MoveL"

    # --- CSV complet ---

    def test_full_csv_move_types(self, csv_full: Path) -> None:
        """MoveL et MoveJ sont correctement lus depuis un CSV complet."""
        traj = CsvConverter().convert(csv_full)
        assert traj.points["move_type"].iloc[0] == "MoveL"
        assert traj.points["move_type"].iloc[1] == "MoveJ"

    def test_full_csv_speed_not_autocompleted(self, csv_full: Path) -> None:
        """speed présente dans la source n'est pas autocomplétée."""
        traj = CsvConverter().convert(csv_full)
        assert "speed" not in traj.meta.autocompleted
        assert traj.points["speed"].iloc[0] == "v500"

    # --- Roundtrip ---

    def test_full_roundtrip(self, tmp_path: Path, csv_simple: Path) -> None:
        """convert → save → load produit une trajectoire identique."""
        traj = CsvConverter().convert(csv_simple)
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

    def test_convert_and_save(self, tmp_path: Path, csv_simple: Path) -> None:
        """convert_and_save() crée bien le fichier .trajcenter."""
        result = CsvConverter().convert_and_save(source=csv_simple, dest_dir=tmp_path)
        assert result.exists()
        assert result.name == "simple.trajcenter"

    def test_convert_and_save_custom_stem(self, tmp_path: Path, csv_simple: Path) -> None:
        """convert_and_save() utilise le stem personnalisé."""
        result = CsvConverter().convert_and_save(
            source=csv_simple, dest_dir=tmp_path, stem="ma_trajectoire"
        )
        assert result.name == "ma_trajectoire.trajcenter"
