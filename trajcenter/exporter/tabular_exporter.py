#!/usr/bin/env python3
# trajcenter/exporter/tabular_exporter.py
"""Abstract tabular exporter — shared logic for Excel and CSV.

Author: Clement RACINET

This module factors out the construction of the four ``DataFrames``
(traj, tools, wobjs, meta) into :class:`_TabularExporter`.

Subclasses only need to implement one method: :meth:`_write_sheets`,
which receives the ready-to-write ``DataFrames`` and writes the
output file(s).

Architecture
-------------
::

    BaseExporter (ABC)
        └── _TabularExporter (ABC)
                ├── ExcelExporter   → _write_sheets() via openpyxl
                └── CsvExporter     → _write_sheets() via 4 CSV files

Import / export symmetry
-------------------------
The exported ``traj`` sheet is the exact mirror of the imported sheet:

- ``tool_index`` and ``wobj_index`` are resolved to names (``tool``
  and ``wobj`` columns).
- Floats are rounded according to
  :attr:`~trajcenter.exporter.options.ExportOptions.float_precision`.
- The ``meta`` sheet is produced in key/value format, re-readable at
  import time.
"""

from __future__ import annotations

from abc import abstractmethod
from pathlib import Path

import pandas as pd

from trajcenter.core.trajectory import Trajectory, TrajectoryMeta
from trajcenter.exporter.base import BaseExporter
from trajcenter.exporter.options import ExportOptions


#: Float columns to round at export time.
_FLOAT_COLS: frozenset[str] = frozenset({"x", "y", "z", "q1", "q2", "q3", "q4"})

#: TrajectoryMeta fields to skip at export time
#: (recalculated at import or redundant).
_META_SKIP_FIELDS: frozenset[str] = frozenset(
    {
        "point_count",  # recalculated from the DataFrame
        "autocompleted",  # specific to import, meaningless on re-read
    }
)

#: Preferred column order in the traj sheet.
_TRAJ_COL_ORDER: list[str] = [
    "x",
    "y",
    "z",
    "q1",
    "q2",
    "q3",
    "q4",
    "cf1",
    "cf4",
    "cf6",
    "cfx",
    "move_type",
    "speed",
    "zone",
    "tool",
    "wobj",
]


class _TabularExporter(BaseExporter):
    """Abstract exporter for tabular formats (Excel, CSV).

    Concrete subclasses:
    :class:`~trajcenter.exporter.excel_exporter.ExcelExporter` and
    :class:`~trajcenter.exporter.csv_exporter.CsvExporter`.

    Subclasses must implement :meth:`_write_sheets`.

    Attributes:
        options: Export options.
    """

    def __init__(self, options: ExportOptions | None = None) -> None:
        """Initialise the tabular exporter.

        Args:
            options: Export options. When ``None``,
                :class:`~trajcenter.exporter.options.ExportOptions`
                is instantiated with its own default values.
        """
        super().__init__(options)

    # ------------------------------------------------------------------
    # Interface to implement
    # ------------------------------------------------------------------

    @abstractmethod
    def _write_sheets(
        self,
        stem: str,
        dest_dir: Path,
        traj_df: pd.DataFrame,
        tools_df: pd.DataFrame,
        wobjs_df: pd.DataFrame,
        meta_df: pd.DataFrame | None,
    ) -> Path:
        """Write the output file(s) from the prepared ``DataFrames``.

        Args:
            stem: Base name for the file(s) (without extension).
            dest_dir: Destination directory (already created).
            traj_df: Points ``DataFrame`` (tool/wobj resolved to names).
            tools_df: Tools ``DataFrame`` (``name`` column).
            wobjs_df: Wobjs ``DataFrame`` (``name`` column).
            meta_df: Key/value metadata ``DataFrame``, or ``None``
                when ``options.include_meta`` is ``False``.

        Returns:
            Path of the main produced file.
        """
        ...

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def export(self, trajectory: Trajectory, dest_dir: Path) -> Path:
        """Export a trajectory to a tabular file.

        Args:
            trajectory: Trajectory to export.
            dest_dir: Destination directory (created when absent).

        Returns:
            Path of the main produced file.
        """
        dest_dir = self._ensure_dir(dest_dir)
        stem = trajectory.meta.name

        traj_df = self._build_traj_df(trajectory)
        tools_df = self._build_tools_df(trajectory)
        wobjs_df = self._build_wobjs_df(trajectory)
        meta_df = self._build_meta_df(trajectory) if self.options.include_meta else None

        return self._write_sheets(
            stem=stem,
            dest_dir=dest_dir,
            traj_df=traj_df,
            tools_df=tools_df,
            wobjs_df=wobjs_df,
            meta_df=meta_df,
        )

    # ------------------------------------------------------------------
    # DataFrame construction
    # ------------------------------------------------------------------

    def _build_traj_df(self, trajectory: Trajectory) -> pd.DataFrame:
        """Build the points ``DataFrame`` ready for export.

        - ``tool_index`` → ``tool`` column (names resolved from
          ``trajectory.tools``).
        - ``wobj_index`` → ``wobj`` column (names resolved from
          ``trajectory.wobjs``).
        - Floats rounded according to
          :attr:`~trajcenter.exporter.options.ExportOptions.float_precision`.
        - Columns ordered according to :data:`_TRAJ_COL_ORDER`.

        Args:
            trajectory: Source trajectory.

        Returns:
            ``DataFrame`` ready for writing.
        """
        df = trajectory.points.copy()
        prec = self.options.float_precision

        # Resolve tool_index → name
        if "tool_index" in df.columns and trajectory.tools:
            df["tool"] = df["tool_index"].apply(
                lambda i: (
                    trajectory.tools[int(i)]
                    if 0 <= int(i) < len(trajectory.tools)
                    else trajectory.tools[0]
                )
            )
            df = df.drop(columns=["tool_index"])

        # Resolve wobj_index → name
        if "wobj_index" in df.columns and trajectory.wobjs:
            df["wobj"] = df["wobj_index"].apply(
                lambda i: (
                    trajectory.wobjs[int(i)]
                    if 0 <= int(i) < len(trajectory.wobjs)
                    else trajectory.wobjs[0]
                )
            )
            df = df.drop(columns=["wobj_index"])

        # Round floats
        float_cols = [c for c in df.columns if c in _FLOAT_COLS]
        df[float_cols] = df[float_cols].round(prec)

        # Reorder columns
        ordered = [c for c in _TRAJ_COL_ORDER if c in df.columns]
        extras = [c for c in df.columns if c not in _TRAJ_COL_ORDER]
        df = df[ordered + extras]

        return df.reset_index(drop=True)

    @staticmethod
    def _build_tools_df(trajectory: Trajectory) -> pd.DataFrame:
        """Build the tools table ``DataFrame``.

        Args:
            trajectory: Source trajectory.

        Returns:
            Single-column ``DataFrame`` with a ``name`` column.
        """
        return pd.DataFrame({"name": trajectory.tools})

    @staticmethod
    def _build_wobjs_df(trajectory: Trajectory) -> pd.DataFrame:
        """Build the wobjs table ``DataFrame``.

        Args:
            trajectory: Source trajectory.

        Returns:
            Single-column ``DataFrame`` with a ``name`` column.
        """
        return pd.DataFrame({"name": trajectory.wobjs})

    @staticmethod
    def _build_meta_df(trajectory: Trajectory) -> pd.DataFrame:
        """Serialise :class:`~trajcenter.core.trajectory.TrajectoryMeta` to a key/value ``DataFrame``.

        Fields in :data:`_META_SKIP_FIELDS` are omitted.
        Fields that are ``None`` or empty lists are omitted.
        ``extra`` fields are unfolded as individual entries.

        Args:
            trajectory: Source trajectory.

        Returns:
            Two-column ``DataFrame`` with ``key`` and ``value`` columns.
        """
        meta: TrajectoryMeta = trajectory.meta
        rows: list[dict[str, str]] = []

        # Direct TrajectoryMeta fields
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

        # Unfolded extra{} fields
        if meta.extra:
            for key, value in meta.extra.items():
                if value is not None:
                    rows.append({"key": key, "value": str(value)})

        return pd.DataFrame(rows, columns=["key", "value"])
