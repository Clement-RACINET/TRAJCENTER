#!/usr/bin/env python3
# tests/test_base_converter.py
"""Unit tests for :mod:`trajcenter.converter.defaults` and
:meth:`~trajcenter.converter.base.BaseConverter._autocomplete`.

Author: Clement RACINET

``ModConverter`` is used as a concrete proxy to test ``_autocomplete``,
since ``BaseConverter`` is abstract.
"""

from __future__ import annotations

import pandas as pd

from trajcenter.converter.defaults import ConversionDefaults
from trajcenter.converter.mod_converter import ModConverter
from trajcenter.core.trajectory import CONVERTER_COLUMNS


# ---------------------------------------------------------------------------
# Tests — ConversionDefaults
# ---------------------------------------------------------------------------


class TestConversionDefaults:
    """Tests for the ConversionDefaults model."""

    def test_default_values(self) -> None:
        """Standard default values are correct."""
        d = ConversionDefaults()
        assert d.move_type == "MoveJ"
        assert d.speed == "v10"
        assert d.zone == "z10"
        assert d.tool == "tool0"
        assert d.wobj == "wobj0"
        assert d.cf_value == 0

    def test_custom_values(self) -> None:
        """Default values can be overridden."""
        d = ConversionDefaults(speed="v200", zone="fine", move_type="MoveJ")
        assert d.speed == "v200"
        assert d.zone == "fine"
        assert d.move_type == "MoveJ"


# ---------------------------------------------------------------------------
# Tests — BaseConverter._autocomplete
# ---------------------------------------------------------------------------


class TestAutocomplete:
    """Tests for BaseConverter._autocomplete (via ModConverter)."""

    def _make_converter(self) -> ModConverter:
        """Instantiate a ModConverter with default settings.

        Returns:
            A fresh ``ModConverter`` instance.
        """
        return ModConverter(defaults=ConversionDefaults())

    def _minimal_df(self) -> pd.DataFrame:
        """Build a minimal DataFrame with only XYZ and quaternion columns.

        Returns:
            A single-row DataFrame with x, y, z, q1, q2, q3, q4.
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
        """All CONVERTER_COLUMNS are present after autocompletion."""
        conv = self._make_converter()
        df_out, _ = conv._autocomplete(self._minimal_df(), [], [])
        for col in CONVERTER_COLUMNS:
            assert col in df_out.columns, f"Missing column: {col}"

    def test_autocompleted_lists_missing_columns(self) -> None:
        """``autocompleted`` contains exactly the columns that were added."""
        conv = self._make_converter()
        df = self._minimal_df()
        df["move_type"] = "MoveL"  # already present → must not appear in autocompleted
        _, autocompleted = conv._autocomplete(df, ["Tool_formage"], ["Wobj_SerreFlan"])
        assert "move_type" not in autocompleted
        assert "speed" in autocompleted
        assert "zone" in autocompleted

    def test_empty_tools_filled_with_default(self) -> None:
        """Empty tools/wobjs lists are filled with the default values."""
        conv = self._make_converter()
        tools: list[str] = []
        wobjs: list[str] = []
        conv._autocomplete(self._minimal_df(), tools, wobjs)
        assert tools == ["tool0"]
        assert wobjs == ["wobj0"]

    def test_existing_columns_not_overwritten(self) -> None:
        """Columns already present in the DataFrame are not overwritten."""
        conv = self._make_converter()
        df = self._minimal_df()
        df["speed"] = "v9999"
        df_out, _ = conv._autocomplete(df, ["Tool_formage"], ["Wobj_SerreFlan"])
        assert df_out["speed"].iloc[0] == "v9999"

    def test_confdata_autocompleted_as_int8_nullable(self) -> None:
        """Autocompleted confdata columns use nullable Int8 dtype."""
        conv = self._make_converter()
        df_out, _ = conv._autocomplete(self._minimal_df(), [], [])
        for col in ["cf1", "cf4", "cf6", "cfx"]:
            assert df_out[col].dtype == pd.Int8Dtype()
