#!/usr/bin/env python3
# trajcenter/export/excel_exporter.py
"""Excel exporter for TrajCenter v2 trajectories.

> **Author**: Clément RACINET

The exporter writes a single ``.xlsx`` workbook containing:

- ``traj``: trajectory points.
- ``meta``: optional key/value metadata when ``options.include_meta`` is
  ``True``.
- ``process_params``: optional process parameter table when the
  trajectory has process parameters.

Legacy v1 ``tools`` and ``wobjs`` sheets are no longer produced. Tool and
work-object names are exported inline through ``tool_name`` and
``wobj_name`` when these columns exist in ``trajectory.points``.

ABB Route:
    N/A — local Excel export, no RWS route.

ABB Constraints:
    No mastership is acquired. No RAPID variable is read or written.
    The RWS inactive-axis sentinel ``9E+9`` is never exported.

Example:
    ::

        from pathlib import Path
        from trajcenter.export.excel_exporter import ExcelExporter

        ExcelExporter().export(traj, Path("trajectory_exports"))
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from trajcenter.export.options import ExportOptions
from trajcenter.export.tabular_exporter import _TabularExporter


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
            from trajcenter.export.excel_exporter import ExcelExporter

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
                :class:`~trajcenter.export.options.ExportOptions`
                is instantiated with its own default values.

        Returns:
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
        process_params_df: pd.DataFrame | None,
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
            process_params_df: Process parameter DataFrame, or ``None``
                when the trajectory has no process parameter table.

        Returns:
            Path of the produced ``.xlsx`` file.

        Raises:
            OSError: If the workbook cannot be written.

        Example:
            ::

                path = exporter._write_sheets(
                    "traj",
                    dest,
                    traj_df,
                    meta_df,
                    process_params_df,
                )
        """
        dest = dest_dir / f"{stem}.xlsx"

        with pd.ExcelWriter(dest, engine="openpyxl") as writer:
            traj_df.to_excel(writer, sheet_name="traj", index=False)
            if meta_df is not None:
                meta_df.to_excel(writer, sheet_name="meta", index=False)

            if process_params_df is not None:
                process_params_df.to_excel(
                    writer,
                    sheet_name="process_params",
                    index=False,
                )

        return dest
