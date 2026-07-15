#!/usr/bin/env python3
# trajcenter/exporter/csv_exporter.py
"""CSV exporter — produces 4 files in a destination directory.

Author: Clement RACINET
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from trajcenter.exporter.options import ExportOptions
from trajcenter.exporter.tabular_exporter import _TabularExporter


class CsvExporter(_TabularExporter):
    """Export a trajectory to 4 CSV files in a directory.

    Produced files (``stem`` = ``trajectory.meta.name``):

    - ``{stem}.csv``       : trajectory points.
    - ``{stem}_tools.csv`` : tool name table.
    - ``{stem}_wobjs.csv`` : wobj name table.
    - ``{stem}_meta.csv``  : key/value metadata
      (only when ``options.include_meta=True``).

    Example:
        ::

            from trajcenter.exporter.csv_exporter import CsvExporter

            CsvExporter().export(traj, dest_dir=Path("exports/"))
    """

    def __init__(self, options: ExportOptions | None = None) -> None:
        """Initialise the CSV exporter.

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
        """Write the 4 CSV files.

        Args:
            stem: Base name for the files (without extension).
            dest_dir: Destination directory.
            traj_df: Points ``DataFrame``.
            tools_df: Tools ``DataFrame``.
            wobjs_df: Wobjs ``DataFrame``.
            meta_df: Metadata ``DataFrame``, or ``None`` when
                ``options.include_meta`` is ``False``.

        Returns:
            Path of the main file ``{stem}.csv``.
        """
        sep = self.options.csv_separator
        enc = self.options.csv_encoding

        main = dest_dir / f"{stem}.csv"

        traj_df.to_csv(main, sep=sep, encoding=enc, index=False)
        tools_df.to_csv(
            dest_dir / f"{stem}_tools.csv", sep=sep, encoding=enc, index=False
        )
        wobjs_df.to_csv(
            dest_dir / f"{stem}_wobjs.csv", sep=sep, encoding=enc, index=False
        )

        if meta_df is not None:
            meta_df.to_csv(
                dest_dir / f"{stem}_meta.csv", sep=sep, encoding=enc, index=False
            )

        return main
