#!/usr/bin/env python3
"""Reusable widgets for the TrajCenter TUI."""

from __future__ import annotations

from pathlib import Path

from rich.text import Text
from textual.widgets import Static

from trajcenter.store import scan_trajectory_store


class AMLogo(Static):
    """Arts et Métiers duotone ASCII logo."""

    def render(self) -> Text:
        """Render AM logo."""
        from trajcenter.ui.logos import render_am_logo

        return render_am_logo()


class LCFCLogo(Static):
    """LCFC duotone ASCII logo."""

    def render(self) -> Text:
        """Render LCFC logo."""
        from trajcenter.ui.logos import render_lcfc_logo

        return render_lcfc_logo()


class TitleBlock(Static):
    """Clickable centered home title that returns to the splash screen."""

    can_focus = True

    def render(self) -> Text:
        """Render the centered two-line title."""
        text = Text(justify="center")
        text.append("TRAJCENTER\n", style="bold #F59C00")
        text.append(
            "Trajectory conversion and ABB transfer toolkit",
            style="#A1A1AA",
        )
        return text

    def on_click(self) -> None:
        """Return to splash screen when the title is clicked."""
        self.app.switch_screen("splash")


class StoreStatus(Static):
    """Store status panel."""

    def __init__(self, store: Path) -> None:
        """Initialize store status.

        Args:
            store: Local trajectory store path.
        """
        super().__init__()
        self.store = store

    def render(self) -> Text:
        """Render store status."""
        text = Text()

        try:
            entries = scan_trajectory_store(self.store)
        except (FileNotFoundError, NotADirectoryError, ValueError) as exc:
            text.append("Store local\n", style="bold #F59C00")
            text.append(f"Path: {self.store}\n", style="#A1A1AA")
            text.append(f"Status: erreur - {exc}", style="bold #EF4444")
            return text

        text.append("Store local\n", style="bold #F59C00")
        text.append(f"Path: {self.store}\n", style="#A1A1AA")
        text.append(f"Archives détectées: {len(entries)}\n", style="bold #22C55E")

        if entries:
            text.append("\nDernières entrées:\n", style="bold white")
            for entry in entries[:5]:
                text.append(
                    f"  {entry.index:>2}. {entry.name} "
                    f"({entry.point_count} pts, process={entry.process_type})\n",
                    style="#F4F4F5",
                )

        return text


class ActionDescription(Static):
    """Description panel for the selected action."""
