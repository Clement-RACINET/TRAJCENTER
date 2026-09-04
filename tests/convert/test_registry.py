#!/usr/bin/env python3
"""Tests for converter registry helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from trajcenter.convert.apt_converter import AptConverter
from trajcenter.convert.csv_converter import CsvConverter
from trajcenter.convert.excel_converter import ExcelConverter
from trajcenter.convert.mod_converter import ModConverter
from trajcenter.convert.registry import infer_converter


@pytest.mark.parametrize(
    ("source", "format_name", "expected_type"),
    [
        (Path("demo.csv"), None, CsvConverter),
        (Path("demo.txt"), None, CsvConverter),
        (Path("demo.xlsx"), None, ExcelConverter),
        (Path("demo.xlsm"), None, ExcelConverter),
        (Path("demo.xls"), None, ExcelConverter),
        (Path("demo.apt"), None, AptConverter),
        (Path("demo.aptsource"), None, AptConverter),
        (Path("demo.mod"), None, ModConverter),
        (Path("demo.unknown"), "csv", CsvConverter),
        (Path("demo.unknown"), "excel", ExcelConverter),
        (Path("demo.unknown"), "xlsx", ExcelConverter),
        (Path("demo.unknown"), "apt", AptConverter),
        (Path("demo.unknown"), "rapid", ModConverter),
        (Path("demo.unknown"), "mod", ModConverter),
    ],
)
def test_infer_converter(source, format_name, expected_type):
    """infer_converter should select the expected converter."""
    converter = infer_converter(source, format_name)

    assert isinstance(converter, expected_type)


def test_infer_converter_rejects_unknown_auto_format():
    """infer_converter should reject unknown extensions in automatic mode."""
    with pytest.raises(ValueError, match="Unsupported source format"):
        infer_converter(Path("demo.unknown"))


def test_infer_converter_rejects_unknown_explicit_format():
    """infer_converter should reject unknown explicit formats."""
    with pytest.raises(ValueError, match="Unsupported source format"):
        infer_converter(Path("demo.csv"), "bad")
