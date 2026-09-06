#!/usr/bin/env python3
"""Robot supervision screen for the TrajCenter TUI."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar, cast

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, RichLog, Static

from trajcenter.ui.config import UIConfig

if TYPE_CHECKING:
    from textual.app import App


class RobotScreen(Screen[None]):
    """Screen used to start and stop the ABB RWS supervision process."""

    BINDINGS: ClassVar[list[tuple[str, str, str]]] = [
        ("escape", "back_to_home", "Accueil"),
        ("b", "back_to_home", "Retour"),
        ("x", "stop_supervision", "Arrêter supervision"),
    ]

    DEFAULT_CSS = """
    RobotScreen {
        layout: vertical;
        background: #101014;
        color: #F4F4F5;
    }

    #robot-container {
        height: 1fr;
        margin: 1 2 0 2;
        padding: 1;
        border: round #87196B;
        background: #181820;
    }

    #robot-title {
        height: 1;
        margin-bottom: 1;
        content-align: center middle;
        text-align: center;
        color: #F59C00;
        text-style: bold;
    }

    #robot-info {
        height: auto;
        margin-bottom: 1;
        padding: 1;
        border: round #3F3F46;
        background: #101014;
        color: #F4F4F5;
    }

    #robot-button-row {
        height: 3;
        margin-top: 1;
        align: center middle;
    }

    #start-robot-button {
        width: 34;
        height: 3;
        text-style: bold;
        border: tall transparent;
    }

    #start-robot-button.robot-start-button {
        background: #0F7FD6;
        color: white;
        border: tall #0F7FD6;
    }

    #start-robot-button.robot-start-button:hover {
        background: #F59C00;
        color: #101014;
        border: tall #F59C00;
    }

    #start-robot-button.robot-start-button:focus {
        background: #0F7FD6;
        color: white;
        border: tall #F59C00;
    }

    #start-robot-button.robot-stop-button {
        background: #B91C1C;
        color: white;
        border: tall #B91C1C;
    }

    #start-robot-button.robot-stop-button:hover {
        background: #F59C00;
        color: #101014;
        border: tall #F59C00;
    }

    #start-robot-button.robot-stop-button:focus {
        background: #B91C1C;
        color: white;
        border: tall #F59C00;
    }

    #robot-status {
        height: 3;
        margin-top: 1;
        padding: 1;
        border: round #3F3F46;
        background: #101014;
    }

    #robot-log {
        height: 1fr;
        margin-top: 1;
        padding: 1;
        border: round #3F3F46;
        background: #050508;
        color: #F4F4F5;
    }

    #robot-help {
        height: 1;
        padding: 0 1;
        text-align: center;
        color: #A1A1AA;
        background: #181820;
    }
    """

    def __init__(self, config: UIConfig) -> None:
        """Initialize the robot screen.

        Args:
            config: UI configuration.
        """
        super().__init__()
        self.config = config
        self._process: subprocess.Popen[str] | None = None
        self._stopping = False

    def compose(self) -> ComposeResult:
        """Compose the robot supervision screen."""
        yield Header(show_clock=True)

        with Container(id="robot-container"):
            yield Static("Supervision robot ABB", id="robot-title")

            with Vertical(id="robot-info"):
                yield Static(f"Store local : {self.config.store}")
                yield Static(f"Task RAPID : {self.config.task}")
                yield Static(f"Module RAPID : {self.config.module}")
                yield Static(
                    "La supervision écoute les demandes RAPID "
                    "refreshMetaRequest et sendTrajRequest."
                )

            with Horizontal(id="robot-button-row"):
                yield Button(
                    "Démarrer la supervision",
                    id="start-robot-button",
                    classes="robot-start-button",
                )

            yield Static(
                "Status: supervision arrêtée.",
                id="robot-status",
            )

            yield RichLog(
                id="robot-log",
                highlight=True,
                markup=True,
                wrap=True,
                auto_scroll=True,
            )

        yield Static(
            "Entrée bouton · X arrêter · B/Echap accueil · Q quitter",
            id="robot-help",
        )

        yield Footer()

    def action_back_to_home(self) -> None:
        """Return to home screen."""
        if self._is_running():
            self._append_log(
                "[yellow]Supervision encore active. "
                "Appuie sur X ou sur le bouton Arrêter avant de revenir à l'accueil.[/]"
            )
            return

        self.app.switch_screen("home")

    def action_stop_supervision(self) -> None:
        """Stop robot supervision from keyboard binding."""
        self.stop_supervision()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle start/stop button press."""
        if event.button.id != "start-robot-button":
            return

        if self._is_running():
            self.stop_supervision()
            return

        self.start_supervision()

    def start_supervision(self) -> None:
        """Start the ABB RWS supervisor as a subprocess."""
        if self._is_running():
            self._set_status("Status: la supervision est déjà en cours.")
            return

        if not self.config.features.robot:
            self._set_status(
                "Status: option robot indisponible dans cet environnement."
            )
            self._append_log(
                "[red]Option robot indisponible dans cet environnement.[/]"
            )
            return

        script_path = self._get_supervisor_script_path()

        if not script_path.exists():
            self._set_status("Status: script superviseur introuvable.")
            self._append_log(f"[red]Script introuvable : {script_path}[/]")
            return

        command = self._build_supervisor_command(script_path)

        self._clear_log()
        self._append_log("[bold #F59C00]Démarrage supervision robot ABB[/]")
        self._append_log(f"[dim]Commande : {' '.join(command)}[/]")

        try:
            self._process = subprocess.Popen(
                command,
                cwd=self._get_project_root(),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                universal_newlines=True,
                creationflags=self._get_process_creation_flags(),
            )
        except OSError as exc:
            self._process = None
            self._set_status("Status: échec démarrage supervision.")
            self._append_log(f"[red]Erreur démarrage process : {exc}[/]")
            return

        self._stopping = False
        self._set_running_ui()
        self.run_worker(
            self._read_process_output_worker,
            thread=True,
            name="robot-supervisor-output",
        )

    def stop_supervision(self) -> None:
        """Stop the ABB RWS supervisor subprocess."""
        process = self._process

        if process is None or process.poll() is not None:
            self._process = None
            self._set_stopped_ui("Status: supervision arrêtée.")
            return

        if self._stopping:
            self._append_log("[yellow]Arrêt déjà demandé, attente du process...[/]")
            return

        self._stopping = True
        self._set_status("Status: arrêt de la supervision demandé...")
        self._append_log("[yellow]Arrêt de la supervision demandé.[/]")

        self.run_worker(
            self._stop_process_worker,
            thread=True,
            name="robot-supervisor-stop",
        )

    def on_unmount(self) -> None:
        """Stop supervision when the screen is unmounted."""
        if self._is_running():
            self.stop_supervision()

    def _read_process_output_worker(self) -> None:
        """Read supervisor subprocess output and forward it to the TUI."""
        process = self._process

        if process is None:
            return

        stdout = process.stdout

        if stdout is not None:
            for line in stdout:
                clean_line = line.rstrip()
                if clean_line:
                    self._call_from_worker_thread(self._append_log, clean_line)

        exit_code = process.wait()

        if self._stopping:
            self._call_from_worker_thread(
                self._mark_supervision_stopped,
                f"Status: supervision arrêtée. Code retour : {exit_code}",
            )
            return

        if exit_code == 0:
            self._call_from_worker_thread(
                self._mark_supervision_stopped,
                "Status: supervision terminée normalement.",
            )
            return

        self._call_from_worker_thread(
            self._mark_supervision_failed,
            f"Status: supervision terminée en erreur. Code retour : {exit_code}",
        )

    def _stop_process_worker(self) -> None:
        """Terminate the supervisor process from a background worker."""
        process = self._process

        if process is None or process.poll() is not None:
            self._call_from_worker_thread(
                self._mark_supervision_stopped,
                "Status: supervision arrêtée.",
            )
            return

        try:
            self._terminate_process(process)
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self._call_from_worker_thread(
                self._append_log,
                "[red]Le process ne répond pas, kill forcé.[/]",
            )
            process.kill()
            process.wait(timeout=5)
        except OSError as exc:
            self._call_from_worker_thread(
                self._mark_supervision_failed,
                f"Status: erreur pendant l'arrêt : {exc}",
            )

    def _terminate_process(self, process: subprocess.Popen[str]) -> None:
        """Terminate process using the most appropriate platform strategy."""
        if os.name == "nt":
            process.terminate()
            return

        process_group_id = os.getpgid(process.pid)
        os.killpg(process_group_id, signal.SIGTERM)

    def _get_process_creation_flags(self) -> int:
        """Return subprocess creation flags for the current platform."""
        if os.name == "nt":
            return subprocess.CREATE_NEW_PROCESS_GROUP

        return 0

    def _build_supervisor_command(self, script_path: Path) -> list[str]:
        """Build supervisor subprocess command."""
        command = [
            sys.executable,
            str(script_path),
            "--store",
            str(self.config.store),
            "--task",
            self.config.task,
            "--module",
            self.config.module,
            "--mastership-retries",
            str(self.config.mastership_retries),
            "--log-level",
            self.config.log_level,
        ]

        if self.config.env_file is not None:
            command.extend(["--env-file", str(self.config.env_file)])

        if self.config.env_override:
            command.append("--env-override")

        if self.config.host is not None:
            command.extend(["--host", self.config.host])

        if self.config.username is not None:
            command.extend(["--username", self.config.username])

        if self.config.password is not None:
            command.extend(["--password", self.config.password])

        if self.config.port is not None:
            command.extend(["--port", str(self.config.port)])

        if self.config.timeout is not None:
            command.extend(["--timeout", str(self.config.timeout)])

        return command

    def _get_project_root(self) -> Path:
        """Return the repository root."""
        return Path(__file__).resolve().parents[3]

    def _get_supervisor_script_path(self) -> Path:
        """Return the supervisor script path."""
        return self._get_project_root() / "scripts" / "run_trajcenter_supervisor.py"

    def _is_running(self) -> bool:
        """Return whether the supervisor process is currently running."""
        return self._process is not None and self._process.poll() is None

    def _set_running_ui(self) -> None:
        """Update widgets when supervision starts."""
        button = self.query_one("#start-robot-button", Button)
        button.label = "Arrêter la supervision"
        button.remove_class("robot-start-button")
        button.add_class("robot-stop-button")
        self._set_status_text(self._build_running_text())

    def _set_stopped_ui(self, status_message: str) -> None:
        """Update widgets when supervision stops."""
        button = self.query_one("#start-robot-button", Button)
        button.label = "Démarrer la supervision"
        button.remove_class("robot-stop-button")
        button.add_class("robot-start-button")
        self._stopping = False
        self._process = None
        self._set_status(status_message)

    def _mark_supervision_failed(self, status_message: str) -> None:
        """Mark supervision as failed."""
        self._set_stopped_ui(status_message)
        self._append_log(f"[red]{status_message}[/]")

    def _mark_supervision_stopped(self, status_message: str) -> None:
        """Mark supervision as stopped."""
        self._set_stopped_ui(status_message)
        self._append_log(f"[yellow]{status_message}[/]")

    def _set_status(self, message: str) -> None:
        """Update status widget with plain text."""
        self.query_one("#robot-status", Static).update(message)

    def _set_status_text(self, text: Text) -> None:
        """Update status widget with rich text."""
        self.query_one("#robot-status", Static).update(text)

    def _append_log(self, message: str) -> None:
        """Append a line to the log widget."""
        self.query_one("#robot-log", RichLog).write(message)

    def _clear_log(self) -> None:
        """Clear the log widget."""
        self.query_one("#robot-log", RichLog).clear()

    def _call_from_worker_thread(
        self,
        callback: Callable[..., None],
        *args: Any,
    ) -> None:
        """Call a UI callback from a Textual worker thread."""
        app = cast("App[None]", self.app)
        app.call_from_thread(callback, *args)

    def _build_running_text(self) -> Text:
        """Build running status text."""
        text = Text()
        text.append("Status: ", style="bold white")
        text.append("supervision en cours", style="bold #22C55E")
        text.append(" — bouton Arrêter ou touche X pour stopper.", style="#F4F4F5")
        return text
