#!/usr/bin/env python3
"""Trajectory export screen for the TrajCenter TUI."""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Input, Select, Static

from trajcenter.core.trajectory import Trajectory
from trajcenter.export.registry import infer_exporter
from trajcenter.ui.config import UIConfig

EXPORT_FORMAT_OPTIONS: tuple[tuple[str, str], ...] = (
    ("CSV", "csv"),
    ("Excel .xlsx", "excel"),
)


def normalize_export_format(value: object) -> str:
    """Normalize the selected TUI export format.

    Args:
        value: Raw Select value.

    Returns:
        Export format name accepted by ``infer_exporter``.
    """
    if value in {None, Select.BLANK}:
        return "csv"

    return str(value)


def build_export_success_text(output: Path) -> Text:
    """Build export success status text.

    Args:
        output: Created export file path.

    Returns:
        Rich status text.
    """
    text = Text()
    text.append("Status: ", style="bold white")
    text.append("OK", style="bold #22C55E")
    text.append("\nFichier exporté : ", style="#F4F4F5")
    text.append(str(output), style="bold #F59C00")
    return text


def build_export_error_text(exc: Exception) -> Text:
    """Build export error status text.

    Args:
        exc: Export exception.

    Returns:
        Rich status text.
    """
    text = Text()
    text.append("Status: ", style="bold white")
    text.append("Erreur", style="bold #EF4444")
    text.append(f"\n{exc}", style="#F4F4F5")
    return text


class ExportScreen(Screen[None]):
    """Screen used to export ``.trajcenter`` archives to CSV or Excel."""

    BINDINGS: ClassVar[list[tuple[str, str, str]]] = [
        ("escape", "back_to_home", "Accueil"),
        ("b", "back_to_home", "Retour"),
        ("r", "reset_form", "Réinitialiser"),
    ]

    DEFAULT_CSS = """
    ExportScreen {
        layout: vertical;
        background: #101014;
        color: #F4F4F5;
    }

    #export-container {
        height: 1fr;
        margin: 1 2 0 2;
        padding: 1;
        border: round #87196B;
        background: #181820;
    }

    #export-title {
        height: 1;
        margin-bottom: 1;
        content-align: center middle;
        text-align: center;
        color: #F59C00;
        text-style: bold;
    }

    #export-form {
        height: auto;
    }

    .field-row {
        height: 3;
        margin-bottom: 1;
        align: left middle;
    }

    .field-label {
        width: 24;
        height: 3;
        content-align: left middle;
        color: #A1A1AA;
        text-style: bold;
    }

    Input {
        width: 1fr;
        height: 3;
        border: round #3F3F46;
        background: #101014;
        color: #F4F4F5;
    }

    Select {
        width: 1fr;
        height: 3;
    }

    #export-button-row {
        height: 3;
        margin-top: 0;
        align: center middle;
    }

    #export-button {
        width: 32;
        height: 3;
    }

    #export-status {
        height: 9;
        margin-top: 1;
        padding: 1;
        border: round #3F3F46;
        background: #101014;
    }

    #export-help {
        height: 1;
        padding: 0 1;
        text-align: center;
        color: #A1A1AA;
        background: #181820;
    }
    """

    def __init__(self, config: UIConfig) -> None:
        """Initialize the export screen.

        Args:
            config: UI configuration.
        """
        super().__init__()
        self.config = config

    def compose(self) -> ComposeResult:
        """Compose the export screen."""
        yield Header(show_clock=True)

        with Container(id="export-container"):
            yield Static("Exporter une trajectoire", id="export-title")

            with Vertical(id="export-form"):
                with Horizontal(classes="field-row"):
                    yield Static("Archive source", classes="field-label")
                    yield Input(
                        placeholder="Ex: trajectory_store/test_basic.trajcenter",
                        id="source-input",
                    )

                with Horizontal(classes="field-row"):
                    yield Static("Dossier destination", classes="field-label")
                    yield Input(
                        value="trajectory_exports",
                        placeholder="Ex: trajectory_exports",
                        id="dest-input",
                    )

                with Horizontal(classes="field-row"):
                    yield Static("Format export", classes="field-label")
                    yield Select(
                        EXPORT_FORMAT_OPTIONS,
                        value="csv",
                        allow_blank=False,
                        id="format-select",
                    )

                with Horizontal(id="export-button-row"):
                    yield Button(
                        "Exporter la trajectoire",
                        variant="primary",
                        id="export-button",
                    )

            yield Static(
                "Status: en attente d'un export.",
                id="export-status",
            )

        yield Static(
            "Coller: Ctrl+Shift+V · R réinitialiser · B/Echap accueil · Q quitter",
            id="export-help",
        )

        yield Footer()

    def export_file(
        self,
        source: Path,
        dest_dir: Path,
        format_name: str,
    ) -> Path:
        """Export a ``.trajcenter`` archive to a tabular file.

        Args:
            source: Source ``.trajcenter`` archive path.
            dest_dir: Destination directory.
            format_name: Export format name.

        Returns:
            Created export file path.

        Raises:
            FileNotFoundError: If the source does not exist.
            OSError: If output cannot be written.
            ValueError: If the source archive or format is invalid.
        """
        trajectory = Trajectory.load(source)
        exporter = infer_exporter(format_name)
        return exporter.export(trajectory, dest_dir)

    def action_reset_form(self) -> None:
        """Reset export form fields."""
        self.query_one("#source-input", Input).value = ""
        self.query_one("#dest-input", Input).value = "trajectory_exports"
        self.query_one("#format-select", Select).value = "csv"
        self.query_one("#export-status", Static).update(
            "Status: formulaire réinitialisé."
        )

    def action_back_to_home(self) -> None:
        """Return to the home screen."""
        self.app.switch_screen("home")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle export button press."""
        if event.button.id != "export-button":
            return

        self.run_export_from_form()

    def run_export_from_form(self) -> None:
        """Read form values and run the export."""
        source_value = self.query_one("#source-input", Input).value.strip()
        dest_value = self.query_one("#dest-input", Input).value.strip()
        format_value = self.query_one("#format-select", Select).value
        status = self.query_one("#export-status", Static)

        if not source_value:
            status.update(
                build_export_error_text(ValueError("Source archive is required."))
            )
            return

        if not dest_value:
            status.update(
                build_export_error_text(
                    ValueError("Destination directory is required.")
                )
            )
            return

        source = Path(source_value)
        dest_dir = Path(dest_value)
        format_name = normalize_export_format(format_value)

        try:
            output = self.export_file(
                source=source,
                dest_dir=dest_dir,
                format_name=format_name,
            )
        except (FileNotFoundError, OSError, ValueError) as exc:
            status.update(build_export_error_text(exc))
            return

        status.update(build_export_success_text(output))
