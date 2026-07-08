# tests/test_mod_converter.py

"""
Tests unitaires pour :mod:`trajcenter.converter.mod_converter`.

Couvre :
- :class:`~trajcenter.converter.mod_converter.ModConverter`
- :func:`~trajcenter.converter.mod_converter._index_to_list`
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from trajcenter.converter.defaults import ConversionDefaults
from trajcenter.converter.mod_converter import ModConverter, _index_to_list
from trajcenter.core.trajectory import SourceFormat, Trajectory


# ---------------------------------------------------------------------------
# Tests — ModConverter
# ---------------------------------------------------------------------------


class TestModConverter:
    """Tests du convertisseur ModConverter."""

    # --- Erreurs de base ---

    def test_file_not_found_raises(self, tmp_path: Path) -> None:
        """convert() lève FileNotFoundError si le fichier n'existe pas."""
        with pytest.raises(FileNotFoundError, match="Fichier introuvable"):
            ModConverter().convert(tmp_path / "inexistant.mod")

    def test_empty_mod_raises(self, mod_empty: Path) -> None:
        """convert() lève ValueError si aucune instruction Move n'est trouvée."""
        with pytest.raises(ValueError, match="Aucune instruction"):
            ModConverter().convert(mod_empty)

    # --- Métadonnées ---

    def test_source_format(self, mod_simple: Path) -> None:
        """source_format est RAPID."""
        assert ModConverter().convert(mod_simple).meta.source_format == SourceFormat.RAPID

    def test_source_file(self, mod_simple: Path) -> None:
        """source_file contient le nom du fichier."""
        assert ModConverter().convert(mod_simple).meta.source_file == "simple.mod"

    def test_name(self, mod_simple: Path) -> None:
        """name est le stem du fichier."""
        assert ModConverter().convert(mod_simple).meta.name == "simple"

    # --- Contenu ---

    def test_point_count(self, mod_simple: Path) -> None:
        """Un .mod avec 2 MoveL produit une trajectoire de 2 points."""
        assert ModConverter().convert(mod_simple).point_count == 2

    def test_is_complete(self, mod_simple: Path) -> None:
        """La trajectoire produite est complète."""
        assert ModConverter().convert(mod_simple).is_complete is True

    def test_coordinates(self, mod_simple: Path) -> None:
        """Les coordonnées x, y, z sont correctement parsées."""
        traj = ModConverter().convert(mod_simple)
        assert traj.points["x"].iloc[0] == pytest.approx(100.0)
        assert traj.points["y"].iloc[0] == pytest.approx(200.0)
        assert traj.points["z"].iloc[0] == pytest.approx(300.0)

    def test_quaternions(self, mod_simple: Path) -> None:
        """Les quaternions q1..q4 sont correctement parsés."""
        traj = ModConverter().convert(mod_simple)
        assert traj.points["q1"].iloc[0] == pytest.approx(1.0)
        assert traj.points["q2"].iloc[0] == pytest.approx(0.0)

    def test_zone(self, mod_simple: Path) -> None:
        """La zone est correctement parsée."""
        assert ModConverter().convert(mod_simple).points["zone"].iloc[0] == "z0"

    def test_move_type(self, mod_simple: Path) -> None:
        """Le type de mouvement MoveL est correctement parsé."""
        assert ModConverter().convert(mod_simple).points["move_type"].iloc[0] == "MoveL"

    # --- Tools / wobjs ---

    def test_tools_wobjs(self, mod_simple: Path) -> None:
        """Les tables tools et wobjs sont correctement construites."""
        traj = ModConverter().convert(mod_simple)
        assert traj.tools == ["Tool_formage"]
        assert traj.wobjs == ["Wobj_SerreFlan"]

    def test_tool_index(self, mod_simple: Path) -> None:
        """tool_index pointe vers le bon outil."""
        traj = ModConverter().convert(mod_simple)
        assert traj.points["tool_index"].iloc[0] == 0
        assert traj.tools[0] == "Tool_formage"

    def test_multiple_tools_deduplicated(self, mod_multiple_tools: Path) -> None:
        """Plusieurs tools sont correctement dédupliqués."""
        traj = ModConverter().convert(mod_multiple_tools)
        assert len(traj.tools) == 2
        assert "Tool_A" in traj.tools
        assert "Tool_B" in traj.tools

    def test_multiple_tools_index_consistency(self, mod_multiple_tools: Path) -> None:
        """tool_index pointe cohéremment vers la bonne entrée de tools[]."""
        traj = ModConverter().convert(mod_multiple_tools)
        for _, row in traj.points.iterrows():
            assert traj.tools[int(row["tool_index"])] in ("Tool_A", "Tool_B")

    # --- Vitesse ---

    def test_variable_speed_autocompleted(self, mod_simple: Path) -> None:
        """Une vitesse variable est autocomplétée avec la valeur default."""
        traj = ModConverter().convert(mod_simple)
        assert "speed" in traj.meta.autocompleted
        assert traj.points["speed"].iloc[0] == "v10"

    def test_variable_speed_custom_default(self, mod_simple: Path) -> None:
        """La vitesse autocomplétée utilise le default personnalisé."""
        traj = ModConverter(defaults=ConversionDefaults(speed="v200")).convert(mod_simple)
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

    # --- Axes externes ---

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

    # --- Parsing avancé ---

    def test_multiline_robtarget(self, mod_multiline: Path) -> None:
        """Un robtarget sur plusieurs lignes est correctement fusionné."""
        traj = ModConverter().convert(mod_multiline)
        assert traj.point_count == 1
        assert traj.points["x"].iloc[0] == pytest.approx(100.0)

    def test_confdata_parsed(self, mod_with_literal_speed: Path) -> None:
        """Les valeurs confdata sont correctement parsées."""
        traj = ModConverter().convert(mod_with_literal_speed)
        assert traj.points["cf1"].iloc[0] == 0
        assert traj.points["cf1"].iloc[1] == -1
        assert traj.points["cf6"].iloc[1] == 1

    # -----------------------------------------------------------------------
    # NOUVEAUX TESTS — couverture des branches manquantes
    # ----------------------------------------------------------test_confdata_invalid_raises-------------

    # --- Confdata malformé (lignes 286–287) ---

    def test_confdata_invalid_raises(self, tmp_path: Path) -> None:
        """Un confdata non parseable lève ValueError avec un message explicite."""
        mod = tmp_path / "bad_conf.mod"
        mod.write_text(
            "MODULE bad_conf\n"
            "  MoveL [[10.0,20.0,30.0],[1.0,0.0,0.0,0.0],"
            "[bad,x,?,0],[9E9,9E9,9E9,9E9,9E9,9E9]],"
            "v500,z0,Tool_A\\WObj:=Wobj_A;\n"
            "ENDMODULE\n",
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="Conversion numérique échouée"):
            ModConverter().convert(mod)

    # --- Zone : valeur "fine" et variantes (lignes 328, 334, 339) ---

    def test_zone_fine(self, tmp_path: Path) -> None:
        """La zone 'fine' est correctement parsée et stockée telle quelle."""
        mod = tmp_path / "zone_fine.mod"
        mod.write_text(
            "MODULE zone_fine\n"
            "  MoveL [[1.0,2.0,3.0],[1.0,0.0,0.0,0.0],"
            "[0,0,0,0],[9E9,9E9,9E9,9E9,9E9,9E9]],"
            "v100,fine,Tool_A\\WObj:=Wobj_A;\n"
            "ENDMODULE\n",
            encoding="utf-8",
        )
        traj = ModConverter().convert(mod)
        assert traj.points["zone"].iloc[0] == "fine"

    def test_zone_z_numeric(self, tmp_path: Path) -> None:
        """Une zone numérique z50 est correctement parsée."""
        mod = tmp_path / "zone_z50.mod"
        mod.write_text(
            "MODULE zone_z50\n"
            "  MoveL [[1.0,2.0,3.0],[1.0,0.0,0.0,0.0],"
            "[0,0,0,0],[9E9,9E9,9E9,9E9,9E9,9E9]],"
            "v100,z50,Tool_A\\WObj:=Wobj_A;\n"
            "ENDMODULE\n",
            encoding="utf-8",
        )
        traj = ModConverter().convert(mod)
        assert traj.points["zone"].iloc[0] == "z50"

    def test_zone_variable(self, tmp_path: Path) -> None:
        """Une zone non reconnue par _RE_PARAMS (ni 'fine' ni 'z*') lève ValueError."""
        mod = tmp_path / "zone_var.mod"
        mod.write_text(
            "MODULE zone_var\n"
            "  MoveL [[1.0,2.0,3.0],[1.0,0.0,0.0,0.0],"
            "[0,0,0,0],[9E9,9E9,9E9,9E9,9E9,9E9]],"
            "v100,myZoneVar,Tool_A\\WObj:=Wobj_A;\n"
            "ENDMODULE\n",
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="Paramètres Move"):
            ModConverter().convert(mod)

    def test_two_moves_same_physical_line(self, tmp_path: Path) -> None:
        """Deux instructions Move sur la même ligne physique sont toutes deux parsées."""
        mod = tmp_path / "same_line.mod"
        mod.write_text(
            "MODULE same_line\n"
            "  MoveL [[1.0,2.0,3.0],[1.0,0.0,0.0,0.0],[0,0,0,0],[9E9,9E9,9E9,9E9,9E9,9E9]],v100,z0,Tool_A\\WObj:=Wobj_A; MoveL [[4.0,5.0,6.0],[1.0,0.0,0.0,0.0],[0,0,0,0],[9E9,9E9,9E9,9E9,9E9,9E9]],v100,z0,Tool_A\\WObj:=Wobj_A;\n"
            "ENDMODULE\n",
            encoding="utf-8",
        )
        traj = ModConverter().convert(mod)
        assert traj.point_count == 2

    # --- Axes externes : valeurs flottantes et cas limites (lignes 349–366) ---

    def test_eax_multiple_active_axes(self, tmp_path: Path) -> None:
        """Plusieurs axes externes actifs sont tous stockés."""
        mod = tmp_path / "eax_multi.mod"
        mod.write_text(
            "MODULE eax_multi\n"
            "  MoveL [[1.0,2.0,3.0],[1.0,0.0,0.0,0.0],"
            "[0,0,0,0],[45.0,90.0,9E9,9E9,9E9,9E9]],"
            "v100,z0,Tool_A\\WObj:=Wobj_A;\n"
            "ENDMODULE\n",
            encoding="utf-8",
        )
        traj = ModConverter().convert(mod)
        assert "eax_a" in traj.points.columns
        assert "eax_b" in traj.points.columns
        assert traj.points["eax_a"].iloc[0] == pytest.approx(45.0)
        assert traj.points["eax_b"].iloc[0] == pytest.approx(90.0)
        assert "eax_c" not in traj.points.columns

    def test_eax_negative_value(self, tmp_path: Path) -> None:
        """Un axe externe avec valeur négative est correctement parsé."""
        mod = tmp_path / "eax_neg.mod"
        mod.write_text(
            "MODULE eax_neg\n"
            "  MoveL [[1.0,2.0,3.0],[1.0,0.0,0.0,0.0],"
            "[0,0,0,0],[-123.45,9E9,9E9,9E9,9E9,9E9]],"
            "v100,z0,Tool_A\\WObj:=Wobj_A;\n"
            "ENDMODULE\n",
            encoding="utf-8",
        )
        traj = ModConverter().convert(mod)
        assert traj.points["eax_a"].iloc[0] == pytest.approx(-123.45)

    def test_eax_zero_is_active(self, tmp_path: Path) -> None:
        """Un axe externe à 0.0 (≠ 9E9) est considéré actif et stocké."""
        mod = tmp_path / "eax_zero.mod"
        mod.write_text(
            "MODULE eax_zero\n"
            "  MoveL [[1.0,2.0,3.0],[1.0,0.0,0.0,0.0],"
            "[0,0,0,0],[0.0,9E9,9E9,9E9,9E9,9E9]],"
            "v100,z0,Tool_A\\WObj:=Wobj_A;\n"
            "ENDMODULE\n",
            encoding="utf-8",
        )
        traj = ModConverter().convert(mod)
        assert "eax_a" in traj.points.columns
        assert traj.points["eax_a"].iloc[0] == pytest.approx(0.0)

    def test_eax_all_inactive(self, tmp_path: Path) -> None:
        """Tous les axes à 9E9 → aucune colonne eax_* dans le DataFrame."""
        mod = tmp_path / "eax_all_inactive.mod"
        mod.write_text(
            "MODULE eax_all_inactive\n"
            "  MoveL [[1.0,2.0,3.0],[1.0,0.0,0.0,0.0],"
            "[0,0,0,0],[9E9,9E9,9E9,9E9,9E9,9E9]],"
            "v100,z0,Tool_A\\WObj:=Wobj_A;\n"
            "ENDMODULE\n",
            encoding="utf-8",
        )
        traj = ModConverter().convert(mod)
        for col in ["eax_a", "eax_b", "eax_c", "eax_d", "eax_e", "eax_f"]:
            assert col not in traj.points.columns

    # --- Boucle de continuation (ligne 249→251) ---

    def test_instruction_without_robtarget_raises(self, tmp_path: Path) -> None:
        """Une ligne Move avec target nommée (sans robtarget inline) lève ValueError."""
        mod = tmp_path / "named_target.mod"
        mod.write_text(
            "MODULE named_target\n"
            "  MoveL myNamedTarget, v100, z0, Tool_A\\WObj:=Wobj_A;\n"
            "ENDMODULE\n",
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="Robtarget introuvable"):
            ModConverter().convert(mod)

    # --- convert_and_save ---

    def test_convert_and_save(self, tmp_path: Path, mod_simple: Path) -> None:
        """convert_and_save() crée bien le fichier .trajcenter."""
        result = ModConverter().convert_and_save(source=mod_simple, dest_dir=tmp_path)
        assert result.exists()
        assert result.name == "simple.trajcenter"

    def test_convert_and_save_custom_stem(self, tmp_path: Path, mod_simple: Path) -> None:
        """convert_and_save() utilise le stem personnalisé."""
        result = ModConverter().convert_and_save(
            source=mod_simple, dest_dir=tmp_path, stem="ma_trajectoire"
        )
        assert result.name == "ma_trajectoire.trajcenter"

    # --- Roundtrip ---

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
# Tests — _index_to_list
# ---------------------------------------------------------------------------


class TestIndexToList:
    """Tests de la fonction utilitaire _index_to_list."""

    def test_single_entry(self) -> None:
        """Un seul élément est correctement converti."""
        assert _index_to_list({"Tool_formage": 0}) == ["Tool_formage"]

    def test_multiple_entries_ordered(self) -> None:
        """Les entrées sont ordonnées par index."""
        assert _index_to_list({"Tool_A": 0, "Tool_B": 1, "Tool_C": 2}) == [
            "Tool_A", "Tool_B", "Tool_C"
        ]

    def test_insertion_order_preserved(self) -> None:
        """L'ordre est respecté même si les index ne sont pas triés à l'insertion."""
        result = _index_to_list({"Tool_B": 1, "Tool_A": 0})
        assert result == ["Tool_A", "Tool_B"]

    def test_empty_dict(self) -> None:
        """Un dict vide produit une liste vide."""
        assert _index_to_list({}) == []
