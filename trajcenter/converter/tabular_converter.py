#!/usr/bin/env python3
# trajcenter/converter/tabular_converter.py
"""Abstract tabular converter — shared logic for Excel and CSV.

Author: Clement RACINET

This module factors out all tabular data conversion logic (column
resolution, sheet handling, tools/wobjs tables, autocompletion) into
an abstract class :class:`_TabularConverter`.

Subclasses only need to implement one method: :meth:`_read_sheets`,
which returns a ``dict[str, pd.DataFrame]`` (sheet name → raw
``DataFrame``).

Architecture
-------------
::

    BaseConverter (ABC)
        └── _TabularConverter (ABC)
                ├── ExcelConverter   → _read_sheets() via pd.ExcelFile
                └── CsvConverter     → _read_sheets() via pd.read_csv

Reserved sheets
----------------
- ``tools`` / ``tool``    : tool name table (``name`` column)
- ``wobjs`` / ``wobj``    : wobj name table (``name`` column)
- ``meta`` / ``metadata`` : key/value metadata (read, not a trajectory)

Every other sheet is treated as a trajectory sheet.

Meta sheet
-----------
The ``meta`` sheet is expected to have two columns ``key`` and ``value``.
Recognised fields (``name``, ``robot_model``) populate
:class:`TrajectoryMeta`. Unknown fields are stored in
:attr:`TrajectoryMeta.extra`. Fields that are recalculated at import
time (``source_format``, ``autocompleted``, ``created_at``,
``version``, ``point_count``) are silently ignored.

Mandatory columns
------------------
Only ``x``, ``y``, ``z`` are strictly mandatory.
Missing quaternions are replaced by the identity orientation
``[1, 0, 0, 0]``. All other columns are autocompleted from
:class:`~trajcenter.converter.defaults.ConversionDefaults`.
"""

from __future__ import annotations

import warnings
from abc import abstractmethod
from pathlib import Path

import pandas as pd

from trajcenter.converter.base import BaseConverter
from trajcenter.converter.column_mapper import resolve_columns
from trajcenter.converter.defaults import ConversionDefaults
from trajcenter.core.trajectory import SourceFormat, Trajectory, TrajectoryMeta


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SHEET_TOOLS: frozenset[str] = frozenset({"tools", "tool"})
_SHEET_WOBJS: frozenset[str] = frozenset({"wobjs", "wobj"})
_SHEET_META: frozenset[str] = frozenset({"meta", "metadata"})
_SHEET_RESERVED: frozenset[str] = _SHEET_TOOLS | _SHEET_WOBJS | _SHEET_META

#: Only x, y, z are strictly mandatory.
_REQUIRED_COLS: frozenset[str] = frozenset({"x", "y", "z"})

#: Identity quaternion (scalar-first: q1=qw=1, q2=qi=q3=qj=q4=qk=0).
_IDENTITY_QUATERNION: dict[str, float] = {
    "q1": 1.0,
    "q2": 0.0,
    "q3": 0.0,
    "q4": 0.0,
}

#: "Default" sheet names — the sheet name will not be suffixed to the stem.
_SHEET_DEFAULT_NAMES: frozenset[str] = frozenset(
    {
        "feuil1",
        "sheet1",
        "traj",
        "trajectoire",
        "sheet",
    }
)

#: TrajectoryMeta fields that can be applied directly from the meta sheet.
#: Any unknown field goes into extra{}.
_META_APPLICABLE_FIELDS: frozenset[str] = frozenset(
    {
        "name",
        "robot_model",
    }
)

#: TrajectoryMeta fields to explicitly ignore when re-reading
#: (recalculated at import time or not relevant).
_META_IGNORED_FIELDS: frozenset[str] = frozenset(
    {
        "source_format",
        "autocompleted",
        "created_at",
        "version",
        "point_count",
        "external_axes",
        "source_file",
    }
)


# ---------------------------------------------------------------------------
# Abstract tabular converter
# ---------------------------------------------------------------------------


class _TabularConverter(BaseConverter):
    """Abstract converter for tabular formats (Excel, CSV).

    Concrete subclasses:
    :class:`~trajcenter.converter.excel_converter.ExcelConverter` and
    :class:`~trajcenter.converter.csv_converter.CsvConverter`.

    Subclasses must implement :meth:`_read_sheets` and
    :attr:`_source_format`.

    Attributes:
        defaults: Default values for autocompletion.
    """

    def __init__(self, defaults: ConversionDefaults | None = None) -> None:
        """Initialise the tabular converter.

        Args:
            defaults: Default values for autocompletion.
                When ``None``,
                :class:`~trajcenter.converter.defaults.ConversionDefaults`
                is instantiated with its own default values.
        """
        super().__init__(defaults)

    # ------------------------------------------------------------------
    # Interface to implement
    # ------------------------------------------------------------------

    @property
    @abstractmethod
    def _source_format(self) -> SourceFormat:
        """Source format to record in :class:`~trajcenter.core.trajectory.TrajectoryMeta`."""
        ...

    @abstractmethod
    def _read_sheets(self, source: Path) -> dict[str, pd.DataFrame]:
        """Read the source file and return a dict ``{sheet_name: raw_DataFrame}``.

        Args:
            source: Path to the source file (already verified to exist).

        Returns:
            Ordered dictionary ``{sheet_name: DataFrame}``.
            For single-sheet formats (CSV), return ``{"sheet": df}``.
        """
        ...

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def convert(self, source: Path) -> Trajectory:
        """Convert a single-sheet tabular file to a trajectory.

        Args:
            source: Path to the source file.

        Returns:
            A valid :class:`~trajcenter.core.trajectory.Trajectory` object.

        Raises:
            FileNotFoundError: If the file does not exist.
            ValueError: If multiple trajectory sheets are present
                (use :meth:`convert_all` instead).
        """
        trajs = self.convert_all(source)
        if len(trajs) > 1:
            names = [t.meta.name for t in trajs]
            raise ValueError(
                f"The file contains {len(trajs)} trajectory sheets: "
                f"{names}. Use convert_all() to process all of them."
            )
        return trajs[0]

    def convert_all(self, source: Path) -> list[Trajectory]:
        """Convert all trajectory sheets in a tabular file.

        Args:
            source: Path to the source file.

        Returns:
            List of :class:`~trajcenter.core.trajectory.Trajectory` objects.

        Raises:
            FileNotFoundError: If the file does not exist.
            ValueError: If no valid trajectory sheet is found.
        """
        source = Path(source).resolve()
        if not source.exists():
            raise FileNotFoundError(f"File not found: {source}")

        all_sheets = self._read_sheets(source)
        sheet_names = list(all_sheets.keys())

        shared_tools = self._extract_ref_table(all_sheets, _SHEET_TOOLS, "name")
        shared_wobjs = self._extract_ref_table(all_sheets, _SHEET_WOBJS, "name")
        meta_overrides = self._extract_meta_overrides(all_sheets)

        traj_sheets = [s for s in sheet_names if s.casefold() not in _SHEET_RESERVED]

        if not traj_sheets:
            raise ValueError(
                f"No trajectory sheet found in: {source.name}. "
                f"Sheets present: {sheet_names}"
            )

        trajectories: list[Trajectory] = []
        for sheet in traj_sheets:
            try:
                traj = self._convert_sheet(
                    raw_df=all_sheets[sheet],
                    sheet_name=sheet,
                    source=source,
                    shared_tools=shared_tools,
                    shared_wobjs=shared_wobjs,
                    meta_overrides=meta_overrides,
                )
                trajectories.append(traj)
            except ValueError as exc:
                if "mandatory columns missing" in str(exc):
                    raise
                warnings.warn(
                    f"Sheet '{sheet}' skipped — error: {exc}",
                    UserWarning,
                    stacklevel=2,
                )
            except Exception as exc:
                warnings.warn(
                    f"Sheet '{sheet}' skipped — error: {exc}",
                    UserWarning,
                    stacklevel=2,
                )

        if not trajectories:
            raise ValueError(f"No valid trajectory extracted from: {source.name}")

        return trajectories

    # ------------------------------------------------------------------
    # Internal steps
    # ------------------------------------------------------------------

    def _convert_sheet(
        self,
        raw_df: pd.DataFrame,
        sheet_name: str,
        source: Path,
        shared_tools: list[str],
        shared_wobjs: list[str],
        meta_overrides: dict[str, str],
    ) -> Trajectory:
        """Convert a raw ``DataFrame`` to a :class:`~trajcenter.core.trajectory.Trajectory`.

        Args:
            raw_df: Raw ``DataFrame`` from the file reader.
            sheet_name: Sheet name (used in error messages and naming).
            source: Path to the source file (used for metadata).
            shared_tools: Shared tool table (from a dedicated sheet),
                may be empty.
            shared_wobjs: Shared wobj table (from a dedicated sheet),
                may be empty.
            meta_overrides: Key/value dict from the meta sheet,
                may be empty.

        Returns:
            A valid, complete
            :class:`~trajcenter.core.trajectory.Trajectory` object.

        Raises:
            ValueError: If the mandatory columns x, y, z are absent.
        """
        df = raw_df.dropna(how="all").reset_index(drop=True)
        df, unresolved = resolve_columns(df)

        if unresolved:
            warnings.warn(
                f"Sheet '{sheet_name}' — unrecognised columns (ignored): {unresolved}",
                UserWarning,
                stacklevel=4,
            )

        missing = _REQUIRED_COLS - set(df.columns)
        if missing:
            raise ValueError(
                f"Sheet '{sheet_name}' — mandatory columns missing: {sorted(missing)}"
            )

        # Identity quaternion when absent
        autocompleted_quat: list[str] = []
        for col, val in _IDENTITY_QUATERNION.items():
            if col not in df.columns:
                df[col] = val
                autocompleted_quat.append(col)

        tools, wobjs = self._build_ref_tables(df, shared_tools, shared_wobjs)
        df = self._resolve_tool_wobj_indices(df, tools, wobjs)
        df, autocompleted = self._autocomplete(df, tools, wobjs)

        all_autocompleted = autocompleted_quat + [
            c for c in autocompleted if c not in autocompleted_quat
        ]

        # Name: meta_overrides["name"] > name computed from stem + sheet
        traj_name: str = meta_overrides.get("name") or (
            source.stem
            if sheet_name.casefold() in _SHEET_DEFAULT_NAMES
            else f"{source.stem}_{sheet_name}"
        )

        # Direct applicable fields from meta
        robot_model: str | None = meta_overrides.get("robot_model") or None

        # Unknown fields → extra{} (neither applicable nor explicitly ignored)
        extra: dict[str, str | int | float | bool | None] = {
            k: v
            for k, v in meta_overrides.items()
            if k not in _META_APPLICABLE_FIELDS and k not in _META_IGNORED_FIELDS
        }

        meta = TrajectoryMeta(
            name=traj_name,
            source_file=source.name,
            source_format=self._source_format,
            autocompleted=all_autocompleted,
            robot_model=robot_model,
            extra=extra,
        )

        return Trajectory(meta=meta, points=df, tools=tools, wobjs=wobjs)

    @staticmethod
    def _extract_meta_overrides(
        all_sheets: dict[str, pd.DataFrame],
    ) -> dict[str, str]:
        """Read the meta sheet (key/value format) and return a ``{key: value}`` dict.

        The sheet is expected to have two columns ``key`` and ``value``
        (case-insensitive). Rows with an empty key or value are ignored.
        If the sheet is absent or malformed, an empty dict is returned
        silently.

        Args:
            all_sheets: All sheets from the source file.

        Returns:
            Dict ``{normalised_key: value_str}``, never ``None``.
        """
        for sheet_name, df in all_sheets.items():
            if sheet_name.casefold() not in _SHEET_META:
                continue

            df_meta = df.copy()
            df_meta.columns = pd.Index([str(c).casefold() for c in df_meta.columns])

            if "key" not in df_meta.columns or "value" not in df_meta.columns:
                return {}

            result: dict[str, str] = {}
            for _, row in df_meta.iterrows():
                k = str(row["key"]).strip().casefold() if pd.notna(row["key"]) else ""
                v = str(row["value"]).strip() if pd.notna(row["value"]) else ""
                if k and v:
                    result[k] = v

            return result

        return {}

    @staticmethod
    def _extract_ref_table(
        all_sheets: dict[str, pd.DataFrame],
        target_names: frozenset[str],
        name_col: str,
    ) -> list[str]:
        """Extract a reference table (tools or wobjs) from the loaded sheets.

        Args:
            all_sheets: All sheets from the file.
            target_names: Reserved sheet names to search for
                (e.g. ``_SHEET_TOOLS``).
            name_col: Name of the column containing the values
                (``"name"``).

        Returns:
            List of extracted names, or an empty list if the sheet is
            absent.
        """
        for sheet_name, df in all_sheets.items():
            if sheet_name.casefold() in target_names:
                df_ref = df.copy()
                df_ref.columns = pd.Index([str(c).casefold() for c in df_ref.columns])
                if name_col in df_ref.columns:
                    return df_ref[name_col].dropna().astype(str).tolist()
        return []

    @staticmethod
    def _build_ref_tables(
        df: pd.DataFrame,
        shared_tools: list[str],
        shared_wobjs: list[str],
    ) -> tuple[list[str], list[str]]:
        """Build tools/wobjs tables from the ``DataFrame`` or shared sheets.

        Priority: shared sheet > ``tool``/``wobj`` column in the
        ``DataFrame``.

        Args:
            df: Trajectory sheet ``DataFrame``.
            shared_tools: Tool table from a dedicated sheet.
            shared_wobjs: Wobj table from a dedicated sheet.

        Returns:
            Tuple ``(tools, wobjs)``.
        """

        def _extract_unique(col: str) -> list[str]:
            if col in df.columns:
                return list(dict.fromkeys(df[col].dropna().astype(str).tolist()))
            return []

        tools = shared_tools or _extract_unique("tool")
        wobjs = shared_wobjs or _extract_unique("wobj")
        return tools, wobjs

    @staticmethod
    def _resolve_tool_wobj_indices(
        df: pd.DataFrame,
        tools: list[str],
        wobjs: list[str],
    ) -> pd.DataFrame:
        """Replace ``tool``/``wobj`` name columns with integer index columns.

        Args:
            df: Trajectory sheet ``DataFrame``.
            tools: Tool name table.
            wobjs: Wobj name table.

        Returns:
            ``DataFrame`` with ``tool_index`` and ``wobj_index`` columns
            where applicable, and the original name columns dropped.
        """
        df = df.copy()
        for col, table, idx_col in [
            ("tool", tools, "tool_index"),
            ("wobj", wobjs, "wobj_index"),
        ]:
            if col in df.columns and table:
                name_to_idx = {name: i for i, name in enumerate(table)}
                df[idx_col] = df[col].astype(str).map(name_to_idx).fillna(0).astype(int)
                df = df.drop(columns=[col])
        return df
