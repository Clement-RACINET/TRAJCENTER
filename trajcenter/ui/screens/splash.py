#!/usr/bin/env python3
"""Splash screen for the TrajCenter TUI."""

from __future__ import annotations

from typing import ClassVar

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Footer, Header, Static

from trajcenter.ui.widgets import AMLogo, LCFCLogo


class SplashScreen(Screen[None]):
    """Landing page with institutional logos."""

    BINDINGS: ClassVar[list[tuple[str, str]]] = [
        ("enter", "continue_to_home"),
        ("space", "continue_to_home"),
        ("q", "quit"),
        ("escape", "quit"),
    ]
    DEFAULT_CSS = """
    SplashScreen {
        layout: vertical;
        background: #101014;
        color: #F4F4F5;
    }

    #splash-container {
        width: 100%;
        height: 1fr;
        margin: 1 2 0 2;
        padding: 1 2;
        border: round #87196B;
        background: #181820;
    }

    #logos-row {
        width: 100%;
        height: 20;
        layout: horizontal;
        align: center middle;
    }

    #am-card {
        width: 1fr;
        height: 20;
        margin-right: 1;
        align: center middle;
    }

    #lcfc-card {
        width: 1fr;
        height: 20;
        margin-left: 1;
        align: center middle;
    }

    #am-logo {
        width: 100%;
        height: 16;
        content-align: center middle;
    }

    #lcfc-logo {
        width: 100%;
        height: 17;
        content-align: center middle;
    }

    #am-text-1,
    #lcfc-text-1 {
        width: 100%;
        height: 1;
        content-align: center middle;
        color: #F4F4F5;
        text-style: bold;
    }

    #am-text-2,
    #lcfc-text-2 {
        width: 100%;
        height: 1;
        content-align: center middle;
        color: #A1A1AA;
    }

    #separator-top {
        width: 100%;
        height: 1;
        margin-top: 0;
        margin-bottom: 1;
        background: #87196B;
    }

    #separator-bottom {
        width: 100%;
        height: 1;
        margin-top: 1;
        margin-bottom: 1;
        background: #87196B;
    }

    #trajcenter-title {
        width: 100%;
        height: 8;
        content-align: center middle;
        color: white;
        text-style: bold;
    }

    #splash-authors {
        width: 100%;
        height: 1;
        margin-top: 1;
        content-align: center middle;
        color: #F4F4F5;
        text-style: bold;
    }

    #splash-help {
        width: 100%;
        height: 1;
        margin-top: 0;
        content-align: center middle;
        color: #F59C00;
        text-style: bold;
    }
    """

    def compose(self) -> ComposeResult:
        """Compose the splash screen."""
        from trajcenter.ui.logos import (
            AM_TEXT_1,
            AM_TEXT_2,
            LCFC_TEXT_1,
            LCFC_TEXT_2,
            SPLASH_AUTHORS,
            SPLASH_HELP,
            TRAJCENTER_ASCII,
        )

        yield Header(show_clock=True)

        with Container(id="splash-container"):
            with Horizontal(id="logos-row"):
                with Vertical(id="am-card"):
                    yield AMLogo(id="am-logo")
                    yield Static(AM_TEXT_1, id="am-text-1")
                    yield Static(AM_TEXT_2, id="am-text-2")

                with Vertical(id="lcfc-card"):
                    yield LCFCLogo(id="lcfc-logo")
                    yield Static(LCFC_TEXT_1, id="lcfc-text-1")
                    yield Static(LCFC_TEXT_2, id="lcfc-text-2")

            yield Static("", id="separator-top")
            yield Static(TRAJCENTER_ASCII, id="trajcenter-title")
            yield Static("", id="separator-bottom")
            yield Static(SPLASH_AUTHORS, id="splash-authors")
            yield Static(SPLASH_HELP, id="splash-help")

        yield Footer()

    def action_continue_to_home(self) -> None:
        """Switch from splash screen to home screen."""
        self.app.switch_screen("home")
