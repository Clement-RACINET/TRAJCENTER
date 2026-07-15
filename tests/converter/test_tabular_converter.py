#!/usr/bin/env python3
# tests/test_tabular_converter.py
"""Unit tests for :mod:`trajcenter.converter.column_mapper` and the shared
logic of :mod:`trajcenter.converter.tabular_converter`.

Author: Clement RACINET

Covers:

- :func:`~trajcenter.converter.column_mapper.canonical_name`
- :func:`~trajcenter.converter.column_mapper.resolve_columns`
- Shared logic of
  :class:`~trajcenter.converter.tabular_converter._TabularConverter`
  (column resolution, tools/wobjs tables, identity quaternion,
  autocompletion) tested via
  :class:`~trajcenter.converter.csv_converter.CsvConverter`
  as a minimal concrete proxy.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from trajcenter.converter.column_mapper import (
    COLUMN_ALIASES,
    canonical_name,
    resolve_columns,
)
from trajcenter.converter.csv_converter import CsvConverter
from trajcenter.converter.defaults import ConversionDefaults

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_csv(
    tmp_path: Path, name: str, content: str, encoding: str = "utf-8"
) -> Path:
    """Write a synthetic CSV file and return its path.

    Args:
        tmp_path: Temporary directory provided by pytest.
        name: File name (including extension).
        content: Raw CSV content to write.
        encoding: File encoding (default: ``"utf-8"``).

    Returns:
        Path to the written CSV file.
    """
    p = tmp_path / name
    p.write_text(content, encoding=encoding)
    return p


# ---------------------------------------------------------------------------
# Tests — canonical_name
# ---------------------------------------------------------------------------


class TestCanonicalName:
    """Tests for the ``canonical_name`` function."""

    def test_exact_lowercase(self) -> None:
        """An exact lowercase alias is recognised."""
        assert canonical_name("x") == "x"
        assert canonical_name("vitesse") == "speed"
        assert canonical_name("repere") == "wobj"

    def test_uppercase(self) -> None:
        """Uppercase letters are ignored."""
        assert canonical_name("X") == "x"
        assert canonical_name("VITESSE") == "speed"
        assert canonical_name("PosX") == "x"

    def test_accents(self) -> None:
        """Diacritics are stripped before comparison."""
        assert canonical_name("Répère") == "wobj"
        assert canonical_name("REPÈRE") == "wobj"

    def test_unknown_returns_none(self) -> None:
        """An unknown name returns ``None``."""
        assert canonical_name("foobar") is None
        assert canonical_name("colonne_inconnue") is None

    def test_all_canonical_names_resolve_to_themselves(self) -> None:
        """Every canonical name resolves to itself."""
        for canon in COLUMN_ALIASES:
            assert canonical_name(canon) == canon

    def test_quaternion_aliases(self) -> None:
        """Quaternion aliases are correctly resolved."""
        assert canonical_name("qw") == "q1"
        assert canonical_name("qi") == "q2"
        assert canonical_name("qj") == "q3"
        assert canonical_name("qk") == "q4"


# ---------------------------------------------------------------------------
# Tests — resolve_columns
# ---------------------------------------------------------------------------


class TestResolveColumns:
    """Tests for the ``resolve_columns`` function."""

    def test_canonical_columns_unchanged(self) -> None:
        """Already-canonical columns are not modified."""
        df = pd.DataFrame(columns=["x", "y", "z"])
        df_out, unknown = resolve_columns(df)
        assert list(df_out.columns) == ["x", "y", "z"]
        assert unknown == []

    def test_alias_resolved(self) -> None:
        """Aliases are correctly renamed to their canonical form."""
        df = pd.DataFrame(columns=["PosX", "PosY", "PosZ"])
        df_out, unknown = resolve_columns(df)
        assert "x" in df_out.columns
        assert "y" in df_out.columns
        assert "z" in df_out.columns

    def test_unknown_columns_returned(self) -> None:
        """Unknown columns are returned in the list and left intact."""
        df = pd.DataFrame(columns=["x", "y", "z", "custom_col"])
        df_out, unknown = resolve_columns(df)
        assert "custom_col" in unknown
        assert "custom_col" in df_out.columns

    def test_duplicate_canonical_warns(self) -> None:
        """A duplicate canonical name emits a ``UserWarning`` and keeps the first column."""
        df = pd.DataFrame(columns=["x", "pos_x", "y", "z"])
        with pytest.warns(UserWarning, match="pos_x"):
            df_out, _ = resolve_columns(df)
        assert df_out.columns.tolist().count("x") == 1

    def test_accent_and_case_resolved(self) -> None:
        """Mixed casing and accents are resolved correctly."""
        df = pd.DataFrame(columns=["Répère", "VITESSE", "PosX", "PosY", "PosZ"])
        df_out, unknown = resolve_columns(df)
        assert "wobj" in df_out.columns
        assert "speed" in df_out.columns
        assert unknown == []


# ---------------------------------------------------------------------------
# Tests — shared _TabularConverter logic (via CsvConverter)
# ---------------------------------------------------------------------------


class TestTabularConverterLogic:
    """Tests for shared tabular converter logic via CsvConverter as a concrete proxy."""

    # --- Basic errors ---

    def test_file_not_found_raises(self, tmp_path: Path) -> None:
        """``convert()`` raises ``FileNotFoundError`` when the file does not exist."""
        with pytest.raises(FileNotFoundError, match=r"not found|introuvable"):
            CsvConverter().convert(tmp_path / "inexistant.csv")

    def test_missing_xyz_raises(self, csv_missing_xyz: Path) -> None:
        """``convert()`` raises ``ValueError`` when XYZ columns are absent."""
        with pytest.raises(
            ValueError, match=r"[Mm]issing.*columns|obligatoires manquantes"
        ):
            CsvConverter().convert(csv_missing_xyz)

    # --- Identity quaternion ---

    def test_xyz_only_quaternion_identity(self, tmp_path: Path) -> None:
        """Without quaternion columns, identity orientation is applied."""
        csv = _write_csv(tmp_path, "xyz.csv", "x,y,z\n1.0,2.0,3.0\n")
        traj = CsvConverter().convert(csv)
        assert traj.points["q1"].iloc[0] == pytest.approx(1.0)
        assert traj.points["q2"].iloc[0] == pytest.approx(0.0)
        assert traj.points["q3"].iloc[0] == pytest.approx(0.0)
        assert traj.points["q4"].iloc[0] == pytest.approx(0.0)

    def test_xyz_only_quaternion_autocompleted(self, tmp_path: Path) -> None:
        """Quaternion columns are listed in ``autocompleted``."""
        csv = _write_csv(tmp_path, "xyz.csv", "x,y,z\n1.0,2.0,3.0\n")
        traj = CsvConverter().convert(csv)
        for col in ("q1", "q2", "q3", "q4"):
            assert col in traj.meta.autocompleted

    # --- Autocompletion ---

    def test_speed_autocompleted(self, tmp_path: Path) -> None:
        """``speed`` is autocompleted when absent from the source."""
        csv = _write_csv(tmp_path, "xyz.csv", "x,y,z\n1.0,2.0,3.0\n")
        traj = CsvConverter().convert(csv)
        assert "speed" in traj.meta.autocompleted

    def test_custom_default_speed(self, tmp_path: Path) -> None:
        """The custom default speed is applied during autocompletion."""
        csv = _write_csv(tmp_path, "xyz.csv", "x,y,z\n1.0,2.0,3.0\n")
        traj = CsvConverter(defaults=ConversionDefaults(speed="v250")).convert(csv)
        assert traj.points["speed"].iloc[0] == "v250"

    def test_move_type_not_autocompleted_when_present(self, tmp_path: Path) -> None:
        """``move_type`` present in the source is not listed in ``autocompleted``."""
        csv = _write_csv(tmp_path, "full.csv", "x,y,z,move_type\n1.0,2.0,3.0,MoveL\n")
        traj = CsvConverter().convert(csv)
        assert "move_type" not in traj.meta.autocompleted
        assert traj.points["move_type"].iloc[0] == "MoveL"

    # --- Column aliases ---

    def test_alias_columns_resolved(self, tmp_path: Path) -> None:
        """Column aliases are correctly resolved."""
        csv = _write_csv(
            tmp_path, "alias.csv", "PosX,PosY,PosZ,VITESSE\n1.0,2.0,3.0,v500\n"
        )
        traj = CsvConverter().convert(csv)
        assert traj.points["x"].iloc[0] == pytest.approx(1.0)
        assert traj.points["speed"].iloc[0] == "v500"

    def test_unknown_columns_warned(self, csv_unknown_col: Path) -> None:
        """Unknown columns emit a ``UserWarning``."""
        with pytest.warns(UserWarning, match=r"[Uu]nknown|inconnue"):
            CsvConverter().convert(csv_unknown_col)

    # --- Tools / wobjs tables ---

    def test_tool_column_extracted(self, tmp_path: Path) -> None:
        """The ``tool`` column is extracted and converted to ``tool_index``."""
        csv = _write_csv(
            tmp_path,
            "tools.csv",
            "x,y,z,tool\n1.0,2.0,3.0,Tool_A\n4.0,5.0,6.0,Tool_B\n",
        )
        traj = CsvConverter().convert(csv)
        assert "Tool_A" in traj.tools
        assert "Tool_B" in traj.tools
        assert "tool" not in traj.points.columns
        assert "tool_index" in traj.points.columns

    def test_wobj_column_extracted(self, tmp_path: Path) -> None:
        """The ``wobj`` column is extracted and converted to ``wobj_index``."""
        csv = _write_csv(tmp_path, "wobj.csv", "x,y,z,wobj\n1.0,2.0,3.0,Wobj_A\n")
        traj = CsvConverter().convert(csv)
        assert "Wobj_A" in traj.wobjs

    # --- Metadata defaults ---

    def test_no_meta_overrides_name_is_stem(self, tmp_path: Path) -> None:
        """Without a meta sheet, the name defaults to the source file stem."""
        csv = _write_csv(tmp_path, "ma_traj.csv", "x,y,z\n1.0,2.0,3.0\n")
        traj = CsvConverter().convert(csv)
        assert traj.meta.name == "ma_traj"

    def test_no_meta_overrides_robot_model_is_none(self, tmp_path: Path) -> None:
        """Without a meta sheet, ``robot_model`` is ``None``."""
        csv = _write_csv(tmp_path, "xyz.csv", "x,y,z\n1.0,2.0,3.0\n")
        assert CsvConverter().convert(csv).meta.robot_model is None

    def test_no_meta_overrides_extra_is_empty(self, tmp_path: Path) -> None:
        """Without a meta sheet, ``extra{}`` is empty."""
        csv = _write_csv(tmp_path, "xyz.csv", "x,y,z\n1.0,2.0,3.0\n")
        assert CsvConverter().convert(csv).meta.extra == {}

    # --- Empty rows ---

    def test_empty_rows_dropped(self, tmp_path: Path) -> None:
        """Fully empty rows are dropped."""
        csv = _write_csv(
            tmp_path, "empty_rows.csv", "x,y,z\n1.0,2.0,3.0\n,,\n4.0,5.0,6.0\n"
        )
        traj = CsvConverter().convert(csv)
        assert traj.point_count == 2

    # --- is_complete ---

    def test_is_complete(self, tmp_path: Path) -> None:
        """The produced trajectory is always complete."""
        csv = _write_csv(tmp_path, "xyz.csv", "x,y,z\n1.0,2.0,3.0\n")
        assert CsvConverter().convert(csv).is_complete is True
