#!/usr/bin/env python3
"""Tests for the TrajCenter conversion Textual screen."""

from __future__ import annotations

from textual.widgets import Select

from trajcenter.ui.config import UIConfig
from trajcenter.ui.screens.convert import (
    ConvertScreen,
    build_conversion_error_text,
    build_conversion_success_text,
    normalize_convert_format,
    normalize_optional_stem,
)


def test_convert_screen_uses_provided_config(tmp_path):
    """ConvertScreen should keep the provided UI configuration."""
    config = UIConfig(store=tmp_path)

    screen = ConvertScreen(config)

    assert screen.config is config


def test_normalize_convert_format_auto_values():
    """normalize_convert_format should return None for auto-like values."""
    assert normalize_convert_format(None) is None
    assert normalize_convert_format(Select.BLANK) is None
    assert normalize_convert_format("auto") is None


def test_normalize_convert_format_explicit_value():
    """normalize_convert_format should return explicit format strings."""
    assert normalize_convert_format("csv") == "csv"
    assert normalize_convert_format("excel") == "excel"
    assert normalize_convert_format("mod") == "mod"


def test_normalize_optional_stem():
    """normalize_optional_stem should return None when the stem is blank."""
    assert normalize_optional_stem("") is None
    assert normalize_optional_stem("   ") is None
    assert normalize_optional_stem("demo") == "demo"
    assert normalize_optional_stem("  demo  ") == "demo"


def test_build_conversion_success_text(tmp_path):
    """build_conversion_success_text should include the output path."""
    output = tmp_path / "demo.trajcenter"

    text = build_conversion_success_text(output)

    assert "OK" in text.plain
    assert str(output) in text.plain


def test_build_conversion_error_text():
    """build_conversion_error_text should include the error message."""
    text = build_conversion_error_text(ValueError("bad conversion"))

    assert "Erreur" in text.plain
    assert "bad conversion" in text.plain


def test_convert_screen_convert_file(monkeypatch, tmp_path):
    """ConvertScreen.convert_file should infer a converter and save the archive."""
    source = tmp_path / "input.csv"
    dest_dir = tmp_path / "store"
    output = dest_dir / "demo.trajcenter"
    calls = {}

    class FakeConverter:
        def convert_and_save(self, source, dest_dir, stem=None):
            calls["source"] = source
            calls["dest_dir"] = dest_dir
            calls["stem"] = stem
            return output

    def fake_infer_converter(source_arg, format_name=None):
        calls["infer_source"] = source_arg
        calls["format_name"] = format_name
        return FakeConverter()

    monkeypatch.setattr(
        "trajcenter.ui.screens.convert.infer_converter",
        fake_infer_converter,
    )

    screen = ConvertScreen(UIConfig(store=dest_dir))

    result = screen.convert_file(
        source=source,
        dest_dir=dest_dir,
        stem="demo",
        format_name="csv",
    )

    assert result == output
    assert calls == {
        "infer_source": source,
        "format_name": "csv",
        "source": source,
        "dest_dir": dest_dir,
        "stem": "demo",
    }
