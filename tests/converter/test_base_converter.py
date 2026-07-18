#!/usr/bin/env python3
# tests/converter/test_base_converter.py
"""Unit tests for converter defaults and base autocompletion.

Author: Clement RACINET
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from trajcenter.converter.base import BaseConverter
from trajcenter.converter.defaults import ConversionDefaults
from trajcenter.core.trajectory import CONVERTER_COLUMNS, Trajectory, TrajectoryMeta


class DummyConverter(BaseConverter):
    """Concrete converter used to test ``BaseConverter``."""

    def convert(self, source: Path) -> Trajectory:
        """Build a minimal trajectory from a dummy source path.

        ABB Route:
            N/A — test-only local converter.

        ABB Constraints:
            No ABB controller access.

        Args:
            source: Dummy source path.

        Returns:
            Minimal valid trajectory.

        Raises:
            FileNotFoundError: If the source does not exist.

        Example:
            ::

                traj = DummyConverter().convert(Path("source.csv"))
        """
        if not source.exists():
            raise FileNotFoundError(source)
        points = pd.DataFrame(
            {
                "x": [1.0],
                "y": [2.0],
                "z": [3.0],
                "q1": [1.0],
                "q2": [0.0],
                "q3": [0.0],
                "q4": [0.0],
            }
        )
        points, autocompleted = self._autocomplete(points)
        return Trajectory(
            meta=TrajectoryMeta(
                name=source.stem,
                autocompleted=autocompleted,
            ),
            points=points,
        )


class TestConversionDefaults:
    """Tests for the ``ConversionDefaults`` model."""

    def test_default_values(self) -> None:
        """Standard default values are correct."""
        defaults = ConversionDefaults()
        assert defaults.move_type == "MoveL"
        assert defaults.cf_value == 0
        assert defaults.readconfs is None
        assert defaults.tcp_speed is None
        assert defaults.zone_type is None
        assert defaults.tool_name is None
        assert defaults.wobj_name is None

    def test_custom_values(self) -> None:
        """Default values can be overridden."""
        defaults = ConversionDefaults(
            move_type="MoveJ",
            cf_value=-1,
            readconfs=True,
            tcp_speed=500.0,
            zone_type=10,
            tool_name="Tool_formage",
            wobj_name="Wobj_SerreFlan",
        )
        assert defaults.move_type == "MoveJ"
        assert defaults.cf_value == -1
        assert defaults.readconfs is True
        assert defaults.tcp_speed == pytest.approx(500.0)
        assert defaults.zone_type == 10
        assert defaults.tool_name == "Tool_formage"
        assert defaults.wobj_name == "Wobj_SerreFlan"

    def test_move_type_can_be_disabled(self) -> None:
        """move_type autocompletion can be disabled with None."""
        defaults = ConversionDefaults(move_type=None)
        assert defaults.move_type is None


class TestAutocomplete:
    """Tests for ``BaseConverter._autocomplete``."""

    def _make_converter(
        self,
        defaults: ConversionDefaults | None = None,
    ) -> DummyConverter:
        """Instantiate a concrete dummy converter.

        Args:
            defaults: Optional conversion defaults.

        Returns:
            A fresh dummy converter.
        """
        return DummyConverter(defaults=defaults)

    def _minimal_df(self) -> pd.DataFrame:
        """Build a minimal geometry-only DataFrame.

        Returns:
            A single-row DataFrame with mandatory trajectory columns.
        """
        return pd.DataFrame(
            {
                "x": [1.0],
                "y": [2.0],
                "z": [3.0],
                "q1": [1.0],
                "q2": [0.0],
                "q3": [0.0],
                "q4": [0.0],
            }
        )

    def test_all_converter_columns_present_after_autocomplete(self) -> None:
        """All converter-safe columns are present after autocompletion."""
        converter = self._make_converter()
        df_out, _ = converter._autocomplete(self._minimal_df())
        for col in CONVERTER_COLUMNS:
            assert col in df_out.columns

    def test_default_does_not_add_cell_specific_columns(self) -> None:
        """Default autocompletion does not invent send metadata."""
        converter = self._make_converter()
        df_out, _ = converter._autocomplete(self._minimal_df())
        assert "tcp_speed" not in df_out.columns
        assert "zone_type" not in df_out.columns
        assert "tool_name" not in df_out.columns
        assert "wobj_name" not in df_out.columns
        assert "readconfs" not in df_out.columns
        assert "process_param_index" not in df_out.columns

    def test_autocompleted_lists_missing_columns(self) -> None:
        """autocompleted contains exactly columns added by the method."""
        converter = self._make_converter()
        df = self._minimal_df()
        df["move_type"] = "MoveJ"

        _, autocompleted = converter._autocomplete(df)

        assert "move_type" not in autocompleted
        for col in ["cf1", "cf4", "cf6", "cfx"]:
            assert col in autocompleted

    def test_existing_columns_not_overwritten(self) -> None:
        """Existing columns are not overwritten."""
        converter = self._make_converter(
            ConversionDefaults(tcp_speed=500.0, tool_name="Tool_A")
        )
        df = self._minimal_df()
        df["tcp_speed"] = 999.0
        df["tool_name"] = "Tool_Source"

        df_out, autocompleted = converter._autocomplete(df)

        assert df_out["tcp_speed"].iloc[0] == pytest.approx(999.0)
        assert df_out["tool_name"].iloc[0] == "Tool_Source"
        assert "tcp_speed" not in autocompleted
        assert "tool_name" not in autocompleted

    def test_confdata_autocompleted_as_int8_nullable(self) -> None:
        """Autocompleted confdata columns use nullable Int8 dtype."""
        converter = self._make_converter()
        df_out, _ = converter._autocomplete(self._minimal_df())

        for col in ["cf1", "cf4", "cf6", "cfx"]:
            assert df_out[col].dtype == pd.Int8Dtype()

    def test_move_type_added_by_default(self) -> None:
        """move_type is added by default."""
        converter = self._make_converter()
        df_out, autocompleted = converter._autocomplete(self._minimal_df())

        assert df_out["move_type"].iloc[0] == "MoveL"
        assert "move_type" in autocompleted

    def test_move_type_not_added_when_disabled(self) -> None:
        """move_type is not added when default is None."""
        converter = self._make_converter(ConversionDefaults(move_type=None))
        df_out, autocompleted = converter._autocomplete(self._minimal_df())

        assert "move_type" not in df_out.columns
        assert "move_type" not in autocompleted

    def test_explicit_tcp_speed_added(self) -> None:
        """tcp_speed is added only when explicitly configured."""
        converter = self._make_converter(ConversionDefaults(tcp_speed=500.0))
        df_out, autocompleted = converter._autocomplete(self._minimal_df())

        assert df_out["tcp_speed"].iloc[0] == pytest.approx(500.0)
        assert df_out["tcp_speed"].dtype == "float64"
        assert "tcp_speed" in autocompleted

    def test_explicit_zone_type_added(self) -> None:
        """zone_type is added only when explicitly configured."""
        converter = self._make_converter(ConversionDefaults(zone_type=10))
        df_out, autocompleted = converter._autocomplete(self._minimal_df())

        assert df_out["zone_type"].iloc[0] == 10
        assert df_out["zone_type"].dtype == pd.Int16Dtype()
        assert "zone_type" in autocompleted

    def test_explicit_tool_and_wobj_added(self) -> None:
        """tool_name and wobj_name are added only when explicitly configured."""
        converter = self._make_converter(
            ConversionDefaults(
                tool_name="Tool_formage",
                wobj_name="Wobj_SerreFlan",
            )
        )
        df_out, autocompleted = converter._autocomplete(self._minimal_df())

        assert df_out["tool_name"].iloc[0] == "Tool_formage"
        assert df_out["wobj_name"].iloc[0] == "Wobj_SerreFlan"
        assert "tool_name" in autocompleted
        assert "wobj_name" in autocompleted

    def test_explicit_readconfs_added(self) -> None:
        """readconfs is added only when explicitly configured."""
        converter = self._make_converter(ConversionDefaults(readconfs=True))
        df_out, autocompleted = converter._autocomplete(self._minimal_df())

        assert bool(df_out["readconfs"].iloc[0]) is True
        assert str(df_out["readconfs"].dtype) == "boolean"
        assert "readconfs" in autocompleted

    def test_convert_and_save(self, tmp_path: Path) -> None:
        """convert_and_save saves the produced trajectory archive."""
        source = tmp_path / "source.csv"
        source.write_text("dummy", encoding="utf-8")

        dest = self._make_converter().convert_and_save(
            source=source,
            dest_dir=tmp_path / "out",
        )

        assert dest.exists()
        assert dest.name == "source.trajcenter"
