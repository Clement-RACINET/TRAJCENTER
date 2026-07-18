#!/usr/bin/env python3
# trajcenter/converter/csv_converter.py
"""Converter for CSV and delimited text files to ``.trajcenter``.

Author: Clement RACINET

Delegates all conversion logic to
:class:`~trajcenter.converter.tabular_converter._TabularConverter`.
This class only implements CSV file reading with automatic separator
detection.

TrajCenter v2 mapping
---------------------
The converter imports human-readable tabular columns into canonical v2
trajectory columns:

- ``speed`` / ``v500`` / numeric speed aliases -> ``tcp_speed``.
- ``zone`` / ``z10`` -> ``zone_type=10``.
- ``zone`` / ``fine`` -> ``zone_type=255``.
- ``tool`` / tool aliases -> ``tool_name``.
- ``wobj`` / work-object aliases -> ``wobj_name``.

Legacy index columns such as ``tool_index`` and ``wobj_index`` are not
part of the v2 output.

Unmapped columns
----------------
Columns that cannot be mapped to the TrajCenter v2 schema are not stored
in ``Trajectory.points``. A ``UserWarning`` is emitted and their names are
recorded in ``Trajectory.meta.extra["unmapped_columns"]`` for audit.

Separator
---------
The separator is detected automatically via :func:`_detect_separator`
by reading the first non-empty lines of the file. Supported delimiters
are comma, semicolon, tab and pipe. If detection fails, comma is used.

The separator can also be forced via the ``separator`` constructor
parameter.

Encoding
--------
The default encoding is ``"utf-8-sig"``, which supports UTF-8 files with
or without a BOM. It can be overridden via the ``encoding`` parameter.

ABB Route:
    N/A — local CSV file conversion, no RWS route.

ABB Constraints:
    No mastership is acquired. No RAPID variable is read or written.

Example:
    ::

        from pathlib import Path
        from trajcenter.converter.csv_converter import CsvConverter

        traj = CsvConverter().convert(Path("data/trajectoire.csv"))

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

    Reads the first non-empty lines and uses :class:`csv.Sniffer` to
    identify the delimiter. If detection fails or returns an unsupported
    separator, comma is used.

    ABB Route:
        N/A — local file inspection.

    ABB Constraints:
        No ABB controller access.

    Args:
        source: Path to the CSV file.
        encoding: Encoding to use when reading. ``"utf-8-sig"`` handles
            UTF-8 files with or without BOM.

    Returns:
        Detected separator among ``","``, ``";"``, ``"\\t"`` and ``"|"``.
        Returns ``","`` when detection fails.

    Raises:
        None. Detection errors are intentionally swallowed and replaced by
        the comma fallback.

    Example:
        ::

            separator = _detect_separator(Path("trajectory.csv"))
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

    The class inherits all v2 tabular conversion rules from
    :class:`~trajcenter.converter.tabular_converter._TabularConverter` and
    only implements CSV reading, separator detection and encoding handling.

    ABB Route:
        N/A — local CSV file conversion.

    ABB Constraints:
        No ABB controller access.

    Attributes:
        defaults: Optional conversion defaults used only for missing optional
            v2 columns.
        separator: Forced CSV separator. When ``None``, auto-detection is
            used.
        encoding: Source file encoding. Defaults to ``"utf-8-sig"``.

    Example:
        ::

            from pathlib import Path
            from trajcenter.converter.csv_converter import CsvConverter

            traj = CsvConverter().convert(Path("trajectoire.csv"))
            traj = CsvConverter(separator=";").convert(Path("export.csv"))
    """

    def __init__(
        self,
        defaults: ConversionDefaults | None = None,
        separator: str | None = None,
        encoding: str = "utf-8-sig",
    ) -> None:
        """Initialise the CSV converter.

        ABB Route:
            N/A.

        ABB Constraints:
            No ABB controller access.

        Args:
            defaults: Default values for optional v2 columns. When ``None``,
                no optional process column is added unless present in the source.
            separator: Forced CSV separator. When ``None``, auto-detection is
                used.
            encoding: Source file encoding. Defaults to ``"utf-8-sig"``.

        Returns:
            None.

        Raises:
            pydantic.ValidationError: If defaults are invalid.

        Example:
            ::

                converter = CsvConverter(separator=";", encoding="utf-8-sig")
        """
        super().__init__(defaults)
        self.separator: str | None = separator
        self.encoding: str = encoding

    @property
    def _source_format(self) -> SourceFormat:
        """Return the source format identifier for CSV imports.

        ABB Route:
            N/A.

        ABB Constraints:
            No ABB controller access.

        Args:
            None.

        Returns:
            :attr:`trajcenter.core.trajectory.SourceFormat.CSV`.

        Raises:
            None.

        Example:
            ::

                assert converter._source_format == SourceFormat.CSV
        """
        return SourceFormat.CSV

    def _read_sheets(self, source: Path) -> dict[str, pd.DataFrame]:
        """Read the CSV file and expose it as a single tabular sheet.

        The separator is detected automatically unless explicitly configured.

        ABB Route:
            N/A — local CSV file read.

        ABB Constraints:
            No ABB controller access.

        Args:
            source: Path to the CSV file.

        Returns:
            Dictionary ``{"sheet": raw_dataframe}``.

        Raises:
            FileNotFoundError: If the CSV path does not exist.
            pandas.errors.ParserError: If pandas cannot parse the CSV content.
            UnicodeDecodeError: If the configured encoding is invalid for the
                file content.

        Example:
            ::

                sheets = converter._read_sheets(Path("trajectory.csv"))
        """
        sep = self.separator or _detect_separator(source, encoding=self.encoding)
        df = pd.read_csv(
            source,
            sep=sep,
            encoding=self.encoding,
            header=0,
        )
        return {"sheet": df}
