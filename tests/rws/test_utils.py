#!/usr/bin/env python3
# tests/rws/test_utils.py
"""Tests for :mod:`trajcenter.rws._utils`.

> **Author**: Clément RACINET
"""

from __future__ import annotations

import pytest

from trajcenter.rws._utils import (
    symbol,
    symbol_array_element,
    symbol_record_array_field,
)


class TestSymbol:
    """Tests for the :func:`~trajcenter.rws._utils.symbol` helper."""

    def test_simple_variable(self) -> None:
        """A simple variable name produces the correct ``RAPID/`` URL."""
        assert (
            symbol("T_ROB1", "TRAJCENTER_WebServices", "trajReady")
            == "RAPID/T_ROB1/TRAJCENTER_WebServices/trajReady"
        )

    def test_custom_task(self) -> None:
        """A custom task name is forwarded correctly into the URL."""
        assert (
            symbol("T_ROB2", "TRAJCENTER_WebServices", "nbTrajAvailable")
            == "RAPID/T_ROB2/TRAJCENTER_WebServices/nbTrajAvailable"
        )

    def test_custom_module(self) -> None:
        """A custom module name is forwarded correctly into the URL."""
        assert symbol("T_ROB1", "MY_MODULE", "MyVar") == "RAPID/T_ROB1/MY_MODULE/MyVar"


class TestSymbolArrayElement:
    """Tests for RAPID array element symbol URL generation."""

    def test_first_traj_data_element(self) -> None:
        """RAPID braces are percent-encoded for ``trajData{1}``."""
        assert (
            symbol_array_element(
                "T_ROB1",
                "TRAJCENTER_WebServices",
                "trajData",
                1,
            )
            == "RAPID/T_ROB1/TRAJCENTER_WebServices/trajData%7B1%7D"
        )

    def test_trajectory_metadata_element(self) -> None:
        """RAPID braces are percent-encoded for ``trajectories{42}``."""
        assert (
            symbol_array_element(
                "T_ROB1",
                "TRAJCENTER_WebServices",
                "trajectories",
                42,
            )
            == "RAPID/T_ROB1/TRAJCENTER_WebServices/trajectories%7B42%7D"
        )

    def test_invalid_zero_index_raises(self) -> None:
        """RAPID arrays are one-based."""
        with pytest.raises(ValueError, match=">= 1"):
            symbol_array_element(
                "T_ROB1",
                "TRAJCENTER_WebServices",
                "trajData",
                0,
            )


class TestSymbolRecordArrayField:
    """Tests for RAPID record array field symbol URL generation."""

    def test_traj_data_move_type_field(self) -> None:
        """Record field access preserves the dot and encodes braces."""
        assert (
            symbol_record_array_field(
                "T_ROB1",
                "TRAJCENTER_WebServices",
                "trajData",
                1,
                "moveType",
            )
            == "RAPID/T_ROB1/TRAJCENTER_WebServices/trajData%7B1%7D.moveType"
        )

    def test_traj_data_point_field(self) -> None:
        """The ``point`` field URL is generated correctly."""
        assert (
            symbol_record_array_field(
                "T_ROB1",
                "TRAJCENTER_WebServices",
                "trajData",
                12,
                "point",
            )
            == "RAPID/T_ROB1/TRAJCENTER_WebServices/trajData%7B12%7D.point"
        )

    def test_empty_field_raises(self) -> None:
        """An empty RAPID record field name is invalid."""
        with pytest.raises(ValueError, match="field"):
            symbol_record_array_field(
                "T_ROB1",
                "TRAJCENTER_WebServices",
                "trajData",
                1,
                "",
            )

    def test_invalid_zero_index_raises(self) -> None:
        """RAPID record array indexes are one-based."""
        with pytest.raises(ValueError, match=">= 1"):
            symbol_record_array_field(
                "T_ROB1",
                "TRAJCENTER_WebServices",
                "trajData",
                0,
                "moveType",
            )
