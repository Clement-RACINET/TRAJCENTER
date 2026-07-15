#!/usr/bin/env python3
# tests/test_excel_converter.py
"""Unit tests specific to :mod:`trajcenter.converter.excel_converter`.

Author: Clement RACINET

Covers only Excel-specific behaviour:

- Multi-sheet reading
- ``tools`` / ``wobjs`` / ``meta`` sheets
- Empty row handling
- Excel column aliases
- Save/load roundtrip

Common logic (``canonical_name``, ``resolve_columns``, identity quaternion,
autocompletion) is tested in ``test_tabular_converter.py``.
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
    """Tests specific to the ExcelConverter class."""

    # --- Basic errors ---

    def test_file_not_found_raises(self, tmp_path: Path) -> None:
        """``convert()`` raises ``FileNotFoundError`` when the file does not exist."""
        with pytest.raises(FileNotFoundError, match="introuvable"):
            ExcelConverter().convert(tmp_path / "inexistant.xlsx")

    def test_missing_xyz_raises(self, xlsx_missing_xyz: Path) -> None:
        """``convert()`` raises ``ValueError`` when XYZ columns are absent."""
        with pytest.raises(ValueError, match="obligatoires manquantes"):
            ExcelConverter().convert(xlsx_missing_xyz)

    def test_multi_traj_convert_raises(self, xlsx_multi_traj: Path) -> None:
        """``convert()`` raises ``ValueError`` when multiple trajectory sheets exist."""
        with pytest.raises(ValueError, match="convert_all"):
            ExcelConverter().convert(xlsx_multi_traj)

    # --- Nominal case ---

    def test_point_count(self, xlsx_simple: Path) -> None:
        """A 2-row sheet produces 2 points."""
        assert ExcelConverter().convert(xlsx_simple).point_count == 2

    def test_source_format(self, xlsx_simple: Path) -> None:
        """``source_format`` is ``EXCEL``."""
        assert ExcelConverter().convert(xlsx_simple).meta.source_format == SourceFormat.EXCEL

    def test_source_file(self, xlsx_simple: Path) -> None:
        """``source_file`` contains the file name."""
        assert ExcelConverter().convert(xlsx_simple).meta.source_file == "simple.xlsx"

    def test_name(self, xlsx_simple: Path) -> None:
        """``name`` is the file stem for a single default sheet."""
        assert ExcelConverter().convert(xlsx_simple).meta.name == "simple"

    def test_coordinates(self, xlsx_simple: Path) -> None:
        """x, y, z coordinates are correctly read."""
        traj = ExcelConverter().convert(xlsx_simple)
        assert traj.points["x"].iloc[0] == pytest.approx(100.0)
        assert traj.points["y"].iloc[0] == pytest.approx(200.0)
        assert traj.points["z"].iloc[0] == pytest.approx(300.0)

    def test_quaternions(self, xlsx_simple: Path) -> None:
        """Quaternion values are correctly read."""
        traj = ExcelConverter().convert(xlsx_simple)
        assert traj.points["q1"].iloc[0] == pytest.approx(1.0)
        assert traj.points["q2"].iloc[0] == pytest.approx(0.0)

    def test_is_complete(self, xlsx_simple: Path) -> None:
        """The produced trajectory is complete."""
        assert ExcelConverter().convert(xlsx_simple).is_complete is True

    # --- XYZ-only → identity quaternion ---

    def test_xyz_only_quaternion_identity(self, xlsx_xyz_only: Path) -> None:
        """Without quaternion columns, identity orientation is applied."""
        traj = ExcelConverter().convert(xlsx_xyz_only)
        assert traj.points["q1"].iloc[0] == pytest.approx(1.0)
        assert traj.points["q2"].iloc[0] == pytest.approx(0.0)

    def test_xyz_only_quaternion_autocompleted(self, xlsx_xyz_only: Path) -> None:
        """Quaternion columns are listed in ``autocompleted``."""
        traj = ExcelConverter().convert(xlsx_xyz_only)
        for col in ("q1", "q2", "q3", "q4"):
            assert col in traj.meta.autocompleted

    # --- Aliases and accents ---

    def test_aliases_resolved(self, xlsx_aliases: Path) -> None:
        """Column aliases (including accented names) are correctly resolved."""
        traj = ExcelConverter().convert(xlsx_aliases)
        assert traj.points["x"].iloc[0] == pytest.approx(1.0)
        assert traj.points["speed"].iloc[0] == "v500"

    def test_aliases_no_spurious_warning(self, xlsx_aliases: Path) -> None:
        """Resolving aliases does not emit spurious 'unrecognised columns' warnings."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            ExcelConverter().convert(xlsx_aliases)
        unknown_warnings = [x for x in w if "non reconnues" in str(x.message)]
        assert len(unknown_warnings) == 0

    # --- Multi-sheet ---

    def test_multi_traj_count(self, xlsx_multi_traj: Path) -> None:
        """``convert_all()`` returns one trajectory per trajectory sheet."""
        assert len(ExcelConverter().convert_all(xlsx_multi_traj)) == 2

    def test_multi_traj_names(self, xlsx_multi_traj: Path) -> None:
        """Each trajectory is named after its sheet."""
        names = {t.meta.name for t in ExcelConverter().convert_all(xlsx_multi_traj)}
        assert "multi_traj_traj_A" in names
        assert "multi_traj_traj_B" in names

    def test_multi_traj_point_counts(self, xlsx_multi_traj: Path) -> None:
        """Each sheet produces the correct number of points."""
        counts = {
            t.meta.name: t.point_count
            for t in ExcelConverter().convert_all(xlsx_multi_traj)
        }
        assert counts["multi_traj_traj_A"] == 1
        assert counts["multi_traj_traj_B"] == 2

    # --- tools / wobjs sheets ---

    def test_tools_sheet_loaded(self, xlsx_with_tools_sheet: Path) -> None:
        """Tool names from the ``tools`` sheet are loaded into ``traj.tools``."""
        traj = ExcelConverter().convert(xlsx_with_tools_sheet)
        assert "Tool_A" in traj.tools
        assert "Tool_B" in traj.tools

    def test_wobjs_sheet_loaded(self, xlsx_with_tools_sheet: Path) -> None:
        """Wobj names from the ``wobjs`` sheet are loaded into ``traj.wobjs``."""
        assert "Wobj_A" in ExcelConverter().convert(xlsx_with_tools_sheet).wobjs

    def test_tool_index_consistency(self, xlsx_with_tools_sheet: Path) -> None:
        """``tool_index`` consistently points to the correct entry in ``tools[]``."""
        traj = ExcelConverter().convert(xlsx_with_tools_sheet)
        for _, row in traj.points.iterrows():
            assert traj.tools[int(row["tool_index"])] in ("Tool_A", "Tool_B")

    # --- meta sheet ---

    def test_meta_sheet_not_a_traj_sheet(self, xlsx_with_meta_sheet: Path) -> None:
        """The ``meta`` sheet is not treated as a trajectory sheet."""
        assert ExcelConverter().convert(xlsx_with_meta_sheet).point_count == 1

    def test_meta_sheet_name_override(self, xlsx_with_full_meta: Path) -> None:
        """The ``meta`` sheet overrides the trajectory name."""
        traj = ExcelConverter().convert(xlsx_with_full_meta)
        assert traj.meta.name == "Trajectoire_Soudure"

    def test_meta_sheet_robot_model(self, xlsx_with_full_meta: Path) -> None:
        """The ``meta`` sheet populates ``robot_model``."""
        traj = ExcelConverter().convert(xlsx_with_full_meta)
        assert traj.meta.robot_model == "IRB6700-205/2.80"

    def test_meta_sheet_extra_fields(self, xlsx_with_full_meta: Path) -> None:
        """Unknown fields from the ``meta`` sheet are stored in ``extra{}``."""
        traj = ExcelConverter().convert(xlsx_with_full_meta)
        assert traj.meta.extra.get("author") == "Jean Dupont"

    # --- Empty rows ---

    def test_empty_rows_dropped(self, xlsx_empty_rows: Path) -> None:
        """Fully empty rows are dropped."""
        assert ExcelConverter().convert(xlsx_empty_rows).point_count == 2

    # --- Custom defaults ---

    def test_custom_default_move_type(self, xlsx_xyz_only: Path) -> None:
        """The custom default move type is applied."""
        traj = ExcelConverter(
            defaults=ConversionDefaults(move_type="MoveL")
        ).convert(xlsx_xyz_only)
        assert traj.points["move_type"].iloc[0] == "MoveL"

    def test_custom_default_speed(self, xlsx_xyz_only: Path) -> None:
        """The custom default speed is applied."""
        traj = ExcelConverter(
            defaults=ConversionDefaults(speed="v250")
        ).convert(xlsx_xyz_only)
        assert traj.points["speed"].iloc[0] == "v250"

    # --- Roundtrip ---

    def test_full_roundtrip(self, tmp_path: Path, xlsx_simple: Path) -> None:
        """``convert → save → load`` produces an identical trajectory."""
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
        """``convert_and_save()`` creates the ``.trajcenter`` file."""
        result = ExcelConverter().convert_and_save(
            source=xlsx_simple, dest_dir=tmp_path
        )
        assert result.exists()
        assert result.name == "simple.trajcenter"
