#!/usr/bin/env python3
"""Tests for the TrajCenter settings Textual screen."""

from __future__ import annotations

from pathlib import Path

import pytest

from trajcenter.ui.config import UIConfig
from trajcenter.ui.screens.settings import (
    SettingsScreen,
    build_settings_error_text,
    build_settings_success_text,
    parse_optional_float,
    parse_optional_int,
    parse_optional_string,
    parse_required_int,
    parse_required_non_empty,
)


def test_settings_screen_uses_provided_config(tmp_path: Path) -> None:
    """SettingsScreen should keep the provided UI configuration."""
    config = UIConfig(store=tmp_path)

    screen = SettingsScreen(config)

    assert screen.config is config


def test_parse_optional_string() -> None:
    """parse_optional_string should return None for blank values."""
    assert parse_optional_string("") is None
    assert parse_optional_string("   ") is None
    assert parse_optional_string("robot") == "robot"
    assert parse_optional_string("  robot  ") == "robot"


def test_parse_optional_int() -> None:
    """parse_optional_int should parse integers or return None."""
    assert parse_optional_int("", "Port") is None
    assert parse_optional_int("  ", "Port") is None
    assert parse_optional_int("80", "Port") == 80


def test_parse_optional_int_rejects_invalid_value() -> None:
    """parse_optional_int should reject invalid integer strings."""
    with pytest.raises(ValueError, match="Port must be an integer"):
        parse_optional_int("abc", "Port")


def test_parse_required_int() -> None:
    """parse_required_int should parse valid integers."""
    assert parse_required_int("3", "Retries") == 3


def test_parse_required_int_rejects_blank_value() -> None:
    """parse_required_int should reject blank values."""
    with pytest.raises(ValueError, match="Retries is required"):
        parse_required_int("", "Retries")


def test_parse_optional_float() -> None:
    """parse_optional_float should parse floats or return None."""
    assert parse_optional_float("", "Timeout") is None
    assert parse_optional_float("  ", "Timeout") is None
    assert parse_optional_float("5.5", "Timeout") == 5.5
    assert parse_optional_float("5,5", "Timeout") == 5.5


def test_parse_optional_float_rejects_invalid_value() -> None:
    """parse_optional_float should reject invalid float strings."""
    with pytest.raises(ValueError, match="Timeout must be a number"):
        parse_optional_float("abc", "Timeout")


def test_parse_required_non_empty() -> None:
    """parse_required_non_empty should return stripped values."""
    assert parse_required_non_empty(" T_ROB1 ", "Task") == "T_ROB1"


def test_parse_required_non_empty_rejects_blank_value() -> None:
    """parse_required_non_empty should reject empty values."""
    with pytest.raises(ValueError, match="Task is required"):
        parse_required_non_empty("", "Task")


def test_build_settings_success_text() -> None:
    """build_settings_success_text should contain an OK status."""
    text = build_settings_success_text()

    assert "OK" in text.plain
    assert "Paramètres appliqués" in text.plain


def test_build_settings_error_text() -> None:
    """build_settings_error_text should include the error message."""
    text = build_settings_error_text(ValueError("bad settings"))

    assert "Erreur" in text.plain
    assert "bad settings" in text.plain


def test_apply_settings_updates_config(tmp_path: Path) -> None:
    """SettingsScreen.apply_settings should update the shared configuration."""
    config = UIConfig()
    screen = SettingsScreen(config)
    store = tmp_path / "store"
    env_file = tmp_path / ".env"

    screen.apply_settings(
        store=store,
        env_file=env_file,
        host="192.168.125.1",
        port=80,
        username="Default User",
        password_env="TRAJCENTER_PASSWORD",
        timeout=10.0,
        task="T_ROB2",
        module="MY_MODULE",
        mastership_retries=5,
        log_level="DEBUG",
    )

    assert config.store == store
    assert config.env_file == env_file
    assert config.host == "192.168.125.1"
    assert config.port == 80
    assert config.username == "Default User"
    assert config.password_env == "TRAJCENTER_PASSWORD"
    assert config.timeout == 10.0
    assert config.task == "T_ROB2"
    assert config.module == "MY_MODULE"
    assert config.mastership_retries == 5
    assert config.log_level == "DEBUG"
