#!/usr/bin/env python3
# tests/converter/test_base_converter.py
"""Unit tests for converter defaults and explicit base autocompletion.

Author: Clement RACINET
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
from pydantic import ValidationError

from trajcenter.converter.base import BaseConverter
from trajcenter.converter.defaults import ConversionDefaults
from trajcenter.core.trajectory import Trajectory, TrajectoryMeta


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

    def test_default_values_disable_optional_autocomplete(self) -> None:
        """Default values do not request optional autocompletion."""
        defaults = ConversionDefaults()

        assert defaults.autocomplete_columns == set()
        assert defaults.cf_value == 0
        assert defaults.move_type is None
        assert defaults.readconfs is None
        assert defaults.tcp_speed is None
        assert defaults.zone_type is None
        assert defaults.tool_name is None
        assert defaults.wobj_name is None

    def test_custom_values_are_stored_without_requesting_autocomplete(self) -> None:
        """Default values can be stored without enabling autocompletion."""
        defaults = ConversionDefaults(
            move_type="MoveJ",
            cf_value=-1,
            readconfs=True,
            tcp_speed=500.0,
            zone_type=10,
            tool_name="Tool_formage",
            wobj_name="Wobj_SerreFlan",
        )

        assert defaults.autocomplete_columns == set()
        assert defaults.move_type == "MoveJ"
        assert defaults.cf_value == -1
        assert defaults.readconfs is True
        assert defaults.tcp_speed == pytest.approx(500.0)
        assert defaults.zone_type == 10
        assert defaults.tool_name == "Tool_formage"
        assert defaults.wobj_name == "Wobj_SerreFlan"

    def test_explicit_autocomplete_columns_are_stored(self) -> None:
        """Explicit autocompletion columns are accepted."""
        defaults = ConversionDefaults(
            autocomplete_columns={"tcp_speed", "zone_type"},
            tcp_speed=500.0,
            zone_type=10,
        )

        assert defaults.autocomplete_columns == {"tcp_speed", "zone_type"}

    def test_invalid_autocomplete_column_raises(self) -> None:
        """Unsupported autocompletion columns are rejected."""
        with pytest.raises(ValidationError):
            ConversionDefaults(autocomplete_columns={"eax_a"})


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

    def test_no_column_added_by_default(self) -> None:
        """No optional column is added without explicit request."""
        converter = self._make_converter()
        df_out, autocompleted = converter._autocomplete(self._minimal_df())

        assert list(df_out.columns) == ["x", "y", "z", "q1", "q2", "q3", "q4"]
        assert autocompleted == []

    def test_existing_columns_not_overwritten(self) -> None:
        """Existing columns are not overwritten, even when requested."""
        converter = self._make_converter(
            ConversionDefaults(
                autocomplete_columns={"tcp_speed", "tool_name"},
                tcp_speed=500.0,
                tool_name="Tool_A",
            )
        )
        df = self._minimal_df()
        df["tcp_speed"] = 999.0
        df["tool_name"] = "Tool_Source"

        df_out, autocompleted = converter._autocomplete(df)

        assert df_out["tcp_speed"].iloc[0] == pytest.approx(999.0)
        assert df_out["tool_name"].iloc[0] == "Tool_Source"
        assert "tcp_speed" not in autocompleted
        assert "tool_name" not in autocompleted

    def test_explicit_confdata_autocompleted_as_int8_nullable(self) -> None:
        """Requested confdata columns use nullable Int8 dtype."""
        converter = self._make_converter(
            ConversionDefaults(
                autocomplete_columns={"cf1", "cf4", "cf6", "cfx"},
                cf_value=0,
            )
        )
        df_out, autocompleted = converter._autocomplete(self._minimal_df())

        for col in ["cf1", "cf4", "cf6", "cfx"]:
            assert col in df_out.columns
            assert col in autocompleted
            assert df_out[col].dtype == pd.Int8Dtype()
            assert int(df_out[col].iloc[0]) == 0

    def test_explicit_move_type_added(self) -> None:
        """move_type is added only when explicitly requested."""
        converter = self._make_converter(
            ConversionDefaults(
                autocomplete_columns={"move_type"},
                move_type="MoveL",
            )
        )
        df_out, autocompleted = converter._autocomplete(self._minimal_df())

        assert df_out["move_type"].iloc[0] == "MoveL"
        assert "move_type" in autocompleted

    def test_requested_move_type_without_value_raises(self) -> None:
        """Requesting move_type without a value raises ValueError."""
        converter = self._make_converter(
            ConversionDefaults(autocomplete_columns={"move_type"})
        )

        with pytest.raises(ValueError, match="move_type"):
            converter._autocomplete(self._minimal_df())

    def test_explicit_tcp_speed_added(self) -> None:
        """tcp_speed is added only when explicitly requested."""
        converter = self._make_converter(
            ConversionDefaults(
                autocomplete_columns={"tcp_speed"},
                tcp_speed=500.0,
            )
        )
        df_out, autocompleted = converter._autocomplete(self._minimal_df())

        assert df_out["tcp_speed"].iloc[0] == pytest.approx(500.0)
        assert df_out["tcp_speed"].dtype == "float64"
        assert "tcp_speed" in autocompleted

    def test_explicit_zone_type_added(self) -> None:
        """zone_type is added only when explicitly requested."""
        converter = self._make_converter(
            ConversionDefaults(
                autocomplete_columns={"zone_type"},
                zone_type=10,
            )
        )
        df_out, autocompleted = converter._autocomplete(self._minimal_df())

        assert df_out["zone_type"].iloc[0] == 10
        assert df_out["zone_type"].dtype == pd.Int16Dtype()
        assert "zone_type" in autocompleted

    def test_explicit_tool_and_wobj_added(self) -> None:
        """tool_name and wobj_name are added only when explicitly requested."""
        converter = self._make_converter(
            ConversionDefaults(
                autocomplete_columns={"tool_name", "wobj_name"},
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
        """readconfs is added only when explicitly requested."""
        converter = self._make_converter(
            ConversionDefaults(
                autocomplete_columns={"readconfs"},
                readconfs=True,
            )
        )
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
