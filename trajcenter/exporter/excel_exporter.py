#!/usr/bin/env python3
# trajcenter/exporter/excel_exporter.py
"""Excel exporter — produces a single ``.xlsx`` file with up to 4 sheets.

Author: Clement RACINET
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from trajcenter.exporter.options import ExportOptions
from trajcenter.exporter.tabular_exporter import _TabularExporter


class ExcelExporter(_TabularExporter):
    """Export a trajectory to a ``.xlsx`` file.

    The produced file contains up to 4 sheets:

    - ``traj``  : trajectory points (tool/wobj resolved to names).
    - ``tools`` : tool name table.
    - ``wobjs`` : wobj name table.
    - ``meta``  : key/value metadata
      (only when ``options.include_meta=True``).

    This format is directly re-readable by
    :class:`~trajcenter.converter.excel_converter.ExcelConverter`.

    Example:
        ::

            from trajcenter.exporter.excel_exporter import ExcelExporter

            ExcelExporter().export(traj, dest_dir=Path("exports/"))
    """

    def __init__(self, options: ExportOptions | None = None) -> None:
        """Initialise the Excel exporter.

        Args:
            options: Export options. When ``None``,
                :class:`~trajcenter.exporter.options.ExportOptions`
                is instantiated with its own default values.
        """
        super().__init__(options)

    def _write_sheets(
        self,
        stem: str,
        dest_dir: Path,
        traj_df: pd.DataFrame,
        tools_df: pd.DataFrame,
        wobjs_df: pd.DataFrame,
        meta_df: pd.DataFrame | None,
    ) -> Path:
        """Write the ``.xlsx`` file with up to 4 sheets.

        Args:
            stem: Base name for the file (without extension).
            dest_dir: Destination directory.
            traj_df: Points ``DataFrame``.
            tools_df: Tools ``DataFrame``.
            wobjs_df: Wobjs ``DataFrame``.
            meta_df: Metadata ``DataFrame``, or ``None`` when
                ``options.include_meta`` is ``False``.

        Returns:
            Path of the produced ``.xlsx`` file.
        """
        dest = dest_dir / f"{stem}.xlsx"

        with pd.ExcelWriter(dest, engine="openpyxl") as writer:
            traj_df.to_excel(writer, sheet_name="traj", index=False)
            tools_df.to_excel(writer, sheet_name="tools", index=False)
            wobjs_df.to_excel(writer, sheet_name="wobjs", index=False)
            if meta_df is not None:
                meta_df.to_excel(writer, sheet_name="meta", index=False)

        return dest
