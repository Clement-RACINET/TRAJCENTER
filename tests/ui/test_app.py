"""Tests for the simple TrajCenter terminal UI."""

from __future__ import annotations

from pathlib import Path

from trajcenter.ui.app import run_ui
from trajcenter.ui.config import UIConfig


def test_run_ui_quit(monkeypatch, capsys):
    """The UI should exit cleanly when the user selects quit."""
    monkeypatch.setattr("builtins.input", lambda _prompt: "q")

    result = run_ui(UIConfig(store=Path("trajectory_store")))

    captured = capsys.readouterr()

    assert result == 0
    assert "Main menu" in captured.out
    assert "File conversion / trajectory store" in captured.out
    assert "Robot communication / ABB RWS" in captured.out
