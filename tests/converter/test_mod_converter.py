#!/usr/bin/env python3
# tests/converter/test_mod_converter.py
"""Unit tests for :mod:`trajcenter.converter.mod_converter`.

Author: Clement RACINET
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from trajcenter.converter.defaults import ConversionDefaults
from trajcenter.converter.mod_converter import ModConverter, _index_to_list
from trajcenter.core.trajectory import SourceFormat, Trajectory


class TestModConverter:
    """Tests for the ModConverter class."""

    def test_file_not_found_raises(self, tmp_path: Path) -> None:
        """convert raises FileNotFoundError when source does not exist."""
        with pytest.raises(FileNotFoundError, match=r"[Ff]ile not found|introuvable"):
            ModConverter().convert(tmp_path / "inexistant.mod")

    def test_empty_mod_raises(self, mod_empty: Path) -> None:
        """convert raises ValueError when no Move instruction is found."""
        with pytest.raises(ValueError, match=r"[Nn]o.*[Mm]ove|[Aa]ucune instruction"):
            ModConverter().convert(mod_empty)

    def test_source_format(self, mod_simple: Path) -> None:
        """source_format is RAPID."""
        assert (
            ModConverter().convert(mod_simple).meta.source_format == SourceFormat.RAPID
        )

    def test_source_file(self, mod_simple: Path) -> None:
        """source_file contains the file name."""
        assert ModConverter().convert(mod_simple).meta.source_file == "simple.mod"

    def test_name(self, mod_simple: Path) -> None:
        """name is the file stem."""
        assert ModConverter().convert(mod_simple).meta.name == "simple"

    def test_point_count(self, mod_simple: Path) -> None:
        """A file with two MoveL instructions produces two points."""
        assert ModConverter().convert(mod_simple).point_count == 2

    def test_required_geometry_columns_present(self, mod_simple: Path) -> None:
        """The produced trajectory contains required geometry columns."""
        traj = ModConverter().convert(mod_simple)

        for col in ["x", "y", "z", "q1", "q2", "q3", "q4"]:
            assert col in traj.points.columns

    def test_coordinates(self, mod_simple: Path) -> None:
        """x, y and z coordinates are parsed."""
        traj = ModConverter().convert(mod_simple)
        assert traj.points["x"].iloc[0] == pytest.approx(100.0)
        assert traj.points["y"].iloc[0] == pytest.approx(200.0)
        assert traj.points["z"].iloc[0] == pytest.approx(300.0)

    def test_quaternions(self, mod_simple: Path) -> None:
        """Quaternion values are parsed."""
        traj = ModConverter().convert(mod_simple)
        assert traj.points["q1"].iloc[0] == pytest.approx(1.0)
        assert traj.points["q2"].iloc[0] == pytest.approx(0.0)

    def test_variable_zone_not_stored_without_default(self, mod_zone_var: Path) -> None:
        """Unresolved RAPID zone variables are not stored by default."""
        traj = ModConverter().convert(mod_zone_var)
        assert "zone_type" not in traj.points.columns

    def test_move_type(self, mod_simple: Path) -> None:
        """MoveL move type is parsed."""
        assert ModConverter().convert(mod_simple).points["move_type"].iloc[0] == "MoveL"

    def test_tool_wobj_names(self, mod_simple: Path) -> None:
        """Tool and wobj are stored inline as v2 name columns."""
        traj = ModConverter().convert(mod_simple)
        assert traj.points["tool_name"].iloc[0] == "Tool_formage"
        assert traj.points["wobj_name"].iloc[0] == "Wobj_SerreFlan"
        assert "tool_index" not in traj.points.columns
        assert "wobj_index" not in traj.points.columns

    def test_multiple_tool_names_preserved(self, mod_multiple_tools: Path) -> None:
        """Multiple tools are preserved as inline names."""
        traj = ModConverter().convert(mod_multiple_tools)
        assert traj.points["tool_name"].tolist() == [
            "Tool_A",
            "Tool_B",
            "Tool_A",
        ]

    def test_multiple_wobj_names_preserved(self, mod_multiple_tools: Path) -> None:
        """Multiple wobjs are preserved as inline names."""
        traj = ModConverter().convert(mod_multiple_tools)
        assert traj.points["wobj_name"].tolist() == [
            "Wobj_A",
            "Wobj_B",
            "Wobj_A",
        ]

    def test_variable_speed_not_stored_without_default(self, mod_simple: Path) -> None:
        """Unresolved RAPID speed variables are not stored by default."""
        traj = ModConverter().convert(mod_simple)
        assert "tcp_speed" not in traj.points.columns
        assert "tcp_speed" not in traj.meta.autocompleted

    def test_variable_speed_custom_default(self, mod_simple: Path) -> None:
        """Explicit requested tcp_speed default is applied for variable speed files."""
        traj = ModConverter(
            defaults=ConversionDefaults(
                autocomplete_columns={"tcp_speed"},
                tcp_speed=200.0,
            )
        ).convert(mod_simple)

        assert traj.points["tcp_speed"].iloc[0] == pytest.approx(200.0)
        assert "tcp_speed" in traj.meta.autocompleted

    def test_literal_speed_not_autocompleted(
        self, mod_with_literal_speed: Path
    ) -> None:
        """Literal RAPID speeds are parsed to numeric tcp_speed."""
        traj = ModConverter().convert(mod_with_literal_speed)
        assert "tcp_speed" not in traj.meta.autocompleted
        assert traj.points["tcp_speed"].iloc[0] == pytest.approx(500.0)
        assert traj.points["tcp_speed"].iloc[1] == pytest.approx(1000.0)

    def test_literal_zone_not_autocompleted(self, mod_with_literal_speed: Path) -> None:
        """Literal RAPID zones are parsed to numeric zone_type."""
        traj = ModConverter().convert(mod_with_literal_speed)
        assert "zone_type" not in traj.meta.autocompleted
        assert traj.points["zone_type"].iloc[0] == 10
        assert traj.points["zone_type"].iloc[1] == 255

    def test_mixed_move_types(self, mod_with_literal_speed: Path) -> None:
        """MoveL and MoveJ are distinguished."""
        traj = ModConverter().convert(mod_with_literal_speed)
        assert traj.points["move_type"].iloc[0] == "MoveL"
        assert traj.points["move_type"].iloc[1] == "MoveJ"

    def test_eax_active_stored(self, mod_with_eax: Path) -> None:
        """An active external axis is stored."""
        traj = ModConverter().convert(mod_with_eax)
        assert "eax_a" in traj.points.columns
        assert traj.points["eax_a"].iloc[0] == pytest.approx(45.0)

    def test_eax_inactive_not_stored(self, mod_with_eax: Path) -> None:
        """Inactive 9E9 axes are not stored."""
        traj = ModConverter().convert(mod_with_eax)
        for col in ["eax_b", "eax_c", "eax_d", "eax_e", "eax_f"]:
            assert col not in traj.points.columns

    def test_multiline_robtarget(self, mod_multiline: Path) -> None:
        """A robtarget across multiple lines is parsed."""
        traj = ModConverter().convert(mod_multiline)
        assert traj.point_count == 1
        assert traj.points["x"].iloc[0] == pytest.approx(100.0)

    def test_confdata_parsed(self, mod_with_literal_speed: Path) -> None:
        """Confdata values are parsed."""
        traj = ModConverter().convert(mod_with_literal_speed)
        assert traj.points["cf1"].iloc[0] == 0
        assert traj.points["cf1"].iloc[1] == -1
        assert traj.points["cf6"].iloc[1] == 1

    def test_confdata_invalid_raises(self, mod_bad_confdata: Path) -> None:
        """convert raises ValueError on invalid confdata."""
        with pytest.raises(ValueError, match=r"[Cc]onfdata|[Ii]nvalid"):
            ModConverter().convert(mod_bad_confdata)

    def test_zone_fine(self, tmp_path: Path) -> None:
        """fine is parsed as zone_type=255."""
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
        assert traj.points["zone_type"].iloc[0] == 255

    def test_zone_z_numeric(self, tmp_path: Path) -> None:
        """z50 is parsed as zone_type=50."""
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
        assert traj.points["zone_type"].iloc[0] == 50

    def test_zone_variable_custom_default(self, mod_zone_var: Path) -> None:
        """Explicit requested zone_type default is applied for variable zone files."""
        traj = ModConverter(
            defaults=ConversionDefaults(
                autocomplete_columns={"zone_type"},
                zone_type=10,
            )
        ).convert(mod_zone_var)

        assert traj.points["zone_type"].iloc[0] == 10
        assert "zone_type" in traj.meta.autocompleted

    def test_two_moves_same_physical_line(self, tmp_path: Path) -> None:
        """Two Move instructions on the same physical line are parsed."""
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

    def test_eax_multiple_active_axes(self, tmp_path: Path) -> None:
        """Multiple active external axes are stored."""
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
        assert traj.points["eax_a"].iloc[0] == pytest.approx(45.0)
        assert traj.points["eax_b"].iloc[0] == pytest.approx(90.0)
        assert "eax_c" not in traj.points.columns

    def test_eax_negative_value(self, tmp_path: Path) -> None:
        """A negative external axis value is parsed."""
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
        """External axis 0.0 is active and stored."""
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
        assert traj.points["eax_a"].iloc[0] == pytest.approx(0.0)

    def test_eax_all_inactive(self, tmp_path: Path) -> None:
        """All axes at 9E9 create no eax columns."""
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

    def test_instruction_without_robtarget_raises(self, mod_no_robtarget: Path) -> None:
        """convert raises ValueError when a Move has no inline robtarget."""
        with pytest.raises(ValueError, match=r"[Rr]obtarget|[Ii]nstruction"):
            ModConverter().convert(mod_no_robtarget)

    def test_mixed_speed_literal_and_variable_raises(self, tmp_path: Path) -> None:
        """Mixed speed literals and variables are rejected."""
        mod = tmp_path / "mixed_speed.mod"
        mod.write_text(
            "MODULE mixed_speed\n"
            "  MoveL [[1,2,3],[1,0,0,0],[0,0,0,0],[9E9,9E9,9E9,9E9,9E9,9E9]],v100,z0,Tool_A\\WObj:=Wobj_A;\n"
            "  MoveL [[4,5,6],[1,0,0,0],[0,0,0,0],[9E9,9E9,9E9,9E9,9E9,9E9]],vitesse,z0,Tool_A\\WObj:=Wobj_A;\n"
            "ENDMODULE\n",
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="Mixed RAPID speed"):
            ModConverter().convert(mod)

    def test_mixed_zone_literal_and_variable_raises(self, tmp_path: Path) -> None:
        """Mixed zone literals and variables are rejected."""
        mod = tmp_path / "mixed_zone.mod"
        mod.write_text(
            "MODULE mixed_zone\n"
            "  MoveL [[1,2,3],[1,0,0,0],[0,0,0,0],[9E9,9E9,9E9,9E9,9E9,9E9]],v100,z0,Tool_A\\WObj:=Wobj_A;\n"
            "  MoveL [[4,5,6],[1,0,0,0],[0,0,0,0],[9E9,9E9,9E9,9E9,9E9,9E9]],v100,ma_zone,Tool_A\\WObj:=Wobj_A;\n"
            "ENDMODULE\n",
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="Mixed RAPID zone"):
            ModConverter().convert(mod)

    def test_convert_and_save(self, tmp_path: Path, mod_simple: Path) -> None:
        """convert_and_save creates the trajcenter file."""
        result = ModConverter().convert_and_save(source=mod_simple, dest_dir=tmp_path)
        assert result.exists()
        assert result.name == "simple.trajcenter"

    def test_convert_and_save_custom_stem(
        self, tmp_path: Path, mod_simple: Path
    ) -> None:
        """convert_and_save uses the custom stem when provided."""
        result = ModConverter().convert_and_save(
            source=mod_simple,
            dest_dir=tmp_path,
            stem="ma_trajectoire",
        )
        assert result.name == "ma_trajectoire.trajcenter"

    def test_full_roundtrip(self, tmp_path: Path, mod_simple: Path) -> None:
        """convert → save → load produces an equivalent trajectory."""
        traj = ModConverter().convert(mod_simple)
        dest = tmp_path / "simple.trajcenter"
        traj.save(dest)
        loaded = Trajectory.load(dest)

        assert loaded.point_count == traj.point_count
        assert list(loaded.points.columns) == list(traj.points.columns)
        pd.testing.assert_series_equal(
            loaded.points["x"].reset_index(drop=True),
            traj.points["x"].reset_index(drop=True),
            check_names=False,
        )


class TestIndexToList:
    """Tests for the _index_to_list compatibility utility."""

    def test_single_entry(self) -> None:
        """A single entry is converted."""
        assert _index_to_list({"Tool_formage": 0}) == ["Tool_formage"]

    def test_multiple_entries_ordered(self) -> None:
        """Entries are ordered by index value."""
        assert _index_to_list({"Tool_A": 0, "Tool_B": 1, "Tool_C": 2}) == [
            "Tool_A",
            "Tool_B",
            "Tool_C",
        ]

    def test_insertion_order_preserved(self) -> None:
        """Order is correct when indices are inserted out of order."""
        result = _index_to_list({"Tool_B": 1, "Tool_A": 0})
        assert result == ["Tool_A", "Tool_B"]

    def test_empty_dict(self) -> None:
        """An empty dict produces an empty list."""
        assert _index_to_list({}) == []
