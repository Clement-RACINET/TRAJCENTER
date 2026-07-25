#!/usr/bin/env python3
# tests/exporter/test_tabular_exporter.py
"""Unit tests for tabular exporter DataFrame construction.

> **Author**: Clément RACINET
"""

from __future__ import annotations

import pytest

from trajcenter.core.trajectory import Trajectory
from trajcenter.exporter.excel_exporter import ExcelExporter
from trajcenter.exporter.options import ExportOptions
from trajcenter.exporter.tabular_exporter import _DEFAULT_TRAJ_COL_ORDER


def _exporter(options: ExportOptions | None = None) -> ExcelExporter:
    """Instantiate an Excel exporter for testing.

    ABB Route:
        N/A — test helper.

    ABB Constraints:
        No ABB controller access.

    Args:
        options: Optional export options.

    Returns:
        Configured Excel exporter.

    Example:
        ::

            exporter = _exporter()
    """
    return ExcelExporter(options)


class TestBuildTrajDf:
    """Tests for ``_build_traj_df``."""

    def test_known_columns_exported(self, traj_basic: Trajectory) -> None:
        """Known v2 columns are exported by default."""
        df = _exporter()._build_traj_df(traj_basic)
        assert "x" in df.columns
        assert "tcp_speed" in df.columns
        assert "zone_type" in df.columns
        assert "tool_name" in df.columns
        assert "wobj_name" in df.columns

    def test_legacy_columns_not_created(self, traj_basic: Trajectory) -> None:
        """Legacy v1 columns are not created during export."""
        df = _exporter()._build_traj_df(traj_basic)
        assert "speed" not in df.columns
        assert "zone" not in df.columns
        assert "tool_index" not in df.columns
        assert "wobj_index" not in df.columns

    def test_tcp_speed_kept_numeric(self, traj_basic: Trajectory) -> None:
        """tcp_speed is exported as a numeric value, without RAPID v prefix."""
        df = _exporter()._build_traj_df(traj_basic)
        assert df["tcp_speed"].tolist() == [500.0, 250.5, 500.0]

    def test_zone_type_kept_numeric(self, traj_basic: Trajectory) -> None:
        """zone_type is exported as a numeric code."""
        df = _exporter()._build_traj_df(traj_basic)
        assert df["zone_type"].tolist() == [10, 5, 255]

    def test_column_order_respects_default_order(self, traj_basic: Trajectory) -> None:
        """Default known columns follow the preferred v2 order."""
        df = _exporter()._build_traj_df(traj_basic)
        expected = [col for col in _DEFAULT_TRAJ_COL_ORDER if col in df.columns]
        assert df.columns.tolist() == expected

    def test_minimal_trajectory_no_optional_columns(
        self,
        traj_minimal: Trajectory,
    ) -> None:
        """Optional columns are not invented during export."""
        df = _exporter()._build_traj_df(traj_minimal)
        assert df.columns.tolist() == ["x", "y", "z", "q1", "q2", "q3", "q4"]

    def test_float_precision_applied(self, traj_basic: Trajectory) -> None:
        """Float values are rounded according to the configured precision."""
        traj_basic.points.loc[0, "x"] = 1.23456789
        df = _exporter(ExportOptions(float_precision=2))._build_traj_df(traj_basic)
        assert df["x"].iloc[0] == pytest.approx(1.23)

    def test_export_columns_star_exports_all(
        self,
        traj_with_unknown_column: Trajectory,
    ) -> None:
        """export_columns=('*',) exports all columns present in points."""
        opts = ExportOptions(export_columns=("*",))
        df = _exporter(opts)._build_traj_df(traj_with_unknown_column)
        assert "operator_comment" in df.columns

    def test_unknown_columns_warned_and_not_exported_by_default(
        self,
        traj_with_unknown_column: Trajectory,
    ) -> None:
        """Unknown point columns are warned and omitted by default."""
        with pytest.warns(UserWarning, match="operator_comment|not part"):
            df = _exporter()._build_traj_df(traj_with_unknown_column)
        assert "operator_comment" not in df.columns

    def test_export_columns_default_plus_extra(
        self,
        traj_with_unknown_column: Trajectory,
    ) -> None:
        """('default', column) exports default columns plus the requested column."""
        opts = ExportOptions(export_columns=("default", "operator_comment"))
        df = _exporter(opts)._build_traj_df(traj_with_unknown_column)
        assert "operator_comment" in df.columns

    def test_export_columns_exact_subset(self, traj_basic: Trajectory) -> None:
        """A custom tuple exports exactly the requested present columns."""
        opts = ExportOptions(export_columns=("x", "y", "tcp_speed"))
        df = _exporter(opts)._build_traj_df(traj_basic)
        assert df.columns.tolist() == ["x", "y", "tcp_speed"]

    def test_missing_requested_column_warns(self, traj_basic: Trajectory) -> None:
        """A requested absent column emits a warning and is ignored."""
        opts = ExportOptions(export_columns=("x", "missing_col"))
        with pytest.warns(UserWarning, match="missing_col"):
            df = _exporter(opts)._build_traj_df(traj_basic)
        assert df.columns.tolist() == ["x"]

    def test_index_reset(self, traj_basic: Trajectory) -> None:
        """The exported DataFrame index starts at zero."""
        df = _exporter()._build_traj_df(traj_basic)
        assert df.index.tolist() == list(range(len(df)))


class TestBuildMetaDf:
    """Tests for ``_build_meta_df``."""

    def test_columns_are_key_value(self, traj_basic: Trajectory) -> None:
        """The metadata DataFrame has key and value columns."""
        df = _exporter()._build_meta_df(traj_basic)
        assert list(df.columns) == ["key", "value"]

    def test_name_present(self, traj_with_meta: Trajectory) -> None:
        """The trajectory name is present in metadata."""
        df = _exporter()._build_meta_df(traj_with_meta)
        assert "name" in df["key"].values

    def test_robot_model_present(self, traj_with_meta: Trajectory) -> None:
        """The robot model is present when defined."""
        df = _exporter()._build_meta_df(traj_with_meta)
        assert "robot_model" in df["key"].values

    def test_extra_fields_present(self, traj_with_meta: Trajectory) -> None:
        """Extra metadata fields are expanded as key/value rows."""
        df = _exporter()._build_meta_df(traj_with_meta)
        assert "author" in df["key"].values
        assert "project" in df["key"].values

    def test_point_count_excluded(self, traj_basic: Trajectory) -> None:
        """point_count is not exported as explicit metadata."""
        df = _exporter()._build_meta_df(traj_basic)
        assert "point_count" not in df["key"].values

    def test_autocompleted_excluded(self, traj_basic: Trajectory) -> None:
        """autocompleted is not exported as explicit metadata."""
        df = _exporter()._build_meta_df(traj_basic)
        assert "autocompleted" not in df["key"].values
