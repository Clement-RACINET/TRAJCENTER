#!/usr/bin/env python3
# tests/rws/test_utils.py
"""Tests for :mod:`trajcenter.rws._utils`.

Author: Clement RACINET
"""

from __future__ import annotations

from trajcenter.rws._utils import symbol


class TestSymbol:
    """Tests for the :func:`~trajcenter.rws._utils.symbol` helper."""

    def test_simple_variable(self) -> None:
        """A simple variable name produces the correct ``RAPID/`` URL."""
        assert (
            symbol("T_ROB1", "TRAJCENTER", "TrajReady")
            == "RAPID/T_ROB1/TRAJCENTER/TrajReady"
        )

    def test_array_element(self) -> None:
        """Array element notation is preserved as-is in the URL."""
        assert (
            symbol("T_ROB1", "TRAJCENTER", "NomsTraj/[1]")
            == "RAPID/T_ROB1/TRAJCENTER/NomsTraj/[1]"
        )

    def test_custom_task(self) -> None:
        """A custom task name is forwarded correctly into the URL."""
        assert (
            symbol("T_ROB2", "TRAJCENTER", "NbTrajDispo")
            == "RAPID/T_ROB2/TRAJCENTER/NbTrajDispo"
        )

    def test_custom_module(self) -> None:
        """A custom module name is forwarded correctly into the URL."""
        assert symbol("T_ROB1", "MY_MODULE", "MyVar") == "RAPID/T_ROB1/MY_MODULE/MyVar"

    def test_nested_array(self) -> None:
        """Nested array notation (e.g. robtarget array) is preserved in the URL."""
        assert (
            symbol("T_ROB1", "TRAJCENTER", "RobtTRAJCENTER/[42]")
            == "RAPID/T_ROB1/TRAJCENTER/RobtTRAJCENTER/[42]"
        )
