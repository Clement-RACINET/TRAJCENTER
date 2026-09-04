#!/usr/bin/env python3
"""Home screen for the TrajCenter TUI."""

from __future__ import annotations

from typing import ClassVar

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Footer, Header, Label, ListItem, ListView

from trajcenter.ui.actions import HOME_ACTIONS
from trajcenter.ui.config import UIConfig
from trajcenter.ui.widgets import ActionDescription, StoreStatus, TitleBlock


class HomeScreen(Screen[None]):
    """Main TrajCenter home screen."""

    BINDINGS: ClassVar[tuple[tuple[str, str], ...]] = (
        ("s", "back_to_splash"),
        ("escape", "back_to_splash"),
    )

    DEFAULT_CSS = """
    HomeScreen {
        layout: vertical;
        background: #101014;
        color: #F4F4F5;
    }

    #title-block {
        height: 7;
        padding: 1 2;
        border: round #87196B;
        background: #181820;
        margin: 1 2 0 2;
        content-align: center middle;
        text-align: center;
    }

    #main {
        height: 1fr;
        padding: 1 2 0 2;
    }

    #left {
        width: 1fr;
        padding: 1;
        border: round #87196B;
        background: #181820;
    }

    #right {
        width: 1fr;
        padding: 1;
        border: round #F59C00;
        background: #181820;
    }

    #menu-title {
        color: #F59C00;
        text-style: bold;
        margin-bottom: 1;
    }

    #menu {
        height: 1fr;
        border: round #3F3F46;
    }

    ListView {
        background: #101014;
    }

    ListItem {
        padding: 0 1;
    }

    ListItem.--highlight {
        background: #87196B;
        color: white;
        text-style: bold;
    }

    #description {
        height: 5;
        margin: 1 2 0 2;
        padding: 1;
        border: round #3F3F46;
        background: #181820;
        color: #F4F4F5;
    }

    #help {
        height: 3;
        padding: 1;
        text-align: center;
        color: #A1A1AA;
        background: #181820;
    }
    """

    def __init__(self, config: UIConfig) -> None:
        """Initialize home screen.

        Args:
            config: UI configuration.
        """
        super().__init__()
        self.config = config
        self.description = ActionDescription(id="description")

    def compose(self) -> ComposeResult:
        """Compose widgets."""
        yield Header(show_clock=True)

        yield TitleBlock(id="title-block")

        with Horizontal(id="main"):
            with Vertical(id="left"):
                yield Label("Menu principal", id="menu-title")
                yield ListView(
                    *[
                        ListItem(Label(action.label), name=action.key)
                        for action in HOME_ACTIONS
                    ],
                    id="menu",
                )

            with Vertical(id="right"):
                yield StoreStatus(self.config.store)

        yield self.description

        yield Label(
            "↑/↓ naviguer · Entrée sélectionner · S splash · R rafraîchir · Q quitter",
            id="help",
        )

        yield Footer()

    def on_mount(self) -> None:
        """Initialize selected action."""
        menu = self.query_one("#menu", ListView)
        menu.index = 0
        self._update_description(0)

    def action_back_to_splash(self) -> None:
        """Return to splash screen."""
        self.app.switch_screen("splash")

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        """Update description when selected item changes."""
        if event.list_view.id != "menu":
            return
        if event.list_view.index is None:
            return
        self._update_description(event.list_view.index)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Handle selected menu item."""
        menu = self.query_one("#menu", ListView)

        if menu.index is None:
            return

        action = HOME_ACTIONS[menu.index]
        action_name = action.key

        if action_name == "quit":
            self.app.exit()
            return

        self._show_placeholder(action_name)

    def _show_placeholder(self, action_name: str) -> None:
        """Show placeholder description for a selected action."""
        messages = {
            "store": (
                "Explorer le store local",
                "Prochaine étape : afficher une table interactive des archives .trajcenter.",
            ),
            "robot": (
                "Supervision robot ABB",
                "Prochaine étape : écran de transfert de trajectoires et supervision RWS.",
            ),
            "convert": (
                "Convertir une trajectoire",
                "Prochaine étape : assistant de conversion CSV, Excel, APT ou MOD vers .trajcenter.",
            ),
            "export": (
                "Exporter une trajectoire",
                "Prochaine étape : exporter une archive .trajcenter vers CSV ou Excel.",
            ),
            "settings": (
                "Paramètres",
                "Prochaine étape : configurer le store, les paramètres ABB et les chemins par défaut.",
            ),
        }

        title, body = messages.get(
            action_name,
            ("Action inconnue", f"Aucune action définie pour : {action_name}"),
        )

        self.description.update(Text.from_markup(f"[bold #F59C00]{title}[/]\n\n{body}"))

    def _update_description(self, index: int) -> None:
        """Update action description."""
        action = HOME_ACTIONS[index]
        text = Text()
        text.append(f"{action.label}\n", style="bold #F59C00")
        text.append(action.description, style="#F4F4F5")
        self.description.update(text)
