#!/usr/bin/env python3
"""Settings screen for the TrajCenter TUI."""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Input, Static

from trajcenter.ui.config import UIConfig


def parse_optional_string(value: str) -> str | None:
    """Parse an optional string value from an input field.

    Args:
        value: Raw input value.

    Returns:
        Stripped string or ``None`` when empty.
    """
    cleaned = value.strip()
    return cleaned or None


def parse_optional_int(value: str, field_name: str) -> int | None:
    """Parse an optional integer value.

    Args:
        value: Raw input value.
        field_name: Human-readable field name used in errors.

    Returns:
        Parsed integer or ``None`` when empty.

    Raises:
        ValueError: If the value is not a valid integer.
    """
    cleaned = value.strip()
    if not cleaned:
        return None

    try:
        return int(cleaned)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be an integer.") from exc


def parse_required_int(value: str, field_name: str) -> int:
    """Parse a required integer value.

    Args:
        value: Raw input value.
        field_name: Human-readable field name used in errors.

    Returns:
        Parsed integer.

    Raises:
        ValueError: If the value is empty or invalid.
    """
    parsed = parse_optional_int(value, field_name)
    if parsed is None:
        raise ValueError(f"{field_name} is required.")
    return parsed


def parse_optional_float(value: str, field_name: str) -> float | None:
    """Parse an optional float value.

    Args:
        value: Raw input value.
        field_name: Human-readable field name used in errors.

    Returns:
        Parsed float or ``None`` when empty.

    Raises:
        ValueError: If the value is not a valid float.
    """
    cleaned = value.strip()
    if not cleaned:
        return None

    try:
        return float(cleaned.replace(",", "."))
    except ValueError as exc:
        raise ValueError(f"{field_name} must be a number.") from exc


def parse_required_non_empty(value: str, field_name: str) -> str:
    """Parse a required non-empty string.

    Args:
        value: Raw input value.
        field_name: Human-readable field name used in errors.

    Returns:
        Stripped non-empty string.

    Raises:
        ValueError: If the value is empty.
    """
    cleaned = value.strip()
    if not cleaned:
        raise ValueError(f"{field_name} is required.")
    return cleaned


def build_settings_success_text() -> Text:
    """Build settings success status text.

    Returns:
        Rich status text.
    """
    text = Text()
    text.append("Status: ", style="bold white")
    text.append("OK", style="bold #22C55E")
    text.append("\nParamètres appliqués pour cette session.", style="#F4F4F5")
    return text


def build_settings_error_text(exc: Exception) -> Text:
    """Build settings error status text.

    Args:
        exc: Settings parsing exception.

    Returns:
        Rich status text.
    """
    text = Text()
    text.append("Status: ", style="bold white")
    text.append("Erreur", style="bold #EF4444")
    text.append(f"\n{exc}", style="#F4F4F5")
    return text


class SettingsScreen(Screen[None]):
    """Screen used to edit TrajCenter TUI session settings."""

    BINDINGS: ClassVar[tuple[tuple[str, str, str], ...]] = (
        ("escape", "back_to_home", "Accueil"),
        ("b", "back_to_home", "Retour"),
        ("r", "reset_form", "Réinitialiser"),
    )

    DEFAULT_CSS = """
    SettingsScreen {
        layout: vertical;
        background: #101014;
        color: #F4F4F5;
    }

    #settings-container {
        height: 1fr;
        margin: 1 2 0 2;
        padding: 1;
        border: round #87196B;
        background: #181820;
    }

    #settings-title {
        height: 1;
        margin-bottom: 1;
        content-align: center middle;
        text-align: center;
        color: #F59C00;
        text-style: bold;
    }

    #settings-form {
        height: auto;
    }

    .settings-two-columns {
        height: auto;
    }

    .settings-column {
        width: 1fr;
        height: auto;
    }

    .settings-column-left {
        margin-right: 1;
    }

    .settings-column-right {
        margin-left: 1;
    }

    .settings-row {
        height: 4;
        margin-bottom: 0;
    }

    .settings-label {
        height: 1;
        margin-bottom: 0;
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

    #settings-button-row {
        height: 3;
        margin-top: 1;
        align: center middle;
    }

    #apply-settings-button {
        width: 34;
        height: 3;
    }

    #settings-status {
        height: 5;
        margin: 1 0 0 0;
        padding: 1;
        border: round #3F3F46;
        background: #101014;
    }

    #settings-help {
        height: 1;
        padding: 0 1;
        text-align: center;
        color: #A1A1AA;
        background: #181820;
    }
    """


    def __init__(self, config: UIConfig) -> None:
        """Initialize the settings screen.

        Args:
            config: Shared UI configuration.
        """
        super().__init__()
        self.config = config

    def compose(self) -> ComposeResult:
        """Compose the settings screen."""
        yield Header(show_clock=True)

        with Container(id="settings-container"):
            yield Static("Paramètres TrajCenter", id="settings-title")

            with Vertical(id="settings-form"):
                with Horizontal(classes="settings-two-columns"):
                    with Vertical(classes="settings-column settings-column-left"):
                        with Vertical(classes="settings-row"):
                            yield Static("Store local", classes="settings-label")
                            yield Input(
                                value=str(self.config.store),
                                placeholder="trajectory_store",
                                id="store-input",
                            )

                        with Vertical(classes="settings-row"):
                            yield Static("Fichier .env", classes="settings-label")
                            yield Input(
                                value=(
                                    ""
                                    if self.config.env_file is None
                                    else str(self.config.env_file)
                                ),
                                placeholder="Optionnel. Ex: .env",
                                id="env-file-input",
                            )

                        with Vertical(classes="settings-row"):
                            yield Static("Utilisateur", classes="settings-label")
                            yield Input(
                                value=self.config.username or "",
                                placeholder="Ex: Default User",
                                id="username-input",
                            )

                        with Vertical(classes="settings-row"):
                            yield Static("Timeout", classes="settings-label")
                            yield Input(
                                value=(
                                    ""
                                    if self.config.timeout is None
                                    else str(self.config.timeout)
                                ),
                                placeholder="Ex: 5.0",
                                id="timeout-input",
                            )

                        with Vertical(classes="settings-row"):
                            yield Static("Module RAPID", classes="settings-label")
                            yield Input(
                                value=self.config.module,
                                placeholder="TRAJCENTER",
                                id="module-input",
                            )

                        with Vertical(classes="settings-row"):
                            yield Static("Log level", classes="settings-label")
                            yield Input(
                                value=self.config.log_level,
                                placeholder="INFO",
                                id="log-level-input",
                            )

                    with Vertical(classes="settings-column settings-column-right"):
                        with Vertical(classes="settings-row"):
                            yield Static("Host robot", classes="settings-label")
                            yield Input(
                                value=self.config.host or "",
                                placeholder="Ex: 127.0.0.1 ou 192.168.125.1",
                                id="host-input",
                            )

                        with Vertical(classes="settings-row"):
                            yield Static("Port robot", classes="settings-label")
                            yield Input(
                                value=(
                                    ""
                                    if self.config.port is None
                                    else str(self.config.port)
                                ),
                                placeholder="Ex: 80",
                                id="port-input",
                            )

                        with Vertical(classes="settings-row"):
                            yield Static("Password env", classes="settings-label")
                            yield Input(
                                value=self.config.password_env or "",
                                placeholder="Ex: TRAJCENTER_ROBOT_PASSWORD",
                                id="password-env-input",
                            )

                        with Vertical(classes="settings-row"):
                            yield Static("Task RAPID", classes="settings-label")
                            yield Input(
                                value=self.config.task,
                                placeholder="T_ROB1",
                                id="task-input",
                            )

                        with Vertical(classes="settings-row"):
                            yield Static(
                                "Mastership retries",
                                classes="settings-label",
                            )
                            yield Input(
                                value=str(self.config.mastership_retries),
                                placeholder="3",
                                id="mastership-retries-input",
                            )

                with Horizontal(id="settings-button-row"):
                    yield Button(
                        "Appliquer pour cette session",
                        variant="primary",
                        id="apply-settings-button",
                    )

            yield Static(
                "Status: en attente de modification.",
                id="settings-status",
            )

        yield Static(
            "Coller: Ctrl+Shift+V · R réinitialiser · B/Echap accueil · Q quitter",
            id="settings-help",
        )

        yield Footer()

    def apply_settings(
        self,
        store: Path,
        env_file: Path | None,
        host: str | None,
        port: int | None,
        username: str | None,
        password_env: str | None,
        timeout: float | None,
        task: str,
        module: str,
        mastership_retries: int,
        log_level: str,
    ) -> None:
        """Apply settings to the shared UI configuration.

        Args:
            store: Local trajectory store path.
            env_file: Optional env file path.
            host: Optional robot host.
            port: Optional robot port.
            username: Optional robot username.
            password_env: Optional password environment variable name.
            timeout: Optional robot request timeout.
            task: RAPID task name.
            module: RAPID module name.
            mastership_retries: Mastership retry count.
            log_level: Log level name.
        """
        self.config.store = store
        self.config.env_file = env_file
        self.config.host = host
        self.config.port = port
        self.config.username = username
        self.config.password_env = password_env
        self.config.timeout = timeout
        self.config.task = task
        self.config.module = module
        self.config.mastership_retries = mastership_retries
        self.config.log_level = log_level

    def read_settings_from_form(
        self,
    ) -> tuple[
        Path,
        Path | None,
        str | None,
        int | None,
        str | None,
        str | None,
        float | None,
        str,
        str,
        int,
        str,
    ]:
        """Read and validate settings from form fields.

        Returns:
            Tuple of parsed settings.

        Raises:
            ValueError: If a field is invalid.
        """
        store_value = self.query_one("#store-input", Input).value
        env_file_value = self.query_one("#env-file-input", Input).value
        host_value = self.query_one("#host-input", Input).value
        port_value = self.query_one("#port-input", Input).value
        username_value = self.query_one("#username-input", Input).value
        password_env_value = self.query_one("#password-env-input", Input).value
        timeout_value = self.query_one("#timeout-input", Input).value
        task_value = self.query_one("#task-input", Input).value
        module_value = self.query_one("#module-input", Input).value
        retries_value = self.query_one("#mastership-retries-input", Input).value
        log_level_value = self.query_one("#log-level-input", Input).value

        store = Path(parse_required_non_empty(store_value, "Store local"))
        env_file_raw = parse_optional_string(env_file_value)
        env_file = None if env_file_raw is None else Path(env_file_raw)
        host = parse_optional_string(host_value)
        port = parse_optional_int(port_value, "Port robot")
        username = parse_optional_string(username_value)
        password_env = parse_optional_string(password_env_value)
        timeout = parse_optional_float(timeout_value, "Timeout")
        task = parse_required_non_empty(task_value, "Task RAPID")
        module = parse_required_non_empty(module_value, "Module RAPID")
        retries = parse_required_int(retries_value, "Mastership retries")
        log_level = parse_required_non_empty(log_level_value, "Log level").upper()

        if retries < 0:
            raise ValueError("Mastership retries must be greater than or equal to 0.")

        return (
            store,
            env_file,
            host,
            port,
            username,
            password_env,
            timeout,
            task,
            module,
            retries,
            log_level,
        )

    def refresh_form_from_config(self) -> None:
        """Refresh form fields from the current shared configuration."""
        self.query_one("#store-input", Input).value = str(self.config.store)
        self.query_one("#env-file-input", Input).value = (
            "" if self.config.env_file is None else str(self.config.env_file)
        )
        self.query_one("#host-input", Input).value = self.config.host or ""
        self.query_one("#port-input", Input).value = (
            "" if self.config.port is None else str(self.config.port)
        )
        self.query_one("#username-input", Input).value = self.config.username or ""
        self.query_one("#password-env-input", Input).value = (
            self.config.password_env or ""
        )
        self.query_one("#timeout-input", Input).value = (
            "" if self.config.timeout is None else str(self.config.timeout)
        )
        self.query_one("#task-input", Input).value = self.config.task
        self.query_one("#module-input", Input).value = self.config.module
        self.query_one("#mastership-retries-input", Input).value = str(
            self.config.mastership_retries
        )
        self.query_one("#log-level-input", Input).value = self.config.log_level

    def action_reset_form(self) -> None:
        """Reset form fields from the current config."""
        self.refresh_form_from_config()
        self.query_one("#settings-status", Static).update(
            "Status: formulaire réinitialisé depuis la configuration courante."
        )

    def action_back_to_home(self) -> None:
        """Return to the home screen."""
        self.app.switch_screen("home")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle settings button press."""
        if event.button.id != "apply-settings-button":
            return

        self.run_apply_from_form()

    def run_apply_from_form(self) -> None:
        """Read settings from the form and apply them to the config."""
        status = self.query_one("#settings-status", Static)

        try:
            settings = self.read_settings_from_form()
            self.apply_settings(*settings)
        except ValueError as exc:
            status.update(build_settings_error_text(exc))
            return

        status.update(build_settings_success_text())
