# tests/rws/test_utils.py
"""Tests for trajcenter.rws._utils."""

from __future__ import annotations


from trajcenter.rws._utils import symbol


class TestSymbol:
    """Tests for the symbol() helper."""

    def test_simple_variable(self) -> None:
        """Simple variable name produces correct URL."""
        assert (
            symbol("T_ROB1", "TRAJCENTER", "TrajReady")
            == "RAPID/T_ROB1/TRAJCENTER/TrajReady"
        )

    def test_array_element(self) -> None:
        """Array element notation is preserved as-is."""
        assert (
            symbol("T_ROB1", "TRAJCENTER", "NomsTraj/[1]")
            == "RAPID/T_ROB1/TRAJCENTER/NomsTraj/[1]"
        )

    def test_custom_task(self) -> None:
        """Custom task name is forwarded correctly."""
        assert (
            symbol("T_ROB2", "TRAJCENTER", "NbTrajDispo")
            == "RAPID/T_ROB2/TRAJCENTER/NbTrajDispo"
        )

    def test_custom_module(self) -> None:
        """Custom module name is forwarded correctly."""
        assert symbol("T_ROB1", "MY_MODULE", "MyVar") == "RAPID/T_ROB1/MY_MODULE/MyVar"

    def test_nested_array(self) -> None:
        """Nested array notation (robtarget) is preserved."""
        assert (
            symbol("T_ROB1", "TRAJCENTER", "RobtTRAJCENTER/[42]")
            == "RAPID/T_ROB1/TRAJCENTER/RobtTRAJCENTER/[42]"
        )
