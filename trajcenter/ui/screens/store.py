#!/usr/bin/env python3
"""Store exploration screen for the TrajCenter TUI."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import BindingType
from textual.containers import Container, Vertical
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header, Static

from trajcenter.store import scan_trajectory_store
from trajcenter.ui.config import UIConfig

if TYPE_CHECKING:
    from trajcenter.store.models import TrajectoryStoreEntry


class StoreScreen(Screen[None]):
    """Screen used to inspect the local TrajCenter trajectory store."""

    BINDINGS: ClassVar[list[BindingType]] = [
        ("escape", "back_to_home", "Accueil"),
        ("b", "back_to_home", "Retour"),
        ("r", "refresh_entries", "Rafraîchir"),
    ]

    DEFAULT_CSS = """
    StoreScreen {
        layout: vertical;
        background: #101014;
        color: #F4F4F5;
    }

    #store-container {
        height: 1fr;
        margin: 1 2;
        padding: 1;
        border: round #87196B;
        background: #181820;
    }

    #store-title {
        height: 3;
        content-align: center middle;
        text-align: center;
        color: #F59C00;
        text-style: bold;
    }

    #store-path {
        height: 2;
        color: #A1A1AA;
    }

    #store-status {
        height: 3;
        margin-top: 1;
        padding: 1;
        border: round #3F3F46;
        background: #101014;
    }

    #store-table {
        height: 1fr;
        margin-top: 1;
        border: round #3F3F46;
        background: #101014;
    }

    #store-help {
        height: 3;
        padding: 1;
        text-align: center;
        color: #A1A1AA;
        background: #181820;
    }
    """

    def __init__(self, config: UIConfig) -> None:
        """Initialize the store screen.

        Args:
            config: UI configuration.
        """
        super().__init__()
        self.config = config

    def compose(self) -> ComposeResult:
        """Compose the store screen."""
        yield Header(show_clock=True)

        with Container(id="store-container"), Vertical():
            yield Static("Store local TrajCenter", id="store-title")
            yield Static(f"Path: {self.config.store}", id="store-path")
            yield DataTable(id="store-table")
            yield Static("", id="store-status")

        yield Static(
            "↑/↓ naviguer · R rafraîchir · B/Echap retour accueil · Q quitter",
            id="store-help",
        )

        yield Footer()

    def on_mount(self) -> None:
        """Initialize the data table when the screen is mounted."""
        table = self.query_one("#store-table", DataTable)
        table.cursor_type = "row"
        table.zebra_stripes = True
        table.add_columns("IDX", "Nom", "Points", "Process", "Fichier")
        self.refresh_entries()

    def load_entries(self) -> tuple[TrajectoryStoreEntry, ...]:
        """Load trajectory entries from the configured store.

        Returns:
            Store entries.
        """
        return scan_trajectory_store(self.config.store)

    def refresh_entries(self) -> None:
        """Refresh displayed store entries."""
        table = self.query_one("#store-table", DataTable)
        status = self.query_one("#store-status", Static)

        table.clear()

        try:
            entries = self.load_entries()
        except (FileNotFoundError, NotADirectoryError, ValueError) as exc:
            status.update(self._error_text(exc))
            return

        for entry in entries:
            table.add_row(
                str(entry.index),
                entry.name,
                str(entry.point_count),
                str(entry.process_type),
                entry.path.name,
            )

        status.update(self._success_text(len(entries)))

    def action_refresh_entries(self) -> None:
        """Refresh store entries from the keyboard binding."""
        self.refresh_entries()

    def action_back_to_home(self) -> None:
        """Return to the home screen."""
        self.app.switch_screen("home")

    def _success_text(self, count: int) -> Text:
        """Build success status text.

        Args:
            count: Number of detected store entries.

        Returns:
            Rich text status.
        """
        text = Text()
        text.append("Status: ", style="bold white")
        text.append("OK", style="bold #22C55E")
        text.append(f" — {count} archive(s) détectée(s).", style="#F4F4F5")
        return text

    def _error_text(self, exc: Exception) -> Text:
        """Build error status text.

        Args:
            exc: Exception raised while loading the store.

        Returns:
            Rich text status.
        """
        text = Text()
        text.append("Status: ", style="bold white")
        text.append("Erreur", style="bold #EF4444")
        text.append(f" — {exc}", style="#F4F4F5")
        return text
