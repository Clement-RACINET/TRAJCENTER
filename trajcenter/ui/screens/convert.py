#!/usr/bin/env python3
"""Trajectory conversion screen for the TrajCenter TUI."""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import BindingType
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Input, Select, Static

from trajcenter.convert.registry import infer_converter
from trajcenter.ui.config import UIConfig

CONVERT_FORMAT_OPTIONS: tuple[tuple[str, str], ...] = (
    ("Auto-détection selon extension", "auto"),
    ("CSV / TXT", "csv"),
    ("Excel .xlsx / .xlsm / .xls", "excel"),
    ("APT / APTSOURCE", "apt"),
    ("RAPID .mod", "mod"),
)


def normalize_convert_format(value: object) -> str | None:
    """Normalize the selected TUI conversion format.

    Args:
        value: Raw Select value.

    Returns:
        Format name accepted by ``infer_converter``, or ``None`` for auto mode.
    """
    if value in {None, Select.BLANK, "auto"}:
        return None

    return str(value)


def normalize_optional_stem(value: str) -> str | None:
    """Normalize an optional output stem.

    Args:
        value: Raw input value.

    Returns:
        Clean stem, or ``None`` when empty.
    """
    cleaned = value.strip()
    return cleaned or None


def build_conversion_success_text(output: Path) -> Text:
    """Build conversion success status text.

    Args:
        output: Created archive path.

    Returns:
        Rich status text.
    """
    text = Text()
    text.append("Status: ", style="bold white")
    text.append("OK", style="bold #22C55E")
    text.append("\nArchive créée : ", style="#F4F4F5")
    text.append(str(output), style="bold #F59C00")
    return text


def build_conversion_error_text(exc: Exception) -> Text:
    """Build conversion error status text.

    Args:
        exc: Conversion exception.

    Returns:
        Rich status text.
    """
    text = Text()
    text.append("Status: ", style="bold white")
    text.append("Erreur", style="bold #EF4444")
    text.append(f"\n{exc}", style="#F4F4F5")
    return text


class ConvertScreen(Screen[None]):
    """Screen used to convert source files to ``.trajcenter`` archives."""

    BINDINGS: ClassVar[list[BindingType]] = [
        ("escape", "back_to_home", "Accueil"),
        ("b", "back_to_home", "Retour"),
        ("r", "reset_form", "Réinitialiser"),
    ]

    DEFAULT_CSS = """
    ConvertScreen {
        layout: vertical;
        background: #101014;
        color: #F4F4F5;
    }

    #convert-container {
        height: 1fr;
        margin: 1 2 0 2;
        padding: 1;
        border: round #87196B;
        background: #181820;
    }

    #convert-title {
        height: 1;
        margin-bottom: 1;
        content-align: center middle;
        text-align: center;
        color: #F59C00;
        text-style: bold;
    }

    #convert-form {
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

    #convert-button-row {
        height: 3;
        margin-top: 0;
        align: center middle;
    }

    #convert-button {
        width: 32;
        height: 3;
    }

    #convert-status {
        height: 8;
        margin-top: 1;
        padding: 1;
        border: round #3F3F46;
        background: #101014;
    }

    #convert-help {
        height: 1;
        padding: 0 1;
        text-align: center;
        color: #A1A1AA;
        background: #181820;
    }
    """

    def __init__(self, config: UIConfig) -> None:
        """Initialize the conversion screen.

        Args:
            config: UI configuration.
        """
        super().__init__()
        self.config = config

    def compose(self) -> ComposeResult:
        """Compose the conversion screen."""
        yield Header(show_clock=True)

        with Container(id="convert-container"):
            yield Static("Convertir une trajectoire", id="convert-title")

            with Vertical(id="convert-form"):
                with Horizontal(classes="field-row"):
                    yield Static("Fichier source", classes="field-label")
                    yield Input(
                        placeholder="Ex: trajectory_files/test_basic.xlsx",
                        id="source-input",
                    )

                with Horizontal(classes="field-row"):
                    yield Static("Dossier destination", classes="field-label")
                    yield Input(
                        value=str(self.config.store),
                        placeholder="Ex: trajectory_store",
                        id="dest-input",
                    )

                with Horizontal(classes="field-row"):
                    yield Static("Nom de sortie", classes="field-label")
                    yield Input(
                        placeholder="Optionnel. Défaut : nom du fichier source",
                        id="name-input",
                    )

                with Horizontal(classes="field-row"):
                    yield Static("Format source", classes="field-label")
                    yield Select(
                        CONVERT_FORMAT_OPTIONS,
                        value="auto",
                        allow_blank=False,
                        id="format-select",
                    )

                with Horizontal(id="convert-button-row"):
                    yield Button(
                        "Convertir vers .trajcenter",
                        variant="primary",
                        id="convert-button",
                    )

            yield Static(
                "Status: en attente d'une conversion.",
                id="convert-status",
            )

        yield Static(
            "Coller: Ctrl+Shift+V · R réinitialiser · B/Echap accueil · Q quitter",
            id="convert-help",
        )

        yield Footer()

    def convert_file(
        self,
        source: Path,
        dest_dir: Path,
        stem: str | None = None,
        format_name: str | None = None,
    ) -> Path:
        """Convert a source file and save it as a ``.trajcenter`` archive.

        Args:
            source: Source file path.
            dest_dir: Destination directory.
            stem: Optional output archive stem.
            format_name: Optional explicit source format.

        Returns:
            Created archive path.

        Raises:
            FileNotFoundError: If the source does not exist.
            OSError: If output cannot be written.
            ValueError: If the format or file content is invalid.
        """
        converter = infer_converter(source, format_name)
        return converter.convert_and_save(
            source=source,
            dest_dir=dest_dir,
            stem=stem,
        )

    def action_reset_form(self) -> None:
        """Reset conversion form fields."""
        self.query_one("#source-input", Input).value = ""
        self.query_one("#dest-input", Input).value = str(self.config.store)
        self.query_one("#name-input", Input).value = ""
        self.query_one("#format-select", Select).value = "auto"
        self.query_one("#convert-status", Static).update(
            "Status: formulaire réinitialisé."
        )

    def action_back_to_home(self) -> None:
        """Return to the home screen."""
        self.app.switch_screen("home")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle conversion button press."""
        if event.button.id != "convert-button":
            return

        self.run_conversion_from_form()

    def run_conversion_from_form(self) -> None:
        """Read the form values and run the conversion."""
        source_value = self.query_one("#source-input", Input).value.strip()
        dest_value = self.query_one("#dest-input", Input).value.strip()
        name_value = self.query_one("#name-input", Input).value
        format_value = self.query_one("#format-select", Select).value
        status = self.query_one("#convert-status", Static)

        if not source_value:
            status.update(
                build_conversion_error_text(ValueError("Source file is required."))
            )
            return

        if not dest_value:
            status.update(
                build_conversion_error_text(
                    ValueError("Destination directory is required.")
                )
            )
            return

        source = Path(source_value)
        dest_dir = Path(dest_value)
        stem = normalize_optional_stem(name_value)
        format_name = normalize_convert_format(format_value)

        try:
            output = self.convert_file(
                source=source,
                dest_dir=dest_dir,
                stem=stem,
                format_name=format_name,
            )
        except (FileNotFoundError, OSError, ValueError) as exc:
            status.update(build_conversion_error_text(exc))
            return

        status.update(build_conversion_success_text(output))
