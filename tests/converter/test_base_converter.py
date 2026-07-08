# tests/test_base_converter.py

"""
Tests unitaires pour :mod:`trajcenter.converter.defaults`
et :meth:`~trajcenter.converter.base.BaseConverter._autocomplete`.

ModConverter est utilisé comme proxy concret pour tester _autocomplete,
car BaseConverter est abstrait.
"""

from __future__ import annotations

import pandas as pd
import pytest

from trajcenter.converter.defaults import ConversionDefaults
from trajcenter.converter.mod_converter import ModConverter
from trajcenter.core.trajectory import CONVERTER_COLUMNS


# ---------------------------------------------------------------------------
# Tests — ConversionDefaults
# ---------------------------------------------------------------------------


class TestConversionDefaults:
    """Tests du modèle ConversionDefaults."""

    def test_default_values(self) -> None:
        """Les valeurs par défaut standard sont correctes."""
        d = ConversionDefaults()
        assert d.move_type == "MoveJ"
        assert d.speed == "v10"
        assert d.zone == "z10"
        assert d.tool == "tool0"
        assert d.wobj == "wobj0"
        assert d.cf_value == 0

    def test_custom_values(self) -> None:
        """Les valeurs peuvent être surchargées."""
        d = ConversionDefaults(speed="v200", zone="fine", move_type="MoveJ")
        assert d.speed == "v200"
        assert d.zone == "fine"
        assert d.move_type == "MoveJ"


# ---------------------------------------------------------------------------
# Tests — BaseConverter._autocomplete
# ---------------------------------------------------------------------------


class TestAutocomplete:
    """Tests de la méthode _autocomplete de BaseConverter (via ModConverter)."""

    def _make_converter(self) -> ModConverter:
        return ModConverter(defaults=ConversionDefaults())

    def _minimal_df(self) -> pd.DataFrame:
        return pd.DataFrame({
            "x": [1.0], "y": [2.0], "z": [3.0],
            "q1": [1.0], "q2": [0.0], "q3": [0.0], "q4": [0.0],
        })

    def test_all_converter_columns_present_after_autocomplete(self) -> None:
        """Toutes les CONVERTER_COLUMNS sont présentes après autocomplétion."""
        conv = self._make_converter()
        df_out, _ = conv._autocomplete(self._minimal_df(), [], [])
        for col in CONVERTER_COLUMNS:
            assert col in df_out.columns, f"Colonne manquante : {col}"

    def test_autocompleted_lists_missing_columns(self) -> None:
        """autocompleted contient exactement les colonnes ajoutées."""
        conv = self._make_converter()
        df = self._minimal_df()
        df["move_type"] = "MoveL"  # déjà présente → ne doit pas apparaître
        _, autocompleted = conv._autocomplete(df, ["Tool_formage"], ["Wobj_SerreFlan"])
        assert "move_type" not in autocompleted
        assert "speed" in autocompleted
        assert "zone" in autocompleted

    def test_empty_tools_filled_with_default(self) -> None:
        """Une liste tools/wobjs vide est complétée avec les defaults."""
        conv = self._make_converter()
        tools: list[str] = []
        wobjs: list[str] = []
        conv._autocomplete(self._minimal_df(), tools, wobjs)
        assert tools == ["tool0"]
        assert wobjs == ["wobj0"]

    def test_existing_columns_not_overwritten(self) -> None:
        """Les colonnes déjà présentes ne sont pas écrasées."""
        conv = self._make_converter()
        df = self._minimal_df()
        df["speed"] = "v9999"
        df_out, _ = conv._autocomplete(df, ["Tool_formage"], ["Wobj_SerreFlan"])
        assert df_out["speed"].iloc[0] == "v9999"

    def test_confdata_autocompleted_as_int8_nullable(self) -> None:
        """Les colonnes confdata autocomplétées sont en Int8 nullable."""
        conv = self._make_converter()
        df_out, _ = conv._autocomplete(self._minimal_df(), [], [])
        for col in ["cf1", "cf4", "cf6", "cfx"]:
            assert df_out[col].dtype == pd.Int8Dtype()
