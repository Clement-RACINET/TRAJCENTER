#!/usr/bin/env python3
# trajcenter/exporter/tabular_exporter.py
"""Abstract tabular exporter shared by Excel and CSV exporters.

Author: Clement RACINET

This module factors out the construction of tabular outputs used by CSV
and Excel exporters:

- trajectory points;
- optional key/value metadata;
- optional process parameter table.

TrajCenter v2 export policy
---------------------------
The exporter writes canonical v2 columns. It does not reintroduce v1
tables or index-based tool/work-object references.

Exported send columns keep their internal representation:

- ``tcp_speed`` is numeric, without a RAPID ``v`` prefix.
- ``zone_type`` is numeric. ``255`` represents ``fine``.
- ``tool_name`` and ``wobj_name`` are inline names.
- ``tool_index`` and ``wobj_index`` are never exported by default.
- ``speed`` and ``zone`` legacy aliases are never created.

Process data
------------
When a trajectory has process parameters, tabular exporters write:

- ``process_param_index`` in the trajectory point table;
- ``process_type`` and ``process_param_names`` in the metadata table;
- a process parameter table through the concrete exporter.

Excel writes this table as a ``process_params`` sheet.
CSV writes it as ``{stem}_process_params.csv``.

Column selection
----------------
The :attr:`trajcenter.exporter.options.ExportOptions.export_columns`
option controls the exported point columns:

- ``None`` exports known v2 columns that are present.
- ``("*",)`` exports all columns present in ``trajectory.points``.
- ``("default", "foo")`` exports default known v2 columns plus ``foo``
  when present.
- Any other tuple exports exactly the requested columns when present.

Unknown columns present in ``trajectory.points`` are not exported by
default. A ``UserWarning`` is emitted so the user knows that these
columns were seen but intentionally ignored.

ABB Route:
    N/A — local file export, no RWS route.

ABB Constraints:
    No mastership is acquired. No RAPID variable is read or written.
    The RWS inactive-axis sentinel ``9E+9`` must not be injected by
    exporters.

Example:
    ::

        from pathlib import Path
        from trajcenter.exporter.excel_exporter import ExcelExporter

        ExcelExporter().export(traj, Path("trajectory_exports"))
"""

from __future__ import annotations

import warnings
from abc import abstractmethod
from pathlib import Path

import pandas as pd

from trajcenter.core.trajectory import Trajectory, TrajectoryMeta
from trajcenter.exporter.base import BaseExporter
from trajcenter.exporter.options import ExportOptions

#: Float columns to round at export time.
_FLOAT_COLS: frozenset[str] = frozenset(
    {
        "x",
        "y",
        "z",
        "q1",
        "q2",
        "q3",
        "q4",
        "tcp_speed",
        "eax_a",
        "eax_b",
        "eax_c",
        "eax_d",
        "eax_e",
        "eax_f",
    }
)

#: Mandatory geometry columns in preferred export order.
_REQUIRED_TRAJ_COLS: tuple[str, ...] = (
    "x",
    "y",
    "z",
    "q1",
    "q2",
    "q3",
    "q4",
)

#: Known optional v2 trajectory columns in preferred export order.
_OPTIONAL_TRAJ_COLS: tuple[str, ...] = (
    "cf1",
    "cf4",
    "cf6",
    "cfx",
    "move_type",
    "tcp_speed",
    "zone_type",
    "tool_name",
    "wobj_name",
    "readconfs",
    "process_param_index",
    "eax_a",
    "eax_b",
    "eax_c",
    "eax_d",
    "eax_e",
    "eax_f",
)

#: Default known v2 column order.
_DEFAULT_TRAJ_COL_ORDER: tuple[str, ...] = _REQUIRED_TRAJ_COLS + _OPTIONAL_TRAJ_COLS

#: TrajectoryMeta fields to skip at export time.
_META_SKIP_FIELDS: frozenset[str] = frozenset(
    {
        "point_count",
        "autocompleted",
    }
)


class _TabularExporter(BaseExporter):
    """Abstract exporter for tabular formats.

    ABB Route:
        N/A — local file export.

    ABB Constraints:
        No ABB controller access.

    Attributes:
        options: Export options.

    Example:
        ::

            exporter = ExcelExporter()
    """

    def __init__(self, options: ExportOptions | None = None) -> None:
        """Initialise the tabular exporter.

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

    @abstractmethod
    def _write_sheets(
        self,
        stem: str,
        dest_dir: Path,
        traj_df: pd.DataFrame,
        meta_df: pd.DataFrame | None,
        process_params_df: pd.DataFrame | None,
    ) -> Path:
        """Write output file or files from prepared DataFrames.

        ABB Route:
            N/A — local file write.

        ABB Constraints:
            No ABB controller access.

        Args:
            stem: Base name for the file or files, without extension.
            dest_dir: Destination directory, already created.
            traj_df: Points DataFrame.
            meta_df: Key/value metadata DataFrame, or ``None`` when
                ``options.include_meta`` is ``False``.
            process_params_df: Process parameter DataFrame, or ``None``
                when the trajectory has no process parameter table.

        Returns:
            Path of the main produced file.

        Raises:
            OSError: If output files cannot be written.

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
        ...

    def export(self, trajectory: Trajectory, dest_dir: Path) -> Path:
        """Export a trajectory to a tabular file.

        ABB Route:
            N/A — local file export.

        ABB Constraints:
            No ABB controller access.

        Args:
            trajectory: Trajectory to export.
            dest_dir: Destination directory, created when absent.

        Returns:
            Path of the main produced file.

        Raises:
            OSError: If the destination directory or output file cannot
                be created.

        Example:
            ::

                path = ExcelExporter().export(traj, Path("exports"))
        """
        dest_dir = self._ensure_dir(dest_dir)
        stem = trajectory.meta.name

        traj_df = self._build_traj_df(trajectory)
        meta_df = self._build_meta_df(trajectory) if self.options.include_meta else None
        process_params_df = (
            trajectory.process_params.copy()
            if trajectory.process_params is not None
            else None
        )

        return self._write_sheets(
            stem=stem,
            dest_dir=dest_dir,
            traj_df=traj_df,
            meta_df=meta_df,
            process_params_df=process_params_df,
        )

    def _build_traj_df(self, trajectory: Trajectory) -> pd.DataFrame:
        """Build the points DataFrame ready for export.

        ABB Route:
            N/A — local DataFrame transformation.

        ABB Constraints:
            No ABB controller access.

        Args:
            trajectory: Source trajectory.

        Returns:
            DataFrame ready for writing.

        Raises:
            UserWarning: If unknown point columns are present and are not
                exported by the selected column policy.

        Example:
            ::

                df = exporter._build_traj_df(traj)
        """
        df = trajectory.points.copy()
        columns = self._select_export_columns(df)
        exported = df.loc[:, columns].copy()

        float_cols = [col for col in exported.columns if col in _FLOAT_COLS]
        if float_cols:
            exported.loc[:, float_cols] = exported.loc[:, float_cols].round(
                self.options.float_precision
            )

        return exported.reset_index(drop=True)

    def _select_export_columns(self, df: pd.DataFrame) -> list[str]:
        """Select point columns according to export options.

        ABB Route:
            N/A.

        ABB Constraints:
            No ABB controller access.

        Args:
            df: Source points DataFrame.

        Returns:
            Ordered list of columns to export.

        Raises:
            UserWarning: If columns are ignored or requested columns are
                absent.

        Example:
            ::

                columns = exporter._select_export_columns(points)
        """
        available = list(df.columns)
        requested = self.options.export_columns

        if requested == ("*",):
            return available

        if requested is None or requested == ("default",):
            columns = [col for col in _DEFAULT_TRAJ_COL_ORDER if col in df.columns]
            self._warn_unexported_unknown_columns(df, columns)
            return columns

        if requested and requested[0] == "default":
            columns = [col for col in _DEFAULT_TRAJ_COL_ORDER if col in df.columns]
            for col in requested[1:]:
                if col in df.columns and col not in columns:
                    columns.append(col)
                elif col not in df.columns:
                    warnings.warn(
                        f"Requested export column {col!r} is not present in "
                        "trajectory points and will be ignored.",
                        UserWarning,
                        stacklevel=3,
                    )
            self._warn_unexported_unknown_columns(df, columns)
            return columns

        columns = []
        for col in requested:
            if col in df.columns:
                columns.append(col)
            else:
                warnings.warn(
                    f"Requested export column {col!r} is not present in "
                    "trajectory points and will be ignored.",
                    UserWarning,
                    stacklevel=3,
                )
        return columns

    @staticmethod
    def _warn_unexported_unknown_columns(
        df: pd.DataFrame,
        exported_columns: list[str],
    ) -> None:
        """Warn when unknown point columns are not exported.

        ABB Route:
            N/A.

        ABB Constraints:
            No ABB controller access.

        Args:
            df: Source points DataFrame.
            exported_columns: Columns selected for export.

        Returns:
            None.

        Raises:
            UserWarning: If unknown columns are present and omitted.

        Example:
            ::

                _TabularExporter._warn_unexported_unknown_columns(df, ["x"])
        """
        known = set(_DEFAULT_TRAJ_COL_ORDER)
        exported = set(exported_columns)
        ignored = [
            col for col in df.columns if col not in known and col not in exported
        ]
        if ignored:
            warnings.warn(
                "Trajectory contains columns that are not part of the "
                f"TrajCenter v2 export schema and were not exported: {ignored}. "
                "Use ExportOptions(export_columns=('*',)) or "
                "ExportOptions(export_columns=('default', ...)) to export them.",
                UserWarning,
                stacklevel=3,
            )

    @staticmethod
    def _build_meta_df(trajectory: Trajectory) -> pd.DataFrame:
        """Serialise trajectory metadata to a key/value DataFrame.

        ABB Route:
            N/A — local metadata serialisation.

        ABB Constraints:
            No ABB controller access.

        Args:
            trajectory: Source trajectory.

        Returns:
            Two-column DataFrame with ``key`` and ``value`` columns.

        Raises:
            None.

        Example:
            ::

                meta_df = _TabularExporter._build_meta_df(traj)
        """
        meta: TrajectoryMeta = trajectory.meta
        rows: list[dict[str, str]] = []

        direct_fields: dict[str, object] = {
            "name": meta.name,
            "source_file": meta.source_file,
            "source_format": (meta.source_format.value if meta.source_format else None),
            "robot_model": meta.robot_model,
            "created_at": (meta.created_at.isoformat() if meta.created_at else None),
            "version": meta.version,
        }

        for key, value in direct_fields.items():
            if key in _META_SKIP_FIELDS:
                continue
            if value is None:
                continue
            rows.append({"key": key, "value": str(value)})

        rows.append(
            {
                "key": "process_type",
                "value": str(meta.process.process_type),
            }
        )

        if meta.process.process_param_names:
            rows.append(
                {
                    "key": "process_param_names",
                    "value": ";".join(meta.process.process_param_names),
                }
            )

        if meta.extra:
            for key, value in meta.extra.items():
                if value is not None:
                    rows.append({"key": key, "value": str(value)})

        return pd.DataFrame(rows, columns=["key", "value"])
