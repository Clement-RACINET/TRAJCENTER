#!/usr/bin/env python3
# tests/exporter/test_tabular_exporter.py
"""Unit tests for ``_TabularExporter`` — DataFrame construction logic.

Author: Clement RACINET

Tests ``_build_traj_df``, ``_build_tools_df``, ``_build_wobjs_df`` and
``_build_meta_df`` directly via :class:`~trajcenter.exporter.excel_exporter.ExcelExporter`
as the simplest concrete subclass.
"""

from __future__ import annotations

import pandas as pd

from trajcenter.core.trajectory import Trajectory
from trajcenter.exporter.excel_exporter import ExcelExporter
from trajcenter.exporter.options import ExportOptions
from trajcenter.exporter.tabular_exporter import _TRAJ_COL_ORDER


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _exporter(options: ExportOptions | None = None) -> ExcelExporter:
    """Instantiate an ``ExcelExporter`` with optional options.

    Args:
        options: Export options. Uses defaults when ``None``.

    Returns:
        A configured :class:`~trajcenter.exporter.excel_exporter.ExcelExporter`.
    """
    return ExcelExporter(options)


# ---------------------------------------------------------------------------
# _build_traj_df
# ---------------------------------------------------------------------------


class TestBuildTrajDf:
    """Tests for the ``_build_traj_df`` method."""

    def test_tool_index_resolved_to_name(self, traj_basic: Trajectory) -> None:
        """``tool_index=0`` is resolved to the corresponding tool name."""
        df = _exporter()._build_traj_df(traj_basic)
        assert "tool" in df.columns
        assert (df["tool"] == "tool0").all()

    def test_wobj_index_resolved_to_name(self, traj_basic: Trajectory) -> None:
        """``wobj_index=0`` is resolved to the corresponding wobj name."""
        df = _exporter()._build_traj_df(traj_basic)
        assert "wobj" in df.columns
        assert (df["wobj"] == "wobj0").all()

    def test_tool_index_column_dropped(self, traj_basic: Trajectory) -> None:
        """The ``tool_index`` column is removed after resolution."""
        df = _exporter()._build_traj_df(traj_basic)
        assert "tool_index" not in df.columns

    def test_wobj_index_column_dropped(self, traj_basic: Trajectory) -> None:
        """The ``wobj_index`` column is removed after resolution."""
        df = _exporter()._build_traj_df(traj_basic)
        assert "wobj_index" not in df.columns

    def test_multi_tools_resolved_correctly(self, traj_multi_tools: Trajectory) -> None:
        """``tool_index 0`` → ``Tool_A``, ``tool_index 1`` → ``Tool_B``."""
        df = _exporter()._build_traj_df(traj_multi_tools)
        assert df["tool"].tolist() == ["Tool_A", "Tool_B"]

    def test_multi_wobjs_resolved_correctly(self, traj_multi_tools: Trajectory) -> None:
        """``wobj_index 0`` → ``Wobj_A``, ``wobj_index 1`` → ``Wobj_B``."""
        df = _exporter()._build_traj_df(traj_multi_tools)
        assert df["wobj"].tolist() == ["Wobj_A", "Wobj_B"]

    def test_float_precision_applied(self, traj_basic: Trajectory) -> None:
        """Float values are rounded according to ``float_precision``."""
        opts = ExportOptions(float_precision=2)
        df = _exporter(opts)._build_traj_df(traj_basic)
        for col in ["x", "y", "z", "q1", "q2", "q3", "q4"]:
            if col in df.columns:
                rounded = df[col].round(2)
                pd.testing.assert_series_equal(df[col], rounded, check_names=False)

    def test_column_order_respects_traj_col_order(self, traj_basic: Trajectory) -> None:
        """Known columns appear in the order defined by ``_TRAJ_COL_ORDER``."""
        df = _exporter()._build_traj_df(traj_basic)
        known_cols = [c for c in _TRAJ_COL_ORDER if c in df.columns]
        actual_leading = df.columns[: len(known_cols)].tolist()
        assert actual_leading == known_cols

    def test_index_reset(self, traj_basic: Trajectory) -> None:
        """The resulting DataFrame index starts at 0."""
        df = _exporter()._build_traj_df(traj_basic)
        assert df.index.tolist() == list(range(len(df)))

    def test_row_count_preserved(self, traj_basic: Trajectory) -> None:
        """The row count matches the source trajectory."""
        df = _exporter()._build_traj_df(traj_basic)
        assert len(df) == len(traj_basic.points)


# ---------------------------------------------------------------------------
# _build_tools_df
# ---------------------------------------------------------------------------


class TestBuildToolsDf:
    """Tests for the ``_build_tools_df`` method."""

    def test_single_tool(self, traj_basic: Trajectory) -> None:
        """A single-tool trajectory produces a one-row ``name`` DataFrame."""
        df = _exporter()._build_tools_df(traj_basic)
        assert list(df.columns) == ["name"]
        assert df["name"].tolist() == ["tool0"]

    def test_multi_tools(self, traj_multi_tools: Trajectory) -> None:
        """Multiple tools are all listed in the output DataFrame."""
        df = _exporter()._build_tools_df(traj_multi_tools)
        assert df["name"].tolist() == ["Tool_A", "Tool_B"]

    def test_order_preserved(self, traj_multi_tools: Trajectory) -> None:
        """The tool order from the source list is preserved."""
        df = _exporter()._build_tools_df(traj_multi_tools)
        assert df["name"].tolist() == traj_multi_tools.tools


# ---------------------------------------------------------------------------
# _build_wobjs_df
# ---------------------------------------------------------------------------


class TestBuildWobjsDf:
    """Tests for the ``_build_wobjs_df`` method."""

    def test_single_wobj(self, traj_basic: Trajectory) -> None:
        """A single-wobj trajectory produces a one-row ``name`` DataFrame."""
        df = _exporter()._build_wobjs_df(traj_basic)
        assert list(df.columns) == ["name"]
        assert df["name"].tolist() == ["wobj0"]

    def test_multi_wobjs(self, traj_multi_tools: Trajectory) -> None:
        """Multiple wobjs are all listed in the output DataFrame."""
        df = _exporter()._build_wobjs_df(traj_multi_tools)
        assert df["name"].tolist() == ["Wobj_A", "Wobj_B"]


# ---------------------------------------------------------------------------
# _build_meta_df
# ---------------------------------------------------------------------------


class TestBuildMetaDf:
    """Tests for the ``_build_meta_df`` method."""

    def test_name_present(self, traj_with_meta: Trajectory) -> None:
        """The trajectory ``name`` is present in the meta DataFrame."""
        df = _exporter()._build_meta_df(traj_with_meta)
        assert "name" in df["key"].values

    def test_robot_model_present(self, traj_with_meta: Trajectory) -> None:
        """The ``robot_model`` key is present in the meta DataFrame."""
        df = _exporter()._build_meta_df(traj_with_meta)
        assert "robot_model" in df["key"].values

    def test_robot_model_value(self, traj_with_meta: Trajectory) -> None:
        """The ``robot_model`` value is correctly written."""
        df = _exporter()._build_meta_df(traj_with_meta)
        row = df[df["key"] == "robot_model"]
        assert row["value"].iloc[0] == "IRB6700-205/2.80"

    def test_extra_fields_present(self, traj_with_meta: Trajectory) -> None:
        """``extra{}`` fields are expanded as individual key/value entries."""
        df = _exporter()._build_meta_df(traj_with_meta)
        assert "author" in df["key"].values
        assert "project" in df["key"].values

    def test_extra_author_value(self, traj_with_meta: Trajectory) -> None:
        """The ``author`` extra field value is correctly written."""
        df = _exporter()._build_meta_df(traj_with_meta)
        row = df[df["key"] == "author"]
        assert row["value"].iloc[0] == "Jean Dupont"

    def test_columns_are_key_value(self, traj_basic: Trajectory) -> None:
        """The meta DataFrame has exactly ``key`` and ``value`` columns."""
        df = _exporter()._build_meta_df(traj_basic)
        assert list(df.columns) == ["key", "value"]

    def test_point_count_excluded(self, traj_basic: Trajectory) -> None:
        """``point_count`` is in ``_META_SKIP_FIELDS`` and must not appear."""
        df = _exporter()._build_meta_df(traj_basic)
        assert "point_count" not in df["key"].values

    def test_autocompleted_excluded(self, traj_basic: Trajectory) -> None:
        """``autocompleted`` is in ``_META_SKIP_FIELDS`` and must not appear."""
        df = _exporter()._build_meta_df(traj_basic)
        assert "autocompleted" not in df["key"].values

    def test_none_fields_excluded(self, traj_basic: Trajectory) -> None:
        """Fields with ``None`` value (e.g. absent ``robot_model``) must not appear."""
        df = _exporter()._build_meta_df(traj_basic)
        assert "robot_model" not in df["key"].values
