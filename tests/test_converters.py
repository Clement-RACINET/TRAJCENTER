# tests/test_converters.py

"""
Tests unitaires pour :mod:`trajcenter.converter`.

Couvre :
- :class:`~trajcenter.converter.defaults.ConversionDefaults`
- :class:`~trajcenter.converter.base.BaseConverter._autocomplete`
- :class:`~trajcenter.converter.mod_converter.ModConverter`
"""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pandas as pd
import pytest

from trajcenter.converter.base import BaseConverter
from trajcenter.converter.defaults import ConversionDefaults
from trajcenter.converter.mod_converter import ModConverter, _index_to_list
from trajcenter.core.trajectory import (
    CONVERTER_COLUMNS,
    REQUIRED_COLUMNS,
    SourceFormat,
    Trajectory,
)


# ---------------------------------------------------------------------------
# Fixtures — fichiers .mod synthétiques
# ---------------------------------------------------------------------------


@pytest.fixture
def mod_simple(tmp_path: Path) -> Path:
    """Fichier .mod minimal avec deux MoveL et une vitesse variable."""
    content = dedent("""\
        MODULE TestModule
            PROC TestProc()
                MoveL [[100.0,200.0,300.0],[1.0,0.0,0.0,0.0],[0,0,0,0],[9E9,9E9,9E9,9E9,9E9,9E9]],vitesse,z0,Tool_formage\\wobj:=Wobj_SerreFlan;
                MoveL [[150.0,250.0,350.0],[1.0,0.0,0.0,0.0],[0,0,0,0],[9E9,9E9,9E9,9E9,9E9,9E9]],vitesse,z0,Tool_formage\\wobj:=Wobj_SerreFlan;
            ENDPROC
        ENDMODULE
    """)
    p = tmp_path / "simple.mod"
    p.write_text(content, encoding="utf-8")
    return p


@pytest.fixture
def mod_with_literal_speed(tmp_path: Path) -> Path:
    """Fichier .mod avec vitesse littérale RAPID (v500)."""
    content = dedent("""\
        MODULE TestModule
            PROC TestProc()
                MoveL [[10.0,20.0,30.0],[1.0,0.0,0.0,0.0],[0,0,0,0],[9E9,9E9,9E9,9E9,9E9,9E9]],v500,z10,Tool_formage\\wobj:=Wobj_SerreFlan;
                MoveJ [[40.0,50.0,60.0],[1.0,0.0,0.0,0.0],[-1,0,1,0],[9E9,9E9,9E9,9E9,9E9,9E9]],v1000,fine,Tool_formage\\wobj:=Wobj_SerreFlan;
            ENDPROC
        ENDMODULE
    """)
    p = tmp_path / "literal_speed.mod"
    p.write_text(content, encoding="utf-8")
    return p


@pytest.fixture
def mod_with_eax(tmp_path: Path) -> Path:
    """Fichier .mod avec un axe externe actif (eax_a = 45.0)."""
    content = dedent("""\
        MODULE TestModule
            PROC TestProc()
                MoveL [[100.0,200.0,300.0],[1.0,0.0,0.0,0.0],[0,0,0,0],[45.0,9E9,9E9,9E9,9E9,9E9]],vitesse,z0,Tool_formage\\wobj:=Wobj_SerreFlan;
            ENDPROC
        ENDMODULE
    """)
    p = tmp_path / "eax.mod"
    p.write_text(content, encoding="utf-8")
    return p


@pytest.fixture
def mod_multiline(tmp_path: Path) -> Path:
    """Fichier .mod avec un robtarget formaté sur plusieurs lignes."""
    content = dedent("""\
        MODULE TestModule
            PROC TestProc()
                MoveL [[100.0,200.0,300.0],
                       [1.0,0.0,0.0,0.0],
                       [0,0,0,0],
                       [9E9,9E9,9E9,9E9,9E9,9E9]],vitesse,z0,Tool_formage\\wobj:=Wobj_SerreFlan;
            ENDPROC
        ENDMODULE
    """)
    p = tmp_path / "multiline.mod"
    p.write_text(content, encoding="utf-8")
    return p


@pytest.fixture
def mod_multiple_tools(tmp_path: Path) -> Path:
    """Fichier .mod avec deux tools et deux wobjs différents."""
    content = dedent("""\
        MODULE TestModule
            PROC TestProc()
                MoveL [[1.0,2.0,3.0],[1.0,0.0,0.0,0.0],[0,0,0,0],[9E9,9E9,9E9,9E9,9E9,9E9]],vitesse,z0,Tool_A\\wobj:=Wobj_A;
                MoveL [[4.0,5.0,6.0],[1.0,0.0,0.0,0.0],[0,0,0,0],[9E9,9E9,9E9,9E9,9E9,9E9]],vitesse,z0,Tool_B\\wobj:=Wobj_B;
                MoveL [[7.0,8.0,9.0],[1.0,0.0,0.0,0.0],[0,0,0,0],[9E9,9E9,9E9,9E9,9E9,9E9]],vitesse,z0,Tool_A\\wobj:=Wobj_A;
            ENDPROC
        ENDMODULE
    """)
    p = tmp_path / "multi_tools.mod"
    p.write_text(content, encoding="utf-8")
    return p


@pytest.fixture
def mod_empty(tmp_path: Path) -> Path:
    """Fichier .mod sans aucune instruction Move."""
    content = dedent("""\
        MODULE TestModule
            PROC TestProc()
                ! Aucune instruction Move ici
            ENDPROC
        ENDMODULE
    """)
    p = tmp_path / "empty.mod"
    p.write_text(content, encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# Tests — ConversionDefaults
# ---------------------------------------------------------------------------


class TestConversionDefaults:
    """Tests du modèle ConversionDefaults."""

    def test_default_values(self) -> None:
        """Les valeurs par défaut standard sont correctes."""
        d = ConversionDefaults()
        assert d.move_type == "MoveL"
        assert d.speed == "v500"
        assert d.zone == "z10"
        assert d.tool == "tool0"
        assert d.wobj == "wobj0"
        assert d.cf_value == 0

    def test_custom_values(self) -> None:
        """Les valeurs peuvent être surchargées."""
        d = ConversionDefaults(speed="v200", zone="fine", move_type="MoveJ")
        assert d.speed == "v200"
        assert d.zone == "fine"
        assert d.move_type == "MoveJ"


# ---------------------------------------------------------------------------
# Tests — BaseConverter._autocomplete (via ModConverter)
# ---------------------------------------------------------------------------


class TestAutocomplete:
    """Tests de la méthode _autocomplete de BaseConverter."""

    def _make_converter(self) -> ModConverter:
        return ModConverter(defaults=ConversionDefaults())

    def test_all_converter_columns_present_after_autocomplete(self) -> None:
        """Toutes les CONVERTER_COLUMNS sont présentes après autocomplétion."""
        conv = self._make_converter()
        df = pd.DataFrame({
            "x": [1.0], "y": [2.0], "z": [3.0],
            "q1": [1.0], "q2": [0.0], "q3": [0.0], "q4": [0.0],
        })
        tools: list[str] = []
        wobjs: list[str] = []
        df_out, autocompleted = conv._autocomplete(df, tools, wobjs)

        for col in CONVERTER_COLUMNS:
            assert col in df_out.columns, f"Colonne manquante : {col}"

    def test_autocompleted_lists_missing_columns(self) -> None:
        """autocompleted contient exactement les colonnes ajoutées."""
        conv = self._make_converter()
        df = pd.DataFrame({
            "x": [1.0], "y": [2.0], "z": [3.0],
            "q1": [1.0], "q2": [0.0], "q3": [0.0], "q4": [0.0],
            "move_type": ["MoveL"],  # déjà présente
        })
        tools: list[str] = ["Tool_formage"]
        wobjs: list[str] = ["Wobj_SerreFlan"]
        _, autocompleted = conv._autocomplete(df, tools, wobjs)

        assert "move_type" not in autocompleted
        assert "speed" in autocompleted
        assert "zone" in autocompleted

    def test_empty_tools_filled_with_default(self) -> None:
        """Une liste tools vide est complétée avec defaults.tool."""
        conv = self._make_converter()
        df = pd.DataFrame({
            "x": [1.0], "y": [2.0], "z": [3.0],
            "q1": [1.0], "q2": [0.0], "q3": [0.0], "q4": [0.0],
        })
        tools: list[str] = []
        wobjs: list[str] = []
        conv._autocomplete(df, tools, wobjs)
        assert tools == ["tool0"]
        assert wobjs == ["wobj0"]

    def test_existing_columns_not_overwritten(self) -> None:
        """Les colonnes déjà présentes ne sont pas écrasées."""
        conv = self._make_converter()
        df = pd.DataFrame({
            "x": [1.0], "y": [2.0], "z": [3.0],
            "q1": [1.0], "q2": [0.0], "q3": [0.0], "q4": [0.0],
            "speed": ["v9999"],  # valeur custom à préserver
        })
        tools: list[str] = ["Tool_formage"]
        wobjs: list[str] = ["Wobj_SerreFlan"]
        df_out, _ = conv._autocomplete(df, tools, wobjs)
        assert df_out["speed"].iloc[0] == "v9999"

    def test_confdata_autocompleted_as_int8_nullable(self) -> None:
        """Les colonnes confdata autocomplétées sont en Int8 nullable."""
        conv = self._make_converter()
        df = pd.DataFrame({
            "x": [1.0], "y": [2.0], "z": [3.0],
            "q1": [1.0], "q2": [0.0], "q3": [0.0], "q4": [0.0],
        })
        tools: list[str] = []
        wobjs: list[str] = []
        df_out, _ = conv._autocomplete(df, tools, wobjs)
        for col in ["cf1", "cf4", "cf6", "cfx"]:
            assert df_out[col].dtype == pd.Int8Dtype()


# ---------------------------------------------------------------------------
# Tests — ModConverter
# ---------------------------------------------------------------------------


class TestModConverter:
    """Tests du convertisseur ModConverter."""

    def test_file_not_found_raises(self, tmp_path: Path) -> None:
        """convert() lève FileNotFoundError si le fichier n'existe pas."""
        with pytest.raises(FileNotFoundError, match="Fichier introuvable"):
            ModConverter().convert(tmp_path / "inexistant.mod")

    def test_empty_mod_raises(self, mod_empty: Path) -> None:
        """convert() lève ValueError si aucune instruction Move n'est trouvée."""
        with pytest.raises(ValueError, match="Aucune instruction"):
            ModConverter().convert(mod_empty)

    def test_simple_mod_point_count(self, mod_simple: Path) -> None:
        """Un .mod avec 2 MoveL produit une trajectoire de 2 points."""
        traj = ModConverter().convert(mod_simple)
        assert traj.point_count == 2

    def test_simple_mod_source_format(self, mod_simple: Path) -> None:
        """source_format est RAPID."""
        traj = ModConverter().convert(mod_simple)
        assert traj.meta.source_format == SourceFormat.RAPID

    def test_simple_mod_source_file(self, mod_simple: Path) -> None:
        """source_file contient le nom du fichier."""
        traj = ModConverter().convert(mod_simple)
        assert traj.meta.source_file == "simple.mod"

    def test_simple_mod_name(self, mod_simple: Path) -> None:
        """name est le stem du fichier."""
        traj = ModConverter().convert(mod_simple)
        assert traj.meta.name == "simple"

    def test_simple_mod_is_complete(self, mod_simple: Path) -> None:
        """La trajectoire produite est complète (is_complete = True)."""
        traj = ModConverter().convert(mod_simple)
        assert traj.is_complete is True

    def test_simple_mod_coordinates(self, mod_simple: Path) -> None:
        """Les coordonnées x,y,z sont correctement parsées."""
        traj = ModConverter().convert(mod_simple)
        assert traj.points["x"].iloc[0] == pytest.approx(100.0)
        assert traj.points["y"].iloc[0] == pytest.approx(200.0)
        assert traj.points["z"].iloc[0] == pytest.approx(300.0)

    def test_simple_mod_quaternions(self, mod_simple: Path) -> None:
        """Les quaternions q1..q4 sont correctement parsés."""
        traj = ModConverter().convert(mod_simple)
        assert traj.points["q1"].iloc[0] == pytest.approx(1.0)
        assert traj.points["q2"].iloc[0] == pytest.approx(0.0)

    def test_simple_mod_tools_wobjs(self, mod_simple: Path) -> None:
        """Les tables tools et wobjs sont correctement construites."""
        traj = ModConverter().convert(mod_simple)
        assert traj.tools == ["Tool_formage"]
        assert traj.wobjs == ["Wobj_SerreFlan"]

    def test_simple_mod_tool_index(self, mod_simple: Path) -> None:
        """tool_index pointe vers le bon outil."""
        traj = ModConverter().convert(mod_simple)
        assert traj.points["tool_index"].iloc[0] == 0
        assert traj.tools[0] == "Tool_formage"

    def test_simple_mod_zone(self, mod_simple: Path) -> None:
        """La zone est correctement parsée."""
        traj = ModConverter().convert(mod_simple)
        assert traj.points["zone"].iloc[0] == "z0"

    def test_simple_mod_move_type(self, mod_simple: Path) -> None:
        """Le type de mouvement est correctement parsé."""
        traj = ModConverter().convert(mod_simple)
        assert traj.points["move_type"].iloc[0] == "MoveL"

    def test_variable_speed_autocompleted(self, mod_simple: Path) -> None:
        """Une vitesse variable (non littérale) est autocomplétée."""
        traj = ModConverter().convert(mod_simple)
        assert "speed" in traj.meta.autocompleted
        assert traj.points["speed"].iloc[0] == "v500"  # valeur default

    def test_variable_speed_custom_default(self, mod_simple: Path) -> None:
        """La vitesse autocomplétée utilise le default personnalisé."""
        traj = ModConverter(
            defaults=ConversionDefaults(speed="v200")
        ).convert(mod_simple)
        assert traj.points["speed"].iloc[0] == "v200"

    def test_literal_speed_not_autocompleted(self, mod_with_literal_speed: Path) -> None:
        """Une vitesse littérale RAPID n'est pas autocomplétée."""
        traj = ModConverter().convert(mod_with_literal_speed)
        assert "speed" not in traj.meta.autocompleted
        assert traj.points["speed"].iloc[0] == "v500"
        assert traj.points["speed"].iloc[1] == "v1000"

    def test_mixed_move_types(self, mod_with_literal_speed: Path) -> None:
        """MoveL et MoveJ sont correctement distingués."""
        traj = ModConverter().convert(mod_with_literal_speed)
        assert traj.points["move_type"].iloc[0] == "MoveL"
        assert traj.points["move_type"].iloc[1] == "MoveJ"

    def test_eax_active_stored(self, mod_with_eax: Path) -> None:
        """Un axe externe actif (≠ 9E9) est stocké dans le DataFrame."""
        traj = ModConverter().convert(mod_with_eax)
        assert "eax_a" in traj.points.columns
        assert traj.points["eax_a"].iloc[0] == pytest.approx(45.0)

    def test_eax_inactive_not_stored(self, mod_with_eax: Path) -> None:
        """Les axes externes inactifs (9E9) ne sont pas stockés."""
        traj = ModConverter().convert(mod_with_eax)
        for col in ["eax_b", "eax_c", "eax_d", "eax_e", "eax_f"]:
            assert col not in traj.points.columns

    def test_multiline_robtarget(self, mod_multiline: Path) -> None:
        """Un robtarget sur plusieurs lignes est correctement fusionné."""
        traj = ModConverter().convert(mod_multiline)
        assert traj.point_count == 1
        assert traj.points["x"].iloc[0] == pytest.approx(100.0)

    def test_multiple_tools_indexed(self, mod_multiple_tools: Path) -> None:
        """Plusieurs tools sont correctement dédupliqués et indexés."""
        traj = ModConverter().convert(mod_multiple_tools)
        assert len(traj.tools) == 2
        assert "Tool_A" in traj.tools
        assert "Tool_B" in traj.tools

    def test_multiple_tools_index_consistency(self, mod_multiple_tools: Path) -> None:
        """tool_index pointe cohéremment vers la bonne entrée de tools[]."""
        traj = ModConverter().convert(mod_multiple_tools)
        for _, row in traj.points.iterrows():
            idx = int(row["tool_index"])
            assert traj.tools[idx] in ("Tool_A", "Tool_B")

    def test_confdata_parsed(self, mod_with_literal_speed: Path) -> None:
        """Les valeurs confdata sont correctement parsées."""
        traj = ModConverter().convert(mod_with_literal_speed)
        # Point 1 : [0,0,0,0]
        assert traj.points["cf1"].iloc[0] == 0
        # Point 2 : [-1,0,1,0]
        assert traj.points["cf1"].iloc[1] == -1
        assert traj.points["cf6"].iloc[1] == 1

    def test_convert_and_save(self, tmp_path: Path, mod_simple: Path) -> None:
        """convert_and_save() crée bien le fichier .trajcenter."""
        result = ModConverter().convert_and_save(
            source=mod_simple,
            dest_dir=tmp_path,
        )
        assert result.exists()
        assert result.name == "simple.trajcenter"

    def test_convert_and_save_custom_stem(
        self, tmp_path: Path, mod_simple: Path
    ) -> None:
        """convert_and_save() utilise le stem personnalisé."""
        result = ModConverter().convert_and_save(
            source=mod_simple,
            dest_dir=tmp_path,
            stem="ma_trajectoire",
        )
        assert result.name == "ma_trajectoire.trajcenter"

    def test_full_roundtrip(self, tmp_path: Path, mod_simple: Path) -> None:
        """convert → save → load produit une trajectoire identique."""
        traj = ModConverter().convert(mod_simple)
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


# ---------------------------------------------------------------------------
# Tests — utilitaire _index_to_list
# ---------------------------------------------------------------------------


class TestIndexToList:
    """Tests de la fonction utilitaire _index_to_list."""

    def test_single_entry(self) -> None:
        """Un seul élément est correctement converti."""
        assert _index_to_list({"Tool_formage": 0}) == ["Tool_formage"]

    def test_multiple_entries_ordered(self) -> None:
        """Les entrées sont ordonnées par index."""
        result = _index_to_list({"Tool_A": 0, "Tool_B": 1, "Tool_C": 2})
        assert result == ["Tool_A", "Tool_B", "Tool_C"]

    def test_insertion_order_preserved(self) -> None:
        """L'ordre d'insertion est respecté même si les index ne sont pas triés."""
        result = _index_to_list({"Tool_B": 1, "Tool_A": 0})
        assert result[0] == "Tool_A"
        assert result[1] == "Tool_B"

    def test_empty_dict(self) -> None:
        """Un dict vide produit une liste vide."""
        assert _index_to_list({}) == []
