#!/usr/bin/env python3
# tests/test_mod_converter.py
"""Unit tests for :mod:`trajcenter.converter.mod_converter`.

Author: Clement RACINET

Covers:

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
    """Tests for the ModConverter class."""

    # --- Basic errors ---

    def test_file_not_found_raises(self, tmp_path: Path) -> None:
        """``convert()`` raises ``FileNotFoundError`` when the file does not exist."""
        with pytest.raises(FileNotFoundError, match="Fichier introuvable"):
            ModConverter().convert(tmp_path / "inexistant.mod")

    def test_empty_mod_raises(self, mod_empty: Path) -> None:
        """``convert()`` raises ``ValueError`` when no Move instruction is found."""
        with pytest.raises(ValueError, match="Aucune instruction"):
            ModConverter().convert(mod_empty)

    # --- Metadata ---

    def test_source_format(self, mod_simple: Path) -> None:
        """``source_format`` is ``RAPID``."""
        assert (
            ModConverter().convert(mod_simple).meta.source_format == SourceFormat.RAPID
        )

    def test_source_file(self, mod_simple: Path) -> None:
        """``source_file`` contains the file name."""
        assert ModConverter().convert(mod_simple).meta.source_file == "simple.mod"

    def test_name(self, mod_simple: Path) -> None:
        """``name`` is the file stem."""
        assert ModConverter().convert(mod_simple).meta.name == "simple"

    # --- Content ---

    def test_point_count(self, mod_simple: Path) -> None:
        """A .mod file with 2 MoveL instructions produces a 2-point trajectory."""
        assert ModConverter().convert(mod_simple).point_count == 2

    def test_is_complete(self, mod_simple: Path) -> None:
        """The produced trajectory is complete."""
        assert ModConverter().convert(mod_simple).is_complete is True

    def test_coordinates(self, mod_simple: Path) -> None:
        """x, y, z coordinates are correctly parsed."""
        traj = ModConverter().convert(mod_simple)
        assert traj.points["x"].iloc[0] == pytest.approx(100.0)
        assert traj.points["y"].iloc[0] == pytest.approx(200.0)
        assert traj.points["z"].iloc[0] == pytest.approx(300.0)

    def test_quaternions(self, mod_simple: Path) -> None:
        """Quaternion values q1..q4 are correctly parsed."""
        traj = ModConverter().convert(mod_simple)
        assert traj.points["q1"].iloc[0] == pytest.approx(1.0)
        assert traj.points["q2"].iloc[0] == pytest.approx(0.0)

    def test_zone(self, mod_simple: Path) -> None:
        """The zone value is correctly parsed."""
        assert ModConverter().convert(mod_simple).points["zone"].iloc[0] == "z0"

    def test_move_type(self, mod_simple: Path) -> None:
        """The MoveL move type is correctly parsed."""
        assert ModConverter().convert(mod_simple).points["move_type"].iloc[0] == "MoveL"

    # --- Tools / wobjs ---

    def test_tools_wobjs(self, mod_simple: Path) -> None:
        """The tools and wobjs tables are correctly built."""
        traj = ModConverter().convert(mod_simple)
        assert traj.tools == ["Tool_formage"]
        assert traj.wobjs == ["Wobj_SerreFlan"]

    def test_tool_index(self, mod_simple: Path) -> None:
        """``tool_index`` points to the correct tool."""
        traj = ModConverter().convert(mod_simple)
        assert traj.points["tool_index"].iloc[0] == 0
        assert traj.tools[0] == "Tool_formage"

    def test_multiple_tools_deduplicated(self, mod_multiple_tools: Path) -> None:
        """Multiple tools are correctly deduplicated."""
        traj = ModConverter().convert(mod_multiple_tools)
        assert len(traj.tools) == 2
        assert "Tool_A" in traj.tools
        assert "Tool_B" in traj.tools

    def test_multiple_tools_index_consistency(self, mod_multiple_tools: Path) -> None:
        """``tool_index`` consistently points to the correct entry in ``tools[]``."""
        traj = ModConverter().convert(mod_multiple_tools)
        for _, row in traj.points.iterrows():
            assert traj.tools[int(row["tool_index"])] in ("Tool_A", "Tool_B")

    # --- Speed ---

    def test_variable_speed_autocompleted(self, mod_simple: Path) -> None:
        """A variable speed is autocompleted with the default value."""
        traj = ModConverter().convert(mod_simple)
        assert "speed" in traj.meta.autocompleted
        assert traj.points["speed"].iloc[0] == "v10"

    def test_variable_speed_custom_default(self, mod_simple: Path) -> None:
        """The autocompleted speed uses the custom default value."""
        traj = ModConverter(defaults=ConversionDefaults(speed="v200")).convert(
            mod_simple
        )
        assert traj.points["speed"].iloc[0] == "v200"

    def test_literal_speed_not_autocompleted(
        self, mod_with_literal_speed: Path
    ) -> None:
        """A literal RAPID speed is not listed in ``autocompleted``."""
        traj = ModConverter().convert(mod_with_literal_speed)
        assert "speed" not in traj.meta.autocompleted
        assert traj.points["speed"].iloc[0] == "v500"
        assert traj.points["speed"].iloc[1] == "v1000"

    def test_mixed_move_types(self, mod_with_literal_speed: Path) -> None:
        """MoveL and MoveJ are correctly distinguished."""
        traj = ModConverter().convert(mod_with_literal_speed)
        assert traj.points["move_type"].iloc[0] == "MoveL"
        assert traj.points["move_type"].iloc[1] == "MoveJ"

    # --- External axes ---

    def test_eax_active_stored(self, mod_with_eax: Path) -> None:
        """An active external axis (≠ 9E9) is stored in the DataFrame."""
        traj = ModConverter().convert(mod_with_eax)
        assert "eax_a" in traj.points.columns
        assert traj.points["eax_a"].iloc[0] == pytest.approx(45.0)

    def test_eax_inactive_not_stored(self, mod_with_eax: Path) -> None:
        """Inactive external axes (9E9) are not stored in the DataFrame."""
        traj = ModConverter().convert(mod_with_eax)
        for col in ["eax_b", "eax_c", "eax_d", "eax_e", "eax_f"]:
            assert col not in traj.points.columns

    # --- Advanced parsing ---

    def test_multiline_robtarget(self, mod_multiline: Path) -> None:
        """A robtarget spread across multiple lines is correctly merged."""
        traj = ModConverter().convert(mod_multiline)
        assert traj.point_count == 1
        assert traj.points["x"].iloc[0] == pytest.approx(100.0)

    def test_confdata_parsed(self, mod_with_literal_speed: Path) -> None:
        """Confdata values are correctly parsed."""
        traj = ModConverter().convert(mod_with_literal_speed)
        assert traj.points["cf1"].iloc[0] == 0
        assert traj.points["cf1"].iloc[1] == -1
        assert traj.points["cf6"].iloc[1] == 1

    # --- Additional branch coverage ---

    # --- Malformed confdata ---

    def test_confdata_invalid_raises(self, tmp_path: Path) -> None:
        """An unparseable confdata raises ``ValueError`` with an explicit message."""
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

    # --- Zone variants ---

    def test_zone_fine(self, tmp_path: Path) -> None:
        """The zone value ``'fine'`` is correctly parsed and stored as-is."""
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
        """A numeric zone value such as ``z50`` is correctly parsed."""
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
        """An unrecognised zone token (neither ``'fine'`` nor ``'z*'``) raises ``ValueError``."""
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
        """Two Move instructions on the same physical line are both parsed."""
        mod = tmp_path / "same_line.mod"
        mod.write_text(
            "MODULE same_line\n"
            "  MoveL [[1.0,2.0,3.0],[1.0,0.0,0.0,0.0],[0,0,0,0],[9E9,9E9,9E9,9E9,9E9,9E9]],v100,z0,Tool_A\\WObj:=Wobj_A;"
            " MoveL [[4.0,5.0,6.0],[1.0,0.0,0.0,0.0],[0,0,0,0],[9E9,9E9,9E9,9E9,9E9,9E9]],v100,z0,Tool_A\\WObj:=Wobj_A;\n"
            "ENDMODULE\n",
            encoding="utf-8",
        )
        traj = ModConverter().convert(mod)
        assert traj.point_count == 2

    # --- External axes: float values and edge cases ---

    def test_eax_multiple_active_axes(self, tmp_path: Path) -> None:
        """Multiple active external axes are all stored in the DataFrame."""
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
        """An external axis with a negative value is correctly parsed."""
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
        """An external axis at 0.0 (≠ 9E9) is considered active and stored."""
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
        """All axes at 9E9 → no ``eax_*`` column in the DataFrame."""
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

    # --- Continuation loop ---

    def test_instruction_without_robtarget_raises(self, tmp_path: Path) -> None:
        """A Move line with a named target (no inline robtarget) raises ``ValueError``."""
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
        """``convert_and_save()`` creates the ``.trajcenter`` file."""
        result = ModConverter().convert_and_save(source=mod_simple, dest_dir=tmp_path)
        assert result.exists()
        assert result.name == "simple.trajcenter"

    def test_convert_and_save_custom_stem(
        self, tmp_path: Path, mod_simple: Path
    ) -> None:
        """``convert_and_save()`` uses the custom stem when provided."""
        result = ModConverter().convert_and_save(
            source=mod_simple, dest_dir=tmp_path, stem="ma_trajectoire"
        )
        assert result.name == "ma_trajectoire.trajcenter"

    # --- Roundtrip ---

    def test_full_roundtrip(self, tmp_path: Path, mod_simple: Path) -> None:
        """``convert → save → load`` produces an identical trajectory."""
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
    """Tests for the ``_index_to_list`` utility function."""

    def test_single_entry(self) -> None:
        """A single entry is correctly converted."""
        assert _index_to_list({"Tool_formage": 0}) == ["Tool_formage"]

    def test_multiple_entries_ordered(self) -> None:
        """Entries are ordered by index value."""
        assert _index_to_list({"Tool_A": 0, "Tool_B": 1, "Tool_C": 2}) == [
            "Tool_A",
            "Tool_B",
            "Tool_C",
        ]

    def test_insertion_order_preserved(self) -> None:
        """Order is correct even when indices are not inserted in sorted order."""
        result = _index_to_list({"Tool_B": 1, "Tool_A": 0})
        assert result == ["Tool_A", "Tool_B"]

    def test_empty_dict(self) -> None:
        """An empty dict produces an empty list."""
        assert _index_to_list({}) == []
