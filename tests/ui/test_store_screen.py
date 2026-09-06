#!/usr/bin/env python3
"""Tests for the TrajCenter store Textual screen."""

from __future__ import annotations

from trajcenter.store.models import TrajectoryStoreEntry
from trajcenter.ui.config import UIConfig
from trajcenter.ui.screens.store import StoreScreen


def test_store_screen_uses_provided_config(tmp_path):
    """StoreScreen should keep the provided UI configuration."""
    config = UIConfig(store=tmp_path)

    screen = StoreScreen(config)

    assert screen.config is config


def test_store_screen_load_entries(monkeypatch, tmp_path):
    """StoreScreen.load_entries should scan the configured store."""
    expected = (
        TrajectoryStoreEntry(
            index=1,
            path=tmp_path / "demo.trajcenter",
            name="demo",
            point_count=42,
            process_type=1,
        ),
    )
    calls = {}

    def fake_scan_trajectory_store(store):
        calls["store"] = store
        return expected

    monkeypatch.setattr(
        "trajcenter.ui.screens.store.scan_trajectory_store",
        fake_scan_trajectory_store,
    )

    screen = StoreScreen(UIConfig(store=tmp_path))

    assert screen.load_entries() == expected
    assert calls["store"] == tmp_path


def test_store_screen_success_text(tmp_path):
    """StoreScreen should format success status text."""
    screen = StoreScreen(UIConfig(store=tmp_path))

    text = screen._success_text(3)

    assert "OK" in text.plain
    assert "3 archive(s)" in text.plain


def test_store_screen_error_text(tmp_path):
    """StoreScreen should format error status text."""
    screen = StoreScreen(UIConfig(store=tmp_path))

    text = screen._error_text(FileNotFoundError("missing store"))

    assert "Erreur" in text.plain
    assert "missing store" in text.plain
