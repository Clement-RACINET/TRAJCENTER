#!/usr/bin/env python3
# trajcenter/exporter/options.py
"""Configuration options for tabular exporters.

Author: Clement RACINET
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ExportOptions:
    """Configuration options for tabular exporters.

    Attributes:
        float_precision: Number of decimal places for floating-point
            numeric columns.
        csv_separator: Column separator for the CSV format.
        csv_encoding: CSV file encoding.
            ``utf-8-sig`` includes a BOM, which allows Excel to open
            the file without encoding issues.
        include_meta: When ``True``, a ``meta`` sheet / file is
            produced with the trajectory metadata.
    """

    float_precision: int = 6
    csv_separator: str = ","
    csv_encoding: str = "utf-8-sig"
    include_meta: bool = True
