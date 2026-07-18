#!/usr/bin/env python3
# trajcenter/exporter/csv_exporter.py
"""CSV exporter for TrajCenter v2 trajectories.

Author: Clement RACINET

The exporter writes one mandatory trajectory CSV file and optional
sidecar CSV files:

- ``{stem}.csv``: trajectory points.
- ``{stem}_meta.csv``: key/value metadata, only when
  ``options.include_meta`` is ``True``.
- ``{stem}_process_params.csv``: process parameter table, only when the
  trajectory has process parameters.

Legacy v1 ``tools`` and ``wobjs`` sidecar files are no longer produced.
Tool and work-object names are exported inline through ``tool_name`` and
``wobj_name`` when these columns exist in ``trajectory.points``.

ABB Route:
    N/A — local CSV export, no RWS route.

ABB Constraints:
    No mastership is acquired. No RAPID variable is read or written.
    The RWS inactive-axis sentinel ``9E+9`` is never exported.

Example:
    ::

        from pathlib import Path
        from trajcenter.exporter.csv_exporter import CsvExporter

        CsvExporter().export(traj, Path("trajectory_exports"))
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from trajcenter.exporter.options import ExportOptions
from trajcenter.exporter.tabular_exporter import _TabularExporter


class CsvExporter(_TabularExporter):
    """Export a trajectory to CSV files.

    ABB Route:
        N/A — local CSV export.

    ABB Constraints:
        No ABB controller access.

    Attributes:
        options: Export options.

    Example:
        ::

            from pathlib import Path
            from trajcenter.exporter.csv_exporter import CsvExporter

            CsvExporter().export(traj, dest_dir=Path("exports"))
    """

    def __init__(self, options: ExportOptions | None = None) -> None:
        """Initialise the CSV exporter.

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

                exporter = CsvExporter(options=ExportOptions())
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
        """Write trajectory CSV and optional sidecar files.

        ABB Route:
            N/A — local CSV write.

        ABB Constraints:
            No ABB controller access.

        Args:
            stem: Base name for the files, without extension.
            dest_dir: Destination directory.
            traj_df: Points DataFrame.
            meta_df: Metadata DataFrame, or ``None`` when
                ``options.include_meta`` is ``False``.
            process_params_df: Process parameter DataFrame, or ``None``
                when the trajectory has no process parameter table.

        Returns:
            Path of the main file ``{stem}.csv``.

        Raises:
            OSError: If an output file cannot be written.

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
        sep = self.options.csv_separator
        enc = self.options.csv_encoding

        main = dest_dir / f"{stem}.csv"
        traj_df.to_csv(main, sep=sep, encoding=enc, index=False)

        if meta_df is not None:
            meta_df.to_csv(
                dest_dir / f"{stem}_meta.csv",
                sep=sep,
                encoding=enc,
                index=False,
            )

        if process_params_df is not None:
            process_params_df.to_csv(
                dest_dir / f"{stem}_process_params.csv",
                sep=sep,
                encoding=enc,
                index=False,
            )

        return main
