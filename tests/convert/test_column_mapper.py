#!/usr/bin/env python3
# tests/convert/test_column_mapper.py
"""Unit tests for :mod:`trajcenter.convert.column_mapper`.

> **Author**: Clément RACINET
"""

from __future__ import annotations

import re
import warnings

import pandas as pd
import pytest

from trajcenter.convert.column_mapper import (
    _ALIAS_INDEX,
    COLUMN_ALIASES,
    _normalize,
    canonical_name,
    resolve_columns,
)


class TestNormalize:
    """Tests for the ``_normalize`` function."""

    def test_lowercase(self) -> None:
        """Uppercase letters are converted to lowercase."""
        assert _normalize("VITESSE") == "vitesse"

    def test_diacritics_removed(self) -> None:
        """Diacritics are stripped."""
        assert _normalize("Répère") == "repere"
        assert _normalize("précision") == "precision"

    def test_underscore_preserved(self) -> None:
        """Underscores are preserved."""
        assert _normalize("pos_x") == "pos_x"
        assert _normalize("eax_a") == "eax_a"

    def test_digits_preserved(self) -> None:
        """Digits are preserved."""
        assert _normalize("cf1") == "cf1"
        assert _normalize("eax3") == "eax3"

    def test_mixed(self) -> None:
        """Casing, accents and underscores are handled together."""
        assert _normalize("PosX") == "posx"
        assert _normalize("Trans_X") == "trans_x"


class TestCanonicalNameGeometry:
    """Tests for geometry aliases."""

    @pytest.mark.parametrize(
        ("alias", "expected"),
        [
            ("x", "x"),
            ("PosX", "x"),
            ("pos_x", "x"),
            ("POSITIONX", "x"),
            ("y", "y"),
            ("PosY", "y"),
            ("TransY", "y"),
            ("z", "z"),
            ("PosZ", "z"),
            ("position_z", "z"),
            ("q1", "q1"),
            ("QW", "q1"),
            ("quaternionw", "q1"),
            ("q2", "q2"),
            ("qi", "q2"),
            ("QX", "q2"),
            ("q3", "q3"),
            ("qj", "q3"),
            ("RotY", "q3"),
            ("q4", "q4"),
            ("qk", "q4"),
            ("ROTZ", "q4"),
        ],
    )
    def test_geometry_aliases(self, alias: str, expected: str) -> None:
        """Geometric aliases resolve to canonical names."""
        assert canonical_name(alias) == expected


class TestCanonicalNameConfdata:
    """Tests for ABB confdata aliases."""

    @pytest.mark.parametrize(
        ("alias", "expected"),
        [
            ("cf1", "cf1"),
            ("cf4", "cf4"),
            ("cf6", "cf6"),
            ("cfx", "cfx"),
            ("CF1", "cf1"),
            ("Cf4", "cf4"),
            ("CF6", "cf6"),
            ("CFX", "cfx"),
            ("confdata1", "cf1"),
            ("CONFDATA1", "cf1"),
            ("conf1", "cf1"),
            ("config1", "cf1"),
            ("configdata1", "cf1"),
            ("confdata4", "cf4"),
            ("conf4", "cf4"),
            ("config4", "cf4"),
            ("confdata6", "cf6"),
            ("conf6", "cf6"),
            ("config6", "cf6"),
            ("confdatax", "cfx"),
            ("confx", "cfx"),
            ("configx", "cfx"),
            ("configdatax", "cfx"),
        ],
    )
    def test_confdata_aliases(self, alias: str, expected: str) -> None:
        """Confdata aliases resolve to canonical names."""
        assert canonical_name(alias) == expected

    def test_confdata_not_in_unresolved_after_export(self) -> None:
        """cf* columns do not fall into unresolved."""
        df = pd.DataFrame(
            {
                "x": [100.0],
                "y": [200.0],
                "z": [300.0],
                "q1": [1.0],
                "q2": [0.0],
                "q3": [0.0],
                "q4": [0.0],
                "cf1": [0],
                "cf4": [0],
                "cf6": [0],
                "cfx": [0],
                "move_type": ["MoveL"],
                "tcp_speed": [500.0],
                "zone_type": [10],
                "tool_name": ["tool0"],
                "wobj_name": ["wobj0"],
            }
        )
        with warnings.catch_warnings():
            warnings.simplefilter("error", UserWarning)
            _, unresolved = resolve_columns(df)

        assert "cf1" not in unresolved
        assert "cf4" not in unresolved
        assert "cf6" not in unresolved
        assert "cfx" not in unresolved


class TestCanonicalNameExternalAxes:
    """Tests for external axis aliases."""

    @pytest.mark.parametrize(
        ("alias", "expected"),
        [
            ("eax_a", "eax_a"),
            ("eaxa", "eax_a"),
            ("eax1", "eax_a"),
            ("EAX_A", "eax_a"),
            ("eax_b", "eax_b"),
            ("eaxb", "eax_b"),
            ("eax2", "eax_b"),
            ("eax_f", "eax_f"),
            ("eaxf", "eax_f"),
            ("eax6", "eax_f"),
        ],
    )
    def test_eax_aliases(self, alias: str, expected: str) -> None:
        """External axis aliases resolve to canonical names."""
        assert canonical_name(alias) == expected


class TestCanonicalNameMovement:
    """Tests for movement and send metadata aliases."""

    @pytest.mark.parametrize(
        ("alias", "expected"),
        [
            ("move_type", "move_type"),
            ("movetype", "move_type"),
            ("MOUVEMENT", "move_type"),
            ("speed", "tcp_speed"),
            ("tcp_speed", "tcp_speed"),
            ("VITESSE", "tcp_speed"),
            ("feedrate", "tcp_speed"),
            ("zone", "zone_type"),
            ("zone_type", "zone_type"),
            ("PRECISION", "zone_type"),
            ("blend", "zone_type"),
            ("tool", "tool_name"),
            ("OUTIL", "tool_name"),
            ("tool_name", "tool_name"),
            ("wobj", "wobj_name"),
            ("wobj_name", "wobj_name"),
            ("workobject", "wobj_name"),
            ("REPÈRE", "wobj_name"),
            ("readconfs", "readconfs"),
            ("readconf", "readconfs"),
            ("process_param_index", "process_param_index"),
            ("process_index", "process_param_index"),
        ],
    )
    def test_movement_aliases(self, alias: str, expected: str) -> None:
        """Movement and metadata aliases resolve to canonical names."""
        assert canonical_name(alias) == expected


class TestCanonicalNameUnknown:
    """Tests for unrecognised columns."""

    @pytest.mark.parametrize(
        "col",
        [
            "foobar",
            "unknown_col",
            "cf2",
            "cf3",
            "cf5",
            "eax_g",
            "eax_z",
            "q5",
            "q0",
        ],
    )
    def test_unknown_returns_none(self, col: str) -> None:
        """An unrecognised column name returns ``None``."""
        assert canonical_name(col) is None


class TestResolveColumns:
    """Tests for ``resolve_columns``."""

    def test_rename_known_columns(self) -> None:
        """Known columns are renamed to canonical form."""
        df = pd.DataFrame({"PosX": [1.0], "PosY": [2.0], "PosZ": [3.0]})
        result, unresolved = resolve_columns(df)

        assert "x" in result.columns
        assert "y" in result.columns
        assert "z" in result.columns
        assert unresolved == []

    def test_rename_v1_aliases_to_v2_names(self) -> None:
        """Legacy v1 aliases resolve to v2 canonical names."""
        df = pd.DataFrame(
            {
                "speed": ["v500"],
                "zone": ["z10"],
                "tool": ["Tool_A"],
                "wobj": ["Wobj_A"],
            }
        )
        result, unresolved = resolve_columns(df)

        assert "tcp_speed" in result.columns
        assert "zone_type" in result.columns
        assert "tool_name" in result.columns
        assert "wobj_name" in result.columns
        assert unresolved == []

    def test_unknown_columns_in_unresolved(self) -> None:
        """Unknown columns are returned in unresolved."""
        df = pd.DataFrame({"x": [1.0], "custom_col": [42]})
        result, unresolved = resolve_columns(df)

        assert "custom_col" in unresolved
        assert "x" in result.columns

    def test_confdata_columns_resolved(self) -> None:
        """Confdata columns are resolved without warning."""
        df = pd.DataFrame({"cf1": [0], "cf4": [1], "cf6": [-1], "cfx": [0]})
        with warnings.catch_warnings():
            warnings.simplefilter("error", UserWarning)
            result, unresolved = resolve_columns(df)

        assert unresolved == []
        for col in ["cf1", "cf4", "cf6", "cfx"]:
            assert col in result.columns

    def test_confdata_alias_resolved(self) -> None:
        """Long confdata aliases are renamed to canonical form."""
        df = pd.DataFrame(
            {
                "confdata1": [0],
                "confdata4": [1],
                "confdata6": [-1],
                "confdatax": [0],
            }
        )
        result, unresolved = resolve_columns(df)

        assert unresolved == []
        assert "cf1" in result.columns
        assert "cf4" in result.columns
        assert "cf6" in result.columns
        assert "cfx" in result.columns

    def test_duplicate_canonical_emits_warning(self) -> None:
        """Duplicate canonical aliases emit a warning."""
        df = pd.DataFrame(columns=["x", "PosX"])
        with pytest.warns(UserWarning, match=re.escape("PosX")):
            resolve_columns(df)

    def test_no_columns_unchanged(self) -> None:
        """A DataFrame with no recognised columns is returned unchanged."""
        df = pd.DataFrame({"foo": [1], "bar": [2]})
        result, unresolved = resolve_columns(df)

        assert list(result.columns) == ["foo", "bar"]
        assert unresolved == ["foo", "bar"]

    def test_empty_dataframe(self) -> None:
        """An empty DataFrame is handled without error."""
        df = pd.DataFrame()
        result, unresolved = resolve_columns(df)

        assert result.empty
        assert unresolved == []

    def test_alias_index_completeness(self) -> None:
        """Every alias in COLUMN_ALIASES is present in _ALIAS_INDEX."""
        for canonical, aliases in COLUMN_ALIASES.items():
            for alias in aliases:
                norm = _normalize(alias)
                assert norm in _ALIAS_INDEX, (
                    f"Alias {alias!r} normalised as {norm!r} missing "
                    f"from _ALIAS_INDEX for canonical {canonical!r}"
                )
                assert _ALIAS_INDEX[norm] == canonical
