"""Exporter registry helpers.

This module contains exporter selection logic shared by the CLI and the TUI.
"""

from __future__ import annotations

from trajcenter.export.base import BaseExporter
from trajcenter.export.csv_exporter import CsvExporter
from trajcenter.export.excel_exporter import ExcelExporter


def infer_exporter(format_name: str) -> BaseExporter:
    """Return an exporter instance for an output format.

    Args:
        format_name: Export format name.

    Returns:
        Exporter instance.

    Raises:
        ValueError: If the format is unsupported.
    """
    normalized_format = format_name.casefold()

    if normalized_format == "csv":
        return CsvExporter()

    if normalized_format in {"excel", "xlsx"}:
        return ExcelExporter()

    raise ValueError(f"Unsupported export format: {format_name}")
