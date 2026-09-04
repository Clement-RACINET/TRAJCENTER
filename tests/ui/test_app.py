#!/usr/bin/env python3
"""Tests for the TrajCenter Textual UI."""

from __future__ import annotations

from pathlib import Path

from trajcenter.ui.app import TrajCenterTUI, run_tui
from trajcenter.ui.config import UIConfig


def test_run_tui_starts_textual_app(monkeypatch):
    """run_tui should instantiate and run the Textual app."""
    called = False

    def fake_run(self):
        nonlocal called
        called = True

    monkeypatch.setattr(TrajCenterTUI, "run", fake_run)

    result = run_tui(UIConfig(store=Path("trajectory_store")))

    assert result == 0
    assert called is True


def test_trajcenter_tui_uses_provided_config():
    """TrajCenterTUI should keep the provided UI configuration."""
    config = UIConfig(store=Path("trajectory_store"))

    app = TrajCenterTUI(config=config)

    assert app.config is config
