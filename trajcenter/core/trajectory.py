#!/usr/bin/env python3
# trajcenter/core/trajectory.py
"""Central data model for an ABB robot trajectory.

Author: Clement RACINET

This module defines the main data structure of the TrajCenter project.
A trajectory is composed of metadata (:class:`TrajectoryMeta`), a set
of points stored in a ``pandas.DataFrame``, and naming tables for tools
and wobjs.

``.trajcenter`` file format
----------------------------
ZIP archive containing four entries:

- ``meta.json``      : serialised metadata (Pydantic → JSON)
- ``points.parquet`` : trajectory points (PyArrow, zstd compression)
- ``tools.json``     : ordered list of tool names (index → name)
- ``wobjs.json``     : ordered list of wobj names (index → name)

The ``tool_index`` and ``wobj_index`` columns of the ``DataFrame``
reference entries in these lists by their position (``int16`` integer).
These lists are **always present** in the archive (empty array ``[]``
when not applicable).

ABB RAPID conventions
----------------------
- Quaternions: ``[q1, q2, q3, q4]`` = ``[w, x, y, z]`` (scalar-first)
- External axes: ``eax_a`` … ``eax_f`` (presence in the DataFrame =
  active axis)
- The sentinel value ``9E9`` for inactive axes is injected only at RWS
  serialisation time, never stored in the Parquet file.
- Units: positions in mm, rotations in degrees (linear axes in mm)

Autocompletion
---------------
At the output of any converter, the ``.trajcenter`` file is **always
complete**: any column absent from the source is filled with values
from :class:`~trajcenter.converter.defaults.ConversionDefaults`.
Autocompleted columns are listed in
:attr:`TrajectoryMeta.autocompleted`. This module does not know about
``ConversionDefaults`` — the autocompletion logic belongs to the
``converter`` package.

Example:
    Create and save a minimal trajectory::

        import pandas as pd
        from trajcenter.core.trajectory import Trajectory, TrajectoryMeta

        df = pd.DataFrame({
            "x": [100.0], "y": [200.0], "z": [300.0],
            "q1": [1.0], "q2": [0.0], "q3": [0.0], "q4": [0.0],
            "move_type":  ["MoveL"],
            "speed":      ["v500"],
            "zone":       ["z10"],
            "cf1": [0], "cf4": [0], "cf6": [0], "cfx": [0],
            "tool_index": [0],
            "wobj_index": [0],
        })
        meta = TrajectoryMeta(
            name="my_trajectory",
            robot_model="IRB6700",
            autocompleted=["move_type", "speed", "zone", "cf1", "cf4", "cf6", "cfx"],
        )
        traj = Trajectory(
            meta=meta,
            points=df,
            tools=["Tool_formage"],
            wobjs=["Wobj_SerreFlan"],
        )
        traj.save("trajectory_store/my_trajectory.trajcenter")
"""

from __future__ import annotations

import io
import json
import zipfile
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path

from typing_extensions import override

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from pydantic import BaseModel, Field, model_validator


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class SourceFormat(StrEnum):
    """Origin format of the source file that produced the trajectory.

    Attributes:
        EXCEL: Microsoft Excel file (.xlsx / .xls).
        APT: CATIA APT source file (.aptsource).
        CSV: Delimited text file (.csv / .txt).
        RAPID: ABB RAPID module (.mod).
        MANUAL: Created programmatically, without a source file.
        TRAJCENTER: Loaded from an existing ``.trajcenter`` archive.
    """

    EXCEL = "excel"
    APT = "apt"
    CSV = "csv"
    RAPID = "rapid"
    MANUAL = "manual"
    TRAJCENTER = "trajcenter"


class MoveType(StrEnum):
    """RAPID movement type associated with a trajectory point.

    Attributes:
        MOVE_J: Joint movement (MoveJ).
        MOVE_L: Linear Cartesian movement (MoveL).
        MOVE_C: Circular movement (MoveC).
    """

    MOVE_J = "MoveJ"
    MOVE_L = "MoveL"
    MOVE_C = "MoveC"


# ---------------------------------------------------------------------------
# Parquet schema
# ---------------------------------------------------------------------------

#: Geometric columns always present in ``points.parquet``.
#: These are the only columns that ``Trajectory`` requires at instantiation.
#: All other columns are guaranteed complete **by the converters**.
REQUIRED_COLUMNS: list[str] = ["x", "y", "z", "q1", "q2", "q3", "q4"]

#: Columns completed by converters via ``ConversionDefaults``.
#: Always present in a ``.trajcenter`` produced by a converter.
#: Absent only when the trajectory is created manually
#: (``SourceFormat.MANUAL``).
CONVERTER_COLUMNS: list[str] = [
    "cf1",
    "cf4",
    "cf6",
    "cfx",
    "speed",
    "zone",
    "move_type",
    "tool_index",
    "wobj_index",
]

#: Pure optional columns — presence = active external axis on this robot.
#: Never autocompleted. Absent = axis does not exist (9E9 injected on the
#: RWS side).
EXTERNAL_AXIS_COLUMNS: list[str] = [
    "eax_a",
    "eax_b",
    "eax_c",
    "eax_d",
    "eax_e",
    "eax_f",
]

#: Union of all recognised columns (excluding REQUIRED).
OPTIONAL_COLUMNS: list[str] = CONVERTER_COLUMNS + EXTERNAL_AXIS_COLUMNS

#: Mapping column → numpy dtype for type casting at validation time.
COLUMN_DTYPES: dict[str, np.dtype[np.generic]] = {
    "x": np.dtype("float64"),
    "y": np.dtype("float64"),
    "z": np.dtype("float64"),
    "q1": np.dtype("float64"),
    "q2": np.dtype("float64"),
    "q3": np.dtype("float64"),
    "q4": np.dtype("float64"),
    "eax_a": np.dtype("float64"),
    "eax_b": np.dtype("float64"),
    "eax_c": np.dtype("float64"),
    "eax_d": np.dtype("float64"),
    "eax_e": np.dtype("float64"),
    "eax_f": np.dtype("float64"),
    "tool_index": np.dtype("int16"),
    "wobj_index": np.dtype("int16"),
    # cf* → nullable pandas Int8  (handled separately via CONFDATA_COLUMNS)
    # speed, zone, move_type → str (no numpy cast)
}

#: Confdata columns — nullable pandas Int8 (supports NaN, unlike np.int8).
CONFDATA_COLUMNS: frozenset[str] = frozenset({"cf1", "cf4", "cf6", "cfx"})

#: Mapping column → PyArrow type for Parquet schema construction.
#: Columns absent from this dict default to ``pa.string()``.
_PA_TYPE_MAP: dict[str, pa.DataType] = {
    "x": pa.float64(),
    "y": pa.float64(),
    "z": pa.float64(),
    "q1": pa.float64(),
    "q2": pa.float64(),
    "q3": pa.float64(),
    "q4": pa.float64(),
    "cf1": pa.int8(),
    "cf4": pa.int8(),
    "cf6": pa.int8(),
    "cfx": pa.int8(),
    "eax_a": pa.float64(),
    "eax_b": pa.float64(),
    "eax_c": pa.float64(),
    "eax_d": pa.float64(),
    "eax_e": pa.float64(),
    "eax_f": pa.float64(),
    "speed": pa.string(),
    "zone": pa.string(),
    "move_type": pa.string(),
    "tool_index": pa.int16(),
    "wobj_index": pa.int16(),
}

#: Mandatory ZIP entries for a file to be a valid ``.trajcenter`` archive.
_REQUIRED_ZIP_ENTRIES: frozenset[str] = frozenset({"meta.json", "points.parquet"})


# ---------------------------------------------------------------------------
# Pydantic models — metadata
# ---------------------------------------------------------------------------


class ExternalAxisConfig(BaseModel):
    """Description of an active external axis in the trajectory.

    This configuration is independent of the target cell.
    The mapping to a physical actuator is resolved at RWS transfer time.

    Attributes:
        axis_type: Kinematic type of the axis.
            Values: ``"rotational"`` or ``"linear"``.
        unit: Unit of the stored value.
            ``"deg"`` for rotational, ``"mm"`` for linear.
        label: Optional human-readable name
            (e.g. ``"Positionneur A"``).

    Example:
        ::

            ExternalAxisConfig(
                axis_type="rotational", unit="deg", label="Positionneur A"
            )
    """

    axis_type: str = Field(..., description="'rotational' or 'linear'")
    unit: str = Field(..., description="'deg' or 'mm'")
    label: str | None = Field(
        None, description="Human-readable name, e.g. 'Positionneur A'"
    )


class TrajectoryMeta(BaseModel):
    """Metadata for an ABB trajectory — stored in ``meta.json``.

    These metadata are **independent of the target cell**. They describe
    the origin, external axis configuration, and autocompletion
    traceability performed during conversion.

    The autocompletion logic (default values applied to columns absent
    from the source) belongs to the ``converter`` package via
    :class:`~trajcenter.converter.defaults.ConversionDefaults`.
    This model only **stores the result** in ``autocompleted``.

    Attributes:
        name: Trajectory name (human identifier).
        version: ``.trajcenter`` format version.
        created_at: Creation timestamp (UTC).
        source_file: Path or name of the original source file.
        source_format: Source file format (:class:`SourceFormat`).
        robot_model: Target ABB robot model
            (e.g. ``"IRB6700-205/2.80"``).
        point_count: Number of points. Updated automatically at
            ``save()``.
        external_axes: Dict of active external axes.
            Keys: ``"eax_a"`` … ``"eax_f"``.
        autocompleted: List of columns whose values were inferred from
            ``ConversionDefaults`` (not present in the source). Empty
            when all columns come from the source.
        extra: Free field for project-specific metadata.

    Example:
        ::

            meta = TrajectoryMeta(
                name="Pointage_Flan_A",
                robot_model="IRB6700",
                autocompleted=["speed", "move_type"],
                external_axes={
                    "eax_a": ExternalAxisConfig(
                        axis_type="rotational",
                        unit="deg",
                        label="Positionneur A",
                    )
                },
            )
    """

    name: str = Field(..., description="Trajectory name")
    version: str = Field("1.0", description=".trajcenter format version")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Creation timestamp (UTC)",
    )
    source_file: str | None = Field(None, description="Original source file")
    source_format: SourceFormat = Field(SourceFormat.MANUAL)
    robot_model: str | None = Field(None, description="E.g. 'IRB6700-205/2.80'")
    point_count: int = Field(0, description="Updated automatically at save time")
    external_axes: dict[str, ExternalAxisConfig] = Field(
        default_factory=dict,
        description=("Active external axes. Keys: 'eax_a'…'eax_f'. Absent = inactive."),
    )
    autocompleted: list[str] = Field(
        default_factory=list,
        description=(
            "Columns whose values were autocompleted from ConversionDefaults. "
            "E.g.: ['speed', 'move_type', 'cf1']. "
            "Empty when all columns come from the source."
        ),
    )
    extra: dict[str, str | int | float | bool | None] = Field(
        default_factory=dict,
        description="Free field for project-specific metadata.",
    )

    @model_validator(mode="after")
    def _validate_eax_keys(self) -> TrajectoryMeta:
        """Verify that external axis keys belong to the valid set.

        Returns:
            The validated instance.

        Raises:
            ValueError: If a key does not match ``eax_a``…``eax_f``.
        """
        valid = {f"eax_{c}" for c in "abcdef"}
        for key in self.external_axes:
            if key not in valid:
                raise ValueError(
                    f"Invalid external axis key: '{key}'. "
                    f"Expected one of: {sorted(valid)}"
                )
        return self


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------


class Trajectory:
    """ABB robot trajectory.

    Encapsulates metadata (:class:`TrajectoryMeta`), trajectory points
    (``pandas.DataFrame``), and tool/wobj naming tables in a coherent
    object.

    The ``.trajcenter`` file format is a ZIP archive containing:

    - ``meta.json``      : JSON metadata
    - ``points.parquet`` : points (PyArrow, zstd compression)
    - ``tools.json``     : ordered list of tool names (index → name)
    - ``wobjs.json``     : ordered list of wobj names (index → name)

    The ``tool_index`` and ``wobj_index`` columns of the ``DataFrame``
    are ``int16`` integers referencing the ``tools`` and ``wobjs`` lists.

    A ``.trajcenter`` produced by a converter is **always complete**:
    the columns ``cf1/cf4/cf6/cfx``, ``move_type``, ``speed``, ``zone``,
    ``tool_index``, ``wobj_index`` are always present. The ``eax_*``
    columns remain optional (presence = active axis).

    Attributes:
        meta: Trajectory metadata.
        points: Points ``DataFrame``. Mandatory columns:
            ``x, y, z, q1, q2, q3, q4``.
        tools: Ordered list of tool names. ``tools[i]`` = name of tool
            at index ``i``.
        wobjs: Ordered list of wobj names. ``wobjs[i]`` = name of wobj
            at index ``i``.

    Example:
        Create, save and reload::

            import pandas as pd
            from trajcenter.core.trajectory import Trajectory, TrajectoryMeta

            df = pd.DataFrame({
                "x": [100.0, 200.0], "y": [150.0, 250.0], "z": [50.0, 60.0],
                "q1": [1.0, 1.0], "q2": [0.0, 0.0],
                "q3": [0.0, 0.0], "q4": [0.0, 0.0],
                "move_type":  ["MoveL", "MoveL"],
                "speed":      ["v500", "v500"],
                "zone":       ["z0", "z0"],
                "cf1": [0, 0], "cf4": [0, 0], "cf6": [0, 0], "cfx": [0, 0],
                "tool_index": [0, 0],
                "wobj_index": [0, 0],
            })
            meta = TrajectoryMeta(name="test", autocompleted=["speed"])
            traj = Trajectory(
                meta=meta,
                points=df,
                tools=["Tool_formage"],
                wobjs=["Wobj_SerreFlan"],
            )
            traj.save("trajectory_store/test.trajcenter")

            traj2 = Trajectory.load("trajectory_store/test.trajcenter")
            print(traj2)
            # Trajectory(name='test', points=2, tools=1, wobjs=1, eax=none, complete=True)
    """

    meta: TrajectoryMeta
    points: pd.DataFrame
    tools: list[str]
    wobjs: list[str]

    def __init__(
        self,
        meta: TrajectoryMeta,
        points: pd.DataFrame,
        tools: list[str] | None = None,
        wobjs: list[str] | None = None,
    ) -> None:
        """Initialise the trajectory with validation and type casting.

        Args:
            meta: Trajectory metadata.
            points: Points ``DataFrame``. Must contain at minimum the
                columns ``x, y, z, q1, q2, q3, q4``.
            tools: Ordered list of tool names (index → name).
                Initialised to an empty list when ``None``.
            wobjs: Ordered list of wobj names (index → name).
                Initialised to an empty list when ``None``.

        Raises:
            ValueError: If mandatory columns are missing, if a type
                cast fails, or if a ``tool_index`` / ``wobj_index``
                value is out of bounds.
        """
        self.meta = meta
        self.points = self._validate_and_cast(points)
        self.tools = tools or []
        self.wobjs = wobjs or []
        self._validate_index_bounds()

    # ------------------------------------------------------------------
    # Internal validation
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_and_cast(df: pd.DataFrame) -> pd.DataFrame:
        """Verify mandatory columns and normalise pandas types.

        Args:
            df: Raw ``DataFrame`` to validate.

        Returns:
            ``DataFrame`` with normalised types.

        Raises:
            ValueError: If mandatory columns are absent or if a type
                cast is impossible.
        """
        missing = set(REQUIRED_COLUMNS) - set(str(c) for c in df.columns)
        if missing:
            raise ValueError(f"Mandatory columns missing: {sorted(missing)}")

        df = df.copy()

        for col in df.columns:
            col_str = str(col)

            if col_str in COLUMN_DTYPES:
                target = COLUMN_DTYPES[col_str]
                try:
                    df[col] = df[col].astype(target)
                except (ValueError, TypeError) as exc:
                    raise ValueError(
                        f"Cannot cast '{col_str}' to {target}: {exc}"
                    ) from exc

            elif col_str in CONFDATA_COLUMNS:
                try:
                    df[col] = df[col].astype(pd.Int8Dtype())
                except (ValueError, TypeError) as exc:
                    raise ValueError(f"Cannot cast '{col_str}' to Int8: {exc}") from exc

        return df

    def _validate_index_bounds(self) -> None:
        """Verify that tool/wobj indices do not exceed the table sizes.

        No-op if the ``DataFrame`` has no rows (empty trajectory under
        construction).

        Raises:
            ValueError: If a ``tool_index`` or ``wobj_index`` value is
                out of bounds.
        """
        # Guard: an empty DataFrame has no rows to validate — skip entirely.
        if len(self.points) == 0:
            return

        if "tool_index" in self.points.columns and self.tools:
            max_idx = int(self.points["tool_index"].max())
            if max_idx >= len(self.tools):
                raise ValueError(
                    f"tool_index max ({max_idx}) out of bounds "
                    f"(tools contains {len(self.tools)} entries)."
                )
        if "wobj_index" in self.points.columns and self.wobjs:
            max_idx = int(self.points["wobj_index"].max())
            if max_idx >= len(self.wobjs):
                raise ValueError(
                    f"wobj_index max ({max_idx}) out of bounds "
                    f"(wobjs contains {len(self.wobjs)} entries)."
                )

    # ------------------------------------------------------------------
    # Utility properties
    # ------------------------------------------------------------------

    @property
    def point_count(self) -> int:
        """Number of points in the trajectory."""
        return len(self.points)

    @property
    def active_external_axes(self) -> list[str]:
        """List of external axes actually present in the ``DataFrame``.

        Returns:
            Sorted list of ``eax_*`` column names that are present.

        Example:
            ::

                >>> traj.active_external_axes
                ['eax_a', 'eax_b']
        """
        eax_cols = set(EXTERNAL_AXIS_COLUMNS)
        return sorted(c for c in self.points.columns if str(c) in eax_cols)

    @property
    def has_confdata(self) -> bool:
        """Whether robot configuration data (confdata) columns are present."""
        return "cf1" in self.points.columns

    @property
    def has_move_type(self) -> bool:
        """Whether the ``move_type`` column (MoveJ/MoveL/MoveC) is present."""
        return "move_type" in self.points.columns

    @property
    def has_tool_table(self) -> bool:
        """Whether a tool naming table is defined.

        Returns:
            ``True`` if ``tools`` is non-empty and the ``tool_index``
            column is present in the ``DataFrame``.
        """
        return bool(self.tools) and "tool_index" in self.points.columns

    @property
    def has_wobj_table(self) -> bool:
        """Whether a wobj naming table is defined.

        Returns:
            ``True`` if ``wobjs`` is non-empty and the ``wobj_index``
            column is present in the ``DataFrame``.
        """
        return bool(self.wobjs) and "wobj_index" in self.points.columns

    @property
    def is_complete(self) -> bool:
        """Whether all converter columns are present.

        A complete ``.trajcenter`` contains ``cf1/cf4/cf6/cfx``,
        ``move_type``, ``speed``, ``zone``, ``tool_index``,
        ``wobj_index`` in addition to the mandatory geometric columns.

        Returns:
            ``True`` if all :data:`CONVERTER_COLUMNS` are present.
        """
        return all(c in self.points.columns for c in CONVERTER_COLUMNS)

    # ------------------------------------------------------------------
    # Serialisation → .trajcenter
    # ------------------------------------------------------------------

    def save(self, path: str | Path) -> Path:
        """Save the trajectory to a ``.trajcenter`` file.

        The produced file is a ZIP archive containing:

        - ``meta.json``      : metadata (JSON, UTF-8)
        - ``points.parquet`` : points (PyArrow, zstd compression)
        - ``tools.json``     : ordered list of tool names
        - ``wobjs.json``     : ordered list of wobj names

        The parent directory is created automatically when necessary.
        The :attr:`TrajectoryMeta.point_count` counter is updated
        before writing.

        Args:
            path: Destination path (str or Path).
                The ``.trajcenter`` extension is recommended.

        Returns:
            Absolute path of the created file.

        Example:
            ::

                saved_path = traj.save("trajectory_store/pointage.trajcenter")
        """
        dest = Path(path)
        dest.parent.mkdir(parents=True, exist_ok=True)

        self.meta.point_count = self.point_count

        pa_fields: list[pa.Field] = [
            pa.field(str(col), _PA_TYPE_MAP.get(str(col), pa.string()))
            for col in self.points.columns
        ]
        schema = pa.schema(pa_fields)
        table = pa.Table.from_pandas(self.points, schema=schema, preserve_index=False)

        with zipfile.ZipFile(dest, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("meta.json", self.meta.model_dump_json(indent=2))
            zf.writestr(
                "tools.json",
                json.dumps(self.tools, ensure_ascii=False, indent=2),
            )
            zf.writestr(
                "wobjs.json",
                json.dumps(self.wobjs, ensure_ascii=False, indent=2),
            )
            buf = io.BytesIO()
            pq.write_table(table, buf, compression="zstd")
            zf.writestr("points.parquet", buf.getvalue())

        return dest.resolve()

    # ------------------------------------------------------------------
    # Deserialisation ← .trajcenter
    # ------------------------------------------------------------------

    @classmethod
    def load(cls, path: str | Path) -> Trajectory:
        """Load a trajectory from a ``.trajcenter`` file.

        The ``tools.json`` and ``wobjs.json`` entries are optional to
        ensure compatibility with potential legacy files.

        Args:
            path: Path to the ``.trajcenter`` file to load.

        Returns:
            Reconstructed :class:`Trajectory` instance.

        Raises:
            FileNotFoundError: If the file does not exist.
            ValueError: If the archive does not contain the mandatory
                entries (``meta.json``, ``points.parquet``).

        Example:
            ::

                traj = Trajectory.load("trajectory_store/pointage.trajcenter")
                print(traj.point_count)
                print(traj.tools)               # ['Tool_formage']
                print(traj.meta.autocompleted)  # ['speed']
        """
        src = Path(path)
        if not src.exists():
            raise FileNotFoundError(f"File not found: {src}")

        with zipfile.ZipFile(src, "r") as zf:
            names = set(zf.namelist())
            missing = _REQUIRED_ZIP_ENTRIES - names
            if missing:
                raise ValueError(
                    f"Invalid .trajcenter archive — missing entries "
                    f"{sorted(missing)}: {src}"
                )

            meta = TrajectoryMeta.model_validate_json(zf.read("meta.json"))
            tools: list[str] = (
                json.loads(zf.read("tools.json")) if "tools.json" in names else []
            )
            wobjs: list[str] = (
                json.loads(zf.read("wobjs.json")) if "wobjs.json" in names else []
            )
            buf = io.BytesIO(zf.read("points.parquet"))
            points = pq.read_table(buf).to_pandas()

        return cls(meta=meta, points=points, tools=tools, wobjs=wobjs)

    # ------------------------------------------------------------------
    # Representation
    # ------------------------------------------------------------------

    @override
    def __repr__(self) -> str:
        """Concise representation for debugging.

        Returns:
            String of the form
            ``Trajectory(name='...', points=N, tools=T, wobjs=W,
            eax=[...], complete=bool)``.
        """
        eax = self.active_external_axes
        return (
            f"Trajectory("
            f"name={self.meta.name!r}, "
            f"points={self.point_count:,}, "
            f"tools={len(self.tools)}, "
            f"wobjs={len(self.wobjs)}, "
            f"eax={eax if eax else 'none'}, "
            f"complete={self.is_complete}"
            f")"
        )
