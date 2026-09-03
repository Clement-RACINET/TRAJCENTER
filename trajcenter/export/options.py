#!/usr/bin/env python3
# trajcenter/export/options.py
"""Configuration options for tabular exporters.

> **Author**: Clément RACINET
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ExportOptions:
    """Configuration options for tabular exporters.

    ABB Route:
        N/A — local file export, no RWS route.

    ABB Constraints:
        No mastership is acquired. No RAPID variable is read or written.

    Attributes:
        float_precision: Number of decimal places for floating-point
            numeric columns.
        csv_separator: Column separator for the CSV format.
        csv_encoding: CSV file encoding. ``utf-8-sig`` includes a BOM,
            which allows Excel to open the file without encoding issues.
        include_meta: When ``True``, a ``meta`` sheet or ``*_meta.csv``
            file is produced with the trajectory metadata.
        export_columns: Optional explicit column selection.

            Rules:
                - ``None``: export default known v2 columns that are
                  present in ``trajectory.points``.
                - ``("*",)``: export all columns present in
                  ``trajectory.points``.
                - ``("default", "col_a")``: export default known v2
                  columns plus the named columns if present.
                - Any other tuple: export exactly those columns if
                  present, in the requested order.

    Example:
        ::

            options = ExportOptions(export_columns=("default", "tcp_speed"))
    """

    float_precision: int = 6
    csv_separator: str = ","
    csv_encoding: str = "utf-8-sig"
    include_meta: bool = True
    export_columns: tuple[str, ...] | None = None
