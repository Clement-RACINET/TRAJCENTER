# tests/exporter/test_tabular_exporter.py

"""
Tests unitaires pour _TabularExporter — logique de construction des DataFrames.

On teste _build_traj_df, _build_tools_df, _build_wobjs_df et _build_meta_df
directement via ExcelExporter (sous-classe concrète la plus simple).
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from trajcenter.core.trajectory import Trajectory
from trajcenter.exporter.excel_exporter import ExcelExporter
from trajcenter.exporter.options import ExportOptions
from trajcenter.exporter.tabular_exporter import _TRAJ_COL_ORDER


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _exporter(options: ExportOptions | None = None) -> ExcelExporter:
    return ExcelExporter(options)


# ---------------------------------------------------------------------------
# _build_traj_df
# ---------------------------------------------------------------------------


class TestBuildTrajDf:
    def test_tool_index_resolved_to_name(self, traj_basic: Trajectory) -> None:
        """tool_index=0 → colonne 'tool' avec le nom correspondant."""
        df = _exporter()._build_traj_df(traj_basic)
        assert "tool" in df.columns
        assert (df["tool"] == "tool0").all()

    def test_wobj_index_resolved_to_name(self, traj_basic: Trajectory) -> None:
        """wobj_index=0 → colonne 'wobj' avec le nom correspondant."""
        df = _exporter()._build_traj_df(traj_basic)
        assert "wobj" in df.columns
        assert (df["wobj"] == "wobj0").all()

    def test_tool_index_column_dropped(self, traj_basic: Trajectory) -> None:
        """La colonne tool_index doit disparaître après résolution."""
        df = _exporter()._build_traj_df(traj_basic)
        assert "tool_index" not in df.columns

    def test_wobj_index_column_dropped(self, traj_basic: Trajectory) -> None:
        """La colonne wobj_index doit disparaître après résolution."""
        df = _exporter()._build_traj_df(traj_basic)
        assert "wobj_index" not in df.columns

    def test_multi_tools_resolved_correctly(self, traj_multi_tools: Trajectory) -> None:
        """tool_index 0 → Tool_A, tool_index 1 → Tool_B."""
        df = _exporter()._build_traj_df(traj_multi_tools)
        assert df["tool"].tolist() == ["Tool_A", "Tool_B"]

    def test_multi_wobjs_resolved_correctly(self, traj_multi_tools: Trajectory) -> None:
        """wobj_index 0 → Wobj_A, wobj_index 1 → Wobj_B."""
        df = _exporter()._build_traj_df(traj_multi_tools)
        assert df["wobj"].tolist() == ["Wobj_A", "Wobj_B"]

    def test_float_precision_applied(self, traj_basic: Trajectory) -> None:
        """Les floats sont arrondis selon float_precision."""
        opts = ExportOptions(float_precision=2)
        df = _exporter(opts)._build_traj_df(traj_basic)
        # Vérifie que les valeurs ont au plus 2 décimales
        for col in ["x", "y", "z", "q1", "q2", "q3", "q4"]:
            if col in df.columns:
                rounded = df[col].round(2)
                pd.testing.assert_series_equal(df[col], rounded, check_names=False)

    def test_column_order_respects_traj_col_order(self, traj_basic: Trajectory) -> None:
        """Les colonnes connues apparaissent dans l'ordre défini par _TRAJ_COL_ORDER."""
        df = _exporter()._build_traj_df(traj_basic)
        known_cols = [c for c in _TRAJ_COL_ORDER if c in df.columns]
        actual_leading = df.columns[:len(known_cols)].tolist()
        assert actual_leading == known_cols

    def test_index_reset(self, traj_basic: Trajectory) -> None:
        """L'index du DataFrame résultant commence à 0."""
        df = _exporter()._build_traj_df(traj_basic)
        assert df.index.tolist() == list(range(len(df)))

    def test_row_count_preserved(self, traj_basic: Trajectory) -> None:
        """Le nombre de lignes est identique à la trajectoire source."""
        df = _exporter()._build_traj_df(traj_basic)
        assert len(df) == len(traj_basic.points)


# ---------------------------------------------------------------------------
# _build_tools_df
# ---------------------------------------------------------------------------


class TestBuildToolsDf:
    def test_single_tool(self, traj_basic: Trajectory) -> None:
        df = _exporter()._build_tools_df(traj_basic)
        assert list(df.columns) == ["name"]
        assert df["name"].tolist() == ["tool0"]

    def test_multi_tools(self, traj_multi_tools: Trajectory) -> None:
        df = _exporter()._build_tools_df(traj_multi_tools)
        assert df["name"].tolist() == ["Tool_A", "Tool_B"]

    def test_order_preserved(self, traj_multi_tools: Trajectory) -> None:
        """L'ordre des tools dans la liste source est préservé."""
        df = _exporter()._build_tools_df(traj_multi_tools)
        assert df["name"].tolist() == traj_multi_tools.tools


# ---------------------------------------------------------------------------
# _build_wobjs_df
# ---------------------------------------------------------------------------


class TestBuildWobjsDf:
    def test_single_wobj(self, traj_basic: Trajectory) -> None:
        df = _exporter()._build_wobjs_df(traj_basic)
        assert list(df.columns) == ["name"]
        assert df["name"].tolist() == ["wobj0"]

    def test_multi_wobjs(self, traj_multi_tools: Trajectory) -> None:
        df = _exporter()._build_wobjs_df(traj_multi_tools)
        assert df["name"].tolist() == ["Wobj_A", "Wobj_B"]


# ---------------------------------------------------------------------------
# _build_meta_df
# ---------------------------------------------------------------------------


class TestBuildMetaDf:
    def test_name_present(self, traj_with_meta: Trajectory) -> None:
        df = _exporter()._build_meta_df(traj_with_meta)
        assert "name" in df["key"].values

    def test_robot_model_present(self, traj_with_meta: Trajectory) -> None:
        df = _exporter()._build_meta_df(traj_with_meta)
        assert "robot_model" in df["key"].values

    def test_robot_model_value(self, traj_with_meta: Trajectory) -> None:
        df = _exporter()._build_meta_df(traj_with_meta)
        row = df[df["key"] == "robot_model"]
        assert row["value"].iloc[0] == "IRB6700-205/2.80"

    def test_extra_fields_present(self, traj_with_meta: Trajectory) -> None:
        """Les champs extra{} sont dépliés comme entrées individuelles."""
        df = _exporter()._build_meta_df(traj_with_meta)
        assert "author" in df["key"].values
        assert "project" in df["key"].values

    def test_extra_author_value(self, traj_with_meta: Trajectory) -> None:
        df = _exporter()._build_meta_df(traj_with_meta)
        row = df[df["key"] == "author"]
        assert row["value"].iloc[0] == "Jean Dupont"

    def test_columns_are_key_value(self, traj_basic: Trajectory) -> None:
        df = _exporter()._build_meta_df(traj_basic)
        assert list(df.columns) == ["key", "value"]

    def test_point_count_excluded(self, traj_basic: Trajectory) -> None:
        """point_count est dans _META_SKIP_FIELDS et ne doit pas apparaître."""
        df = _exporter()._build_meta_df(traj_basic)
        assert "point_count" not in df["key"].values

    def test_autocompleted_excluded(self, traj_basic: Trajectory) -> None:
        """autocompleted est dans _META_SKIP_FIELDS et ne doit pas apparaître."""
        df = _exporter()._build_meta_df(traj_basic)
        assert "autocompleted" not in df["key"].values

    def test_none_fields_excluded(self, traj_basic: Trajectory) -> None:
        """Les champs None (robot_model absent) ne doivent pas apparaître."""
        df = _exporter()._build_meta_df(traj_basic)
        assert "robot_model" not in df["key"].values
