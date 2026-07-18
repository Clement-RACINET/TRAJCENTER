#!/usr/bin/env python3
# trajcenter/exporter/excel_exporter.py
"""Excel exporter for TrajCenter v2 trajectories.

Author: Clement RACINET

The exporter writes a single ``.xlsx`` workbook containing:

- ``traj``: trajectory points.
- ``meta``: optional key/value metadata when ``options.include_meta`` is
  ``True``.

Legacy v1 ``tools`` and ``wobjs`` sheets are no longer produced. Tool and
work-object names are exported inline through ``tool_name`` and
``wobj_name`` when these columns exist in ``trajectory.points``.

ABB Route:
    N/A — local Excel export, no RWS route.

ABB Constraints:
    No mastership is acquired. No RAPID variable is read or written.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from trajcenter.exporter.options import ExportOptions
from trajcenter.exporter.tabular_exporter import _TabularExporter


class ExcelExporter(_TabularExporter):
    """Export a trajectory to an Excel workbook.

    ABB Route:
        N/A — local Excel export.

    ABB Constraints:
        No ABB controller access.

    Attributes:
        options: Export options.

    Example:
        ::

            from pathlib import Path
            from trajcenter.exporter.excel_exporter import ExcelExporter

            ExcelExporter().export(traj, dest_dir=Path("exports"))
    """

    def __init__(self, options: ExportOptions | None = None) -> None:
        """Initialise the Excel exporter.

        ABB Route:
            N/A.

        ABB Constraints:
            No ABB controller access.

        Args:
            options: Export options. When ``None``,
                :class:`~trajcenter.exporter.options.ExportOptions`
                is instantiated with its own default values.

        Returns:
            None.

        Raises:
            None.

        Example:
            ::

                exporter = ExcelExporter(options=ExportOptions())
        """
        super().__init__(options)

    def _write_sheets(
        self,
        stem: str,
        dest_dir: Path,
        traj_df: pd.DataFrame,
        meta_df: pd.DataFrame | None,
    ) -> Path:
        """Write the Excel workbook.

        ABB Route:
            N/A — local Excel write.

        ABB Constraints:
            No ABB controller access.

        Args:
            stem: Base name for the file, without extension.
            dest_dir: Destination directory.
            traj_df: Points DataFrame.
            meta_df: Metadata DataFrame, or ``None`` when
                ``options.include_meta`` is ``False``.

        Returns:
            Path of the produced ``.xlsx`` file.

        Raises:
            OSError: If the workbook cannot be written.

        Example:
            ::

                path = exporter._write_sheets("traj", dest, traj_df, meta_df)
        """
        dest = dest_dir / f"{stem}.xlsx"

        with pd.ExcelWriter(dest, engine="openpyxl") as writer:
            traj_df.to_excel(writer, sheet_name="traj", index=False)
            if meta_df is not None:
                meta_df.to_excel(writer, sheet_name="meta", index=False)

        return dest
