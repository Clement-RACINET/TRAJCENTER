#!/usr/bin/env python3
# tests/export/test_public_api.py
"""Tests for the public export API facade."""

from __future__ import annotations

from trajcenter import export
from trajcenter.exporter import BaseExporter, CsvExporter, ExcelExporter, ExportOptions


def test_export_facade_reexports_exporter_public_api() -> None:
    """The new public export API re-exports the legacy exporter API."""
    assert export.BaseExporter is BaseExporter
    assert export.CsvExporter is CsvExporter
    assert export.ExcelExporter is ExcelExporter
    assert export.ExportOptions is ExportOptions


def test_export_all_contains_expected_public_names() -> None:
    """The public export API exposes the expected symbol list."""
    assert export.__all__ == [
        "BaseExporter",
        "CsvExporter",
        "ExcelExporter",
        "ExportOptions",
    ]
