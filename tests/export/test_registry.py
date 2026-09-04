#!/usr/bin/env python3
"""Tests for exporter registry helpers."""

from __future__ import annotations

import pytest

from trajcenter.export.csv_exporter import CsvExporter
from trajcenter.export.excel_exporter import ExcelExporter
from trajcenter.export.registry import infer_exporter


@pytest.mark.parametrize(
    ("format_name", "expected_type"),
    [
        ("csv", CsvExporter),
        ("excel", ExcelExporter),
        ("xlsx", ExcelExporter),
    ],
)
def test_infer_exporter(format_name, expected_type):
    """infer_exporter should select the expected exporter."""
    exporter = infer_exporter(format_name)

    assert isinstance(exporter, expected_type)


def test_infer_exporter_rejects_unknown_format():
    """infer_exporter should reject unsupported formats."""
    with pytest.raises(ValueError, match="Unsupported export format"):
        infer_exporter("bad")
