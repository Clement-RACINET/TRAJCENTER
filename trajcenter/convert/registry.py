"""Converter registry helpers.

This module contains converter selection logic shared by the CLI and the TUI.
"""

from __future__ import annotations

from pathlib import Path

from trajcenter.convert.apt_converter import AptConverter
from trajcenter.convert.base import BaseConverter
from trajcenter.convert.csv_converter import CsvConverter
from trajcenter.convert.excel_converter import ExcelConverter
from trajcenter.convert.mod_converter import ModConverter

CSV_EXTENSIONS = {".csv", ".txt"}
EXCEL_EXTENSIONS = {".xlsx", ".xlsm", ".xls"}
APT_EXTENSIONS = {".apt", ".aptsource"}
RAPID_EXTENSIONS = {".mod"}


def infer_converter(source: Path, format_name: str | None = None) -> BaseConverter:
    """Return a converter instance for a source file.

    Args:
        source: Source file path.
        format_name: Optional explicit source format.

    Returns:
        Converter instance.

    Raises:
        ValueError: If the format is unsupported.
    """
    normalized_format = format_name.casefold() if format_name is not None else None
    suffix = source.suffix.casefold()

    if normalized_format == "csv" or (
        normalized_format is None and suffix in CSV_EXTENSIONS
    ):
        return CsvConverter()

    if normalized_format in {"excel", "xlsx"} or (
        normalized_format is None and suffix in EXCEL_EXTENSIONS
    ):
        return ExcelConverter()

    if normalized_format == "apt" or (
        normalized_format is None and suffix in APT_EXTENSIONS
    ):
        return AptConverter()

    if normalized_format in {"rapid", "mod"} or (
        normalized_format is None and suffix in RAPID_EXTENSIONS
    ):
        return ModConverter()

    supported = ", ".join(
        sorted(CSV_EXTENSIONS | EXCEL_EXTENSIONS | APT_EXTENSIONS | RAPID_EXTENSIONS)
    )
    raise ValueError(
        f"Unsupported source format for {source}. "
        f"Supported extensions: {supported}. "
        "Use --format to override detection."
    )
