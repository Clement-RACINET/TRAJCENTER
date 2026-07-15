#!/usr/bin/env python3
# trajcenter/converter/csv_converter.py
"""Converter for CSV / delimited text files to ``.trajcenter``.

Author: Clement RACINET

Delegates all conversion logic to
:class:`~trajcenter.converter.tabular_converter._TabularConverter`.
This class only implements CSV file reading with automatic separator
detection (comma ``,`` or semicolon ``;``).

Separator
----------
The separator is detected automatically via :func:`_detect_separator`
by reading the first 4 lines of the file. If detection fails, a comma
is used as the default.

The separator can also be forced via the ``separator`` constructor
parameter.

Encoding
---------
The encoding is detected automatically (UTF-8 with BOM, UTF-8, Latin-1).
It can be forced via the ``encoding`` parameter.

Example:
    ::

        traj = CsvConverter().convert(Path("data/trajectoire.csv"))

        # Force separator and encoding
        traj = CsvConverter(separator=";", encoding="latin-1").convert(
            Path("data/export_excel.csv")
        )
"""

from __future__ import annotations

import csv
from pathlib import Path

import pandas as pd

from trajcenter.converter.defaults import ConversionDefaults
from trajcenter.converter.tabular_converter import _TabularConverter
from trajcenter.core.trajectory import SourceFormat


# ---------------------------------------------------------------------------
# Separator detection
# ---------------------------------------------------------------------------

_CANDIDATE_SEPARATORS: list[str] = [",", ";", "\t", "|"]
_SNIFF_LINES: int = 4


def _detect_separator(source: Path, encoding: str = "utf-8-sig") -> str:
    """Automatically detect the separator of a CSV file.

    Reads the first :data:`_SNIFF_LINES` non-empty lines and uses
    :class:`csv.Sniffer` to identify the delimiter. If detection fails
    or returns a non-standard separator, a comma is used as the default.

    Args:
        source: Path to the CSV file.
        encoding: Encoding to use when reading. ``"utf-8-sig"``
            handles the UTF-8 BOM automatically.

    Returns:
        Detected separator among ``","``, ``";"``, ``"\\t"``, ``"|"``,
        or ``","`` by default.
    """
    try:
        lines: list[str] = []
        with source.open(encoding=encoding, errors="replace") as f:
            for line in f:
                stripped = line.strip()
                if stripped:
                    lines.append(stripped)
                if len(lines) >= _SNIFF_LINES:
                    break

        sample = "\n".join(lines)
        dialect = csv.Sniffer().sniff(sample, delimiters="".join(_CANDIDATE_SEPARATORS))
        return dialect.delimiter if dialect.delimiter in _CANDIDATE_SEPARATORS else ","

    except (csv.Error, UnicodeDecodeError, OSError):
        return ","


# ---------------------------------------------------------------------------
# CSV converter
# ---------------------------------------------------------------------------


class CsvConverter(_TabularConverter):
    """Converter for CSV files to :class:`~trajcenter.core.trajectory.Trajectory`.

    Inherits from
    :class:`~trajcenter.converter.tabular_converter._TabularConverter`
    for all business logic. Only implements CSV reading with automatic
    separator detection.

    Attributes:
        defaults: Default values for autocompletion.
        separator: Forced separator. When ``None``, auto-detection is used.
        encoding: File encoding. Defaults to ``"utf-8-sig"``
            (handles UTF-8 with and without BOM).

    Example:
        ::

            from pathlib import Path
            from trajcenter.converter.csv_converter import CsvConverter

            # Automatic separator detection
            traj = CsvConverter().convert(Path("trajectoire.csv"))

            # Forced separator (French Excel export)
            traj = CsvConverter(separator=";").convert(Path("export.csv"))
    """

    def __init__(
        self,
        defaults: ConversionDefaults | None = None,
        separator: str | None = None,
        encoding: str = "utf-8-sig",
    ) -> None:
        """Initialise the CSV converter.

        Args:
            defaults: Default values for autocompletion.
            separator: Forced CSV separator (``","`` or ``";"`` etc.).
                When ``None``, auto-detection is used.
            encoding: Source file encoding. Defaults to ``"utf-8-sig"``
                (handles the UTF-8 BOM from Excel exports).
        """
        super().__init__(defaults)
        self.separator: str | None = separator
        self.encoding: str = encoding

    @property
    def _source_format(self) -> SourceFormat:
        """Source format identifier for this converter.

        Returns:
            :attr:`~trajcenter.core.trajectory.SourceFormat.CSV`.
        """
        return SourceFormat.CSV

    def _read_sheets(self, source: Path) -> dict[str, pd.DataFrame]:
        """Read the CSV file and return a single ``"sheet"`` entry.

        The separator is detected automatically when not forced.

        Args:
            source: Path to the CSV file.

        Returns:
            Dictionary ``{"sheet": raw_DataFrame}``.
        """
        sep = self.separator or _detect_separator(source, encoding=self.encoding)
        df = pd.read_csv(
            source,
            sep=sep,
            encoding=self.encoding,
            header=0,
        )
        return {"sheet": df}
