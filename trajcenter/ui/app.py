#!/usr/bin/env python3
"""Textual application entry point for TrajCenter."""

from __future__ import annotations

from typing import ClassVar

from textual.app import App
from textual.binding import BindingType

from trajcenter.ui.config import UIConfig
from trajcenter.ui.screens.convert import ConvertScreen
from trajcenter.ui.screens.export import ExportScreen
from trajcenter.ui.screens.home import HomeScreen
from trajcenter.ui.screens.robot import RobotScreen
from trajcenter.ui.screens.settings import SettingsScreen
from trajcenter.ui.screens.splash import SplashScreen
from trajcenter.ui.screens.store import StoreScreen


class TrajCenterTUI(App[None]):
    """Main TrajCenter TUI app."""

    CSS = """
    Screen {
        background: #101014;
    }

    Header {
        background: #87196B;
        color: white;
    }

    Footer {
        background: #181820;
        color: #A1A1AA;
    }
    """

    BINDINGS: ClassVar[list[BindingType]] = [
        ("q", "quit", "Quitter"),
        ("r", "refresh", "Rafraîchir"),
        ("s", "show_splash", "Splash"),
    ]

    TITLE = "TrajCenter"

    def __init__(self, config: UIConfig | None = None) -> None:
        """Initialize the TUI app.

        Args:
            config: UI configuration.
        """
        super().__init__()
        self.config = config or UIConfig()

    def on_mount(self) -> None:
        """Install and open screens."""
        self.install_screen(SplashScreen(), name="splash")
        self.install_screen(HomeScreen(self.config), name="home")
        self.install_screen(StoreScreen(self.config), name="store")
        self.install_screen(ConvertScreen(self.config), name="convert")
        self.install_screen(ExportScreen(self.config), name="export")
        self.install_screen(RobotScreen(self.config), name="robot")
        self.install_screen(SettingsScreen(self.config), name="settings")
        self.push_screen("splash")

    def action_refresh(self) -> None:
        """Refresh the current screen."""
        self.refresh()

    def action_show_splash(self) -> None:
        """Show splash screen."""
        self.switch_screen("splash")


def run_tui(config: UIConfig | None = None) -> int:
    """Run the TrajCenter Textual TUI.

    Args:
        config: Optional UI configuration.

    Returns:
        Process exit code.
    """
    app = TrajCenterTUI(config=config)
    app.run()
    return 0
