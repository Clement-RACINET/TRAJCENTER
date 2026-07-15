#!/usr/bin/env python3
# trajcenter/converter/tabular_converter.py
"""Abstract tabular converter — shared logic for Excel and CSV.

Author: Clement RACINET

This module factors all tabular data conversion logic (column
resolution, sheet management, tools/wobjs tables, autocompletion) into
the abstract class :class:`_TabularConverter`.

Subclasses only need to implement :meth:`_TabularConverter._read_sheets`,
which returns a ``dict[str, pd.DataFrame]`` (sheet name → raw
DataFrame).

Architecture
-------------
::

    BaseConverter (ABC)
    └── _TabularConverter (ABC)
        ├── ExcelConverter  → _read_sheets() via pd.ExcelFile
        └── CsvConverter    → _read_sheets() via pd.read_csv

Reserved sheets
----------------
- ``tools`` / ``tool``     : tool name table (``name`` column)
- ``wobjs`` / ``wobj``     : wobj name table (``name`` column)
- ``meta``  / ``metadata`` : key/value metadata (read, not a trajectory)

Any other sheet is treated as a trajectory sheet.

Meta sheet
-----------
The ``meta`` sheet is expected to have two columns ``key`` and
``value``.  Recognised fields (``name``, ``robot_model``) populate
:class:`~trajcenter.core.trajectory.TrajectoryMeta`.  Unknown fields
are stored in :attr:`~trajcenter.core.trajectory.TrajectoryMeta.extra`.
Fields recomputed at import time (``source_format``, ``autocompleted``,
``created_at``, ``version``, ``point_count``) are silently ignored.

Mandatory columns
------------------
Only ``x``, ``y``, ``z`` are strictly required.  Missing quaternions
are replaced by the identity orientation ``[1, 0, 0, 0]``.  All other
columns are autocompleted from
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
from trajcenter.core.messages import msg
from trajcenter.core.trajectory import SourceFormat, Trajectory, TrajectoryMeta

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SHEET_TOOLS: frozenset[str] = frozenset({"tools", "tool"})
_SHEET_WOBJS: frozenset[str] = frozenset({"wobjs", "wobj"})
_SHEET_META: frozenset[str] = frozenset({"meta", "metadata"})
_SHEET_RESERVED: frozenset[str] = _SHEET_TOOLS | _SHEET_WOBJS | _SHEET_META

#: Only x, y, z are strictly required.
_REQUIRED_COLS: frozenset[str] = frozenset({"x", "y", "z"})

#: Identity quaternion (scalar-first: q1=qw=1, q2=qi=q3=qj=q4=qk=0).
_IDENTITY_QUATERNION: dict[str, float] = {
    "q1": 1.0,
    "q2": 0.0,
    "q3": 0.0,
    "q4": 0.0,
}

#: Sheet names considered "default" — the sheet name is not appended to the stem.
_SHEET_DEFAULT_NAMES: frozenset[str] = frozenset(
    {
        "feuil1",
        "sheet1",
        "traj",
        "trajectoire",
        "sheet",
    }
)

#: TrajectoryMeta fields directly applicable from the meta sheet.
_META_APPLICABLE_FIELDS: frozenset[str] = frozenset({"name", "robot_model"})

#: TrajectoryMeta fields to silently ignore when reading the meta sheet
#: (recomputed at import time).
_META_IGNORED_FIELDS: frozenset[str] = frozenset(
    {
        "source_format",
        "autocompleted",
        "created_at",
        "version",
        "point_count",
        "source_file",
    }
)


# ---------------------------------------------------------------------------
# Abstract class
# ---------------------------------------------------------------------------


class _TabularConverter(BaseConverter):
    """Abstract base for tabular (Excel / CSV) converters.

    Author: Clement RACINET

    Subclasses must implement :meth:`_read_sheets`.

    Args:
        defaults: Autocompletion defaults. ``None`` uses
            :class:`~trajcenter.converter.defaults.ConversionDefaults`
            built-in values.
        source_format: :class:`~trajcenter.core.trajectory.SourceFormat`
            tag stamped on the produced trajectory.
    """

    def __init__(
        self,
        defaults: ConversionDefaults | None = None,
        source_format: SourceFormat = SourceFormat.EXCEL,
    ) -> None:
        """Initialise the tabular converter.

        Args:
            defaults: Autocompletion defaults.
            source_format: Source format tag for trajectory metadata.
        """
        super().__init__(defaults=defaults)
        self._source_format = source_format

    # ------------------------------------------------------------------
    # Interface to implement
    # ------------------------------------------------------------------

    @abstractmethod
    def _read_sheets(self, source: Path) -> dict[str, pd.DataFrame]:
        """Read *source* and return a mapping of sheet name → raw DataFrame.

        Args:
            source: Path to the source file.

        Returns:
            Dictionary mapping sheet names to their raw DataFrames.

        Raises:
            FileNotFoundError: If *source* does not exist.
        """
        ...

    # ------------------------------------------------------------------
    # Main conversion
    # ------------------------------------------------------------------

    def convert(self, source: Path) -> Trajectory:
        """Convert *source* to a single :class:`~trajcenter.core.trajectory.Trajectory`.

        Reads all sheets, resolves columns, applies identity quaternion
        when absent, autocompletes missing columns, and builds the
        trajectory.

        ABB Route:
            N/A — local file conversion, no RWS call.

        ABB Constraints:
            None.

        Args:
            source: Path to the source file (Excel or CSV).

        Returns:
            Complete :class:`~trajcenter.core.trajectory.Trajectory`.

        Raises:
            FileNotFoundError: If *source* does not exist.
            ValueError: If mandatory XYZ columns are missing.
            ValueError: If multiple trajectory sheets are found (use
                :meth:`convert_all` instead).

        Example:
            ::

                traj = CsvConverter().convert(Path("data/traj.csv"))
        """
        if not source.exists():
            raise FileNotFoundError(msg("FILE_NOT_FOUND", path=source))

        sheets = self._read_sheets(source)
        tools = self._extract_name_list(sheets, _SHEET_TOOLS)
        wobjs = self._extract_name_list(sheets, _SHEET_WOBJS)
        meta_overrides = self._extract_meta(sheets)

        traj_sheets = {
            name: df
            for name, df in sheets.items()
            if name.lower() not in _SHEET_RESERVED
        }

        if len(traj_sheets) > 1:
            raise ValueError(
                f"Multiple trajectory sheets found: {list(traj_sheets)}. "
                f"Use convert_all() to convert each sheet separately."
            )

        sheet_name, df = next(iter(traj_sheets.items()))
        return self._build_trajectory(
            df=df,
            sheet_name=sheet_name,
            source=source,
            tools=tools,
            wobjs=wobjs,
            meta_overrides=meta_overrides,
        )

    def convert_all(self, source: Path) -> list[Trajectory]:
        """Convert all trajectory sheets in *source*.

        ABB Route:
            N/A — local file conversion, no RWS call.

        ABB Constraints:
            None.

        Args:
            source: Path to the source file.

        Returns:
            List of :class:`~trajcenter.core.trajectory.Trajectory`
            objects, one per trajectory sheet.

        Raises:
            FileNotFoundError: If *source* does not exist.
            ValueError: If mandatory XYZ columns are missing in any
                sheet.

        Example:
            ::

                trajs = ExcelConverter().convert_all(Path("data/multi.xlsx"))
        """
        if not source.exists():
            raise FileNotFoundError(msg("FILE_NOT_FOUND", path=source))

        sheets = self._read_sheets(source)
        tools = self._extract_name_list(sheets, _SHEET_TOOLS)
        wobjs = self._extract_name_list(sheets, _SHEET_WOBJS)
        meta_overrides = self._extract_meta(sheets)

        return [
            self._build_trajectory(
                df=df,
                sheet_name=sheet_name,
                source=source,
                tools=tools,
                wobjs=wobjs,
                meta_overrides=meta_overrides,
            )
            for sheet_name, df in sheets.items()
            if sheet_name.lower() not in _SHEET_RESERVED
        ]

    # ------------------------------------------------------------------
    # Single-sheet trajectory builder
    # ------------------------------------------------------------------

    def _build_trajectory(
        self,
        df: pd.DataFrame,
        sheet_name: str,
        source: Path,
        tools: list[str],
        wobjs: list[str],
        meta_overrides: dict[str, str],
    ) -> Trajectory:
        """Build a single :class:`~trajcenter.core.trajectory.Trajectory` from a DataFrame.

        Args:
            df: Raw DataFrame for this sheet.
            sheet_name: Sheet name (used for error messages and naming).
            source: Path to the source file.
            tools: Tool name list from the ``tools`` reserved sheet.
            wobjs: Wobj name list from the ``wobjs`` reserved sheet.
            meta_overrides: Key/value overrides from the ``meta`` sheet.

        Returns:
            Complete :class:`~trajcenter.core.trajectory.Trajectory`.

        Raises:
            ValueError: If mandatory XYZ columns are missing.
        """
        df = df.dropna(how="all").reset_index(drop=True)
        df, unknown = resolve_columns(df)

        if unknown:
            warnings.warn(
                msg("UNKNOWN_COLUMNS", cols=unknown),
                UserWarning,
                stacklevel=3,
            )

        missing = sorted(_REQUIRED_COLS - set(df.columns))
        if missing:
            raise ValueError(
                msg("SHEET_MANDATORY_COLUMNS_MISSING", sheet=sheet_name, cols=missing)
            )

        for qcol, qval in _IDENTITY_QUATERNION.items():
            if qcol not in df.columns:
                df[qcol] = qval

        if not tools:
            tools, df = self._extract_inline_tools(df, "tool")
        if not wobjs:
            wobjs, df = self._extract_inline_tools(df, "wobj")

        if "tool_index" not in df.columns:
            df["tool_index"] = 0
        if "wobj_index" not in df.columns:
            df["wobj_index"] = 0

        df, autocompleted = self._autocomplete(df, tools, wobjs)

        stem = source.stem
        sheet_lower = sheet_name.lower()
        name = stem if sheet_lower in _SHEET_DEFAULT_NAMES else f"{stem}_{sheet_name}"
        if "name" in meta_overrides:
            name = meta_overrides["name"]

        meta = TrajectoryMeta(
            name=name,
            source_format=self._source_format,
            source_file=source.name,
            robot_model=meta_overrides.get("robot_model"),
            autocompleted=autocompleted,
            extra={
                k: v
                for k, v in meta_overrides.items()
                if k not in _META_APPLICABLE_FIELDS and k not in _META_IGNORED_FIELDS
            },
        )
        return Trajectory(meta=meta, points=df, tools=tools, wobjs=wobjs)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_name_list(
        sheets: dict[str, pd.DataFrame],
        reserved_names: frozenset[str],
    ) -> list[str]:
        """Extract an ordered name list from a reserved sheet.

        Args:
            sheets: All sheets read from the source file.
            reserved_names: Reserved sheet names to look for
                (e.g. ``{"tools", "tool"}``).

        Returns:
            List of names from the ``name`` column, or ``[]`` if the
            sheet is absent or malformed.
        """
        for sheet_name, df in sheets.items():
            if sheet_name.lower() in reserved_names:
                if "name" in df.columns:
                    return df["name"].dropna().tolist()
        return []

    @staticmethod
    def _extract_meta(sheets: dict[str, pd.DataFrame]) -> dict[str, str]:
        """Extract key/value metadata from the ``meta`` sheet.

        Args:
            sheets: All sheets read from the source file.

        Returns:
            Dictionary of ``{key: value}`` pairs, or ``{}`` if absent
            or malformed.
        """
        for sheet_name, df in sheets.items():
            if sheet_name.lower() in _SHEET_META:
                if "key" in df.columns and "value" in df.columns:
                    return dict(
                        zip(
                            df["key"].astype(str),
                            df["value"].astype(str),
                        )
                    )
        return {}

    @staticmethod
    def _extract_inline_tools(
        df: pd.DataFrame,
        col: str,
    ) -> tuple[list[str], pd.DataFrame]:
        """Build an index table from an inline ``tool`` or ``wobj`` column.

        If *col* is present in *df*, deduplicates its values into an
        ordered list and replaces the column with an integer index
        column (``tool_index`` or ``wobj_index``).

        Args:
            df: Input DataFrame (may contain a ``tool`` or ``wobj``
                column).
            col: Column name to process (``"tool"`` or ``"wobj"``).

        Returns:
            A tuple ``(name_list, updated_df)`` where:

            - ``name_list`` is the deduplicated list of names.
            - ``updated_df`` has the ``col`` column replaced by
              ``{col}_index``.
        """
        if col not in df.columns:
            return [], df

        names: list[str] = []
        name_to_idx: dict[str, int] = {}
        for name in df[col].fillna(""):
            name_str = str(name)
            if name_str not in name_to_idx:
                name_to_idx[name_str] = len(names)
                names.append(name_str)

        df = df.copy()
        df[f"{col}_index"] = df[col].fillna("").map(name_to_idx).astype("int16")
        df = df.drop(columns=[col])
        return names, df
