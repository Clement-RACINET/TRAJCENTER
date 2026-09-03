# trajcenter/convert/__init__.py
"""Public conversion API for TrajCenter.

This package is the preferred public import path for conversion features.

The legacy :mod:`trajcenter.converter` package remains available temporarily
for backward compatibility.
"""

from __future__ import annotations

from trajcenter.converter import (
    COLUMN_ALIASES,
    AptConverter,
    BaseConverter,
    ConversionDefaults,
    CsvConverter,
    ExcelConverter,
    ModConverter,
    canonical_name,
    resolve_columns,
)

__all__ = [
    "COLUMN_ALIASES",
    "AptConverter",
    "BaseConverter",
    "ConversionDefaults",
    "CsvConverter",
    "ExcelConverter",
    "ModConverter",
    "canonical_name",
    "resolve_columns",
]
