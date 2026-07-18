#!/usr/bin/env python3
# trajcenter/core/trajectory.py
"""Central data model for TrajCenter v2 trajectory archives.

Author: Clement RACINET

This module defines the local ``.trajcenter`` archive format used by
TrajCenter v2. A trajectory archive is independent from a target ABB
cell: tools, work-objects, speeds and zones may be stored point by point,
but they are resolved against the connected robot only during the RWS
transfer phase.

``.trajcenter`` file format
---------------------------
ZIP archive containing at minimum:

- ``meta.json``: serialised metadata.
- ``points.parquet``: trajectory points.

Optional entry:

- ``process_params.parquet``: process parameter table, present only when
  ``meta.process.process_type > 0``.

ABB RAPID conventions
---------------------
- Quaternions: ``[q1, q2, q3, q4] = [w, x, y, z]``.
- External axes: ``eax_a`` … ``eax_f``. Absent column means inactive axis.
- The RWS inactive-axis sentinel ``9E+9`` is never stored in
  ``.trajcenter``. It is injected only by the RWS serialisation layer.
- RAPID arrays are 1-based, but DataFrame rows keep their natural order.

Process convention
------------------
When ``process_type == 0``:

- ``process_param_index`` is not required in ``points.parquet``.
- ``process_params.parquet`` is absent.
- ``process_param_names`` is empty.

When ``process_type > 0``:

- ``process_param_names`` is required.
- ``points.parquet`` must contain ``process_param_index``.
- ``process_params.parquet`` must exist.
- ``process_params.parquet`` is a human-readable wide table:

  ``process_param_index | force | speed | pressure | ...``

- parameter columns must match ``meta.process.process_param_names``.
- ``process_param_index = 0`` on a point means no process parameter set.
- ``process_param_index = 1..256`` references a row in
  ``process_params.parquet``.

Example:
    Create and save an exportable trajectory::

        import pandas as pd
        from trajcenter.core.trajectory import Trajectory, TrajectoryMeta

        points = pd.DataFrame({
            "x": [100.0],
            "y": [200.0],
            "z": [300.0],
            "q1": [1.0],
            "q2": [0.0],
            "q3": [0.0],
            "q4": [0.0],
            "move_type": ["MoveL"],
            "tool_name": ["Tool_A"],
            "wobj_name": ["Wobj_A"],
        })

        traj = Trajectory(meta=TrajectoryMeta(name="demo"), points=points)
        traj.save("trajectory_store/demo.trajcenter")
"""

from __future__ import annotations

import io
import zipfile
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import cast

from typing_extensions import override

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from pydantic import BaseModel, Field, model_validator

from trajcenter.core.messages import msg


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class SourceFormat(StrEnum):
    """Origin format of the source file that produced the trajectory."""

    EXCEL = "excel"
    APT = "apt"
    CSV = "csv"
    RAPID = "rapid"
    MANUAL = "manual"
    TRAJCENTER = "trajcenter"


class MoveType(StrEnum):
    """Canonical movement type stored in ``points.parquet``."""

    MOVE_J = "MoveJ"
    MOVE_L = "MoveL"
    MOVE_C = "MoveC"


# ---------------------------------------------------------------------------
# Schema constants
# ---------------------------------------------------------------------------

REQUIRED_COLUMNS: list[str] = ["x", "y", "z", "q1", "q2", "q3", "q4"]

CONFDATA_COLUMNS: frozenset[str] = frozenset({"cf1", "cf4", "cf6", "cfx"})

CONVERTER_COLUMNS: list[str] = [
    "cf1",
    "cf4",
    "cf6",
    "cfx",
    "move_type",
]

SEND_OPTIONAL_COLUMNS: list[str] = [
    "tcp_speed",
    "zone_type",
    "tool_name",
    "wobj_name",
    "readconfs",
    "process_param_index",
]

EXTERNAL_AXIS_COLUMNS: list[str] = [
    "eax_a",
    "eax_b",
    "eax_c",
    "eax_d",
    "eax_e",
    "eax_f",
]

OPTIONAL_COLUMNS: list[str] = (
    CONVERTER_COLUMNS + SEND_OPTIONAL_COLUMNS + EXTERNAL_AXIS_COLUMNS
)

MAX_PROCESS_PARAM_SET_COUNT: int = 256
MAX_PROCESS_PARAM_PER_SET: int = 10

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
    "tcp_speed": np.dtype("float64"),
}

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
    "tcp_speed": pa.float64(),
    "zone_type": pa.int16(),
    "move_type": pa.string(),
    "tool_name": pa.string(),
    "wobj_name": pa.string(),
    "readconfs": pa.bool_(),
    "process_param_index": pa.int16(),
}

_PROCESS_PARAM_INDEX_COLUMN = "process_param_index"
_REQUIRED_ZIP_ENTRIES: frozenset[str] = frozenset({"meta.json", "points.parquet"})
_PROCESS_PARAMS_ENTRY = "process_params.parquet"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_parquet_table(
    table: pa.Table,
    sink: io.BytesIO,
    *,
    compression: str,
) -> None:
    """Write a PyArrow table to an in-memory Parquet buffer.

    ABB Route:
        N/A — local ``.trajcenter`` archive serialization.

    ABB Constraints:
        The RWS inactive-axis sentinel ``9E+9`` is never written to the
        ``.trajcenter`` archive. It is injected only during RWS transfer.

    Args:
        table: PyArrow table to serialize.
        sink: In-memory binary buffer receiving Parquet bytes.
        compression: Parquet compression codec name.

    Returns:
        None.

    Raises:
        OSError: If PyArrow cannot write the table to the buffer.
        ValueError: If the table schema is invalid for Parquet.

    Example:
        ::

            buffer = io.BytesIO()
            _write_parquet_table(table, buffer, compression="zstd")
    """
    pq.write_table(table, sink, compression=compression)  # type: ignore[no-untyped-call]


def _read_parquet_table(source: io.BytesIO) -> pd.DataFrame:
    """Read a PyArrow Parquet buffer as a pandas DataFrame.

    ABB Route:
        N/A — local ``.trajcenter`` archive deserialization.

    ABB Constraints:
        The ``.trajcenter`` archive must not contain ``9E+9`` sentinel
        values for inactive external axes.

    Args:
        source: In-memory binary buffer containing Parquet bytes.

    Returns:
        Deserialized pandas DataFrame.

    Raises:
        OSError: If the Parquet payload cannot be read.
        ValueError: If the Parquet payload is invalid.

    Example:
        ::

            points = _read_parquet_table(buffer)
    """
    table = pq.read_table(source)  # type: ignore[no-untyped-call]
    return cast(pd.DataFrame, table.to_pandas())


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class ExternalAxisConfig(BaseModel):
    """Description of an active external axis in the trajectory."""

    axis_type: str = Field(..., description="'rotational' or 'linear'")
    unit: str = Field(..., description="'deg' or 'mm'")
    label: str | None = Field(None, description="Human-readable axis label")


class TrajectoryProcess(BaseModel):
    """Process configuration stored in ``meta.json``.

    Attributes:
        process_type: Numeric process identifier. ``0`` means no process.
        process_param_names: Ordered parameter names. Position in this
            list maps to the RAPID slot index ``1..10``.

    Example:
        ::

            TrajectoryProcess(
                process_type=1,
                process_param_names=["force", "speed"],
            )
    """

    process_type: int = Field(0, ge=0, description="0 = NONE")
    process_param_names: list[str] = Field(
        default_factory=list,
        description="Ordered process parameter names, max 10 entries.",
    )

    @model_validator(mode="after")
    def _validate_process(self) -> TrajectoryProcess:
        """Validate process parameter metadata.

        ABB Route:
            N/A — local metadata validation.

        ABB Constraints:
            No ABB controller access.

        Args:
            None.

        Returns:
            The validated process metadata.

        Raises:
            ValueError: If the process metadata is inconsistent.

        Example:
            ::

                process = TrajectoryProcess(process_type=1, process_param_names=["force"])
        """
        if self.process_type == 0 and self.process_param_names:
            raise ValueError("process_param_names must be empty when process_type is 0")

        if len(self.process_param_names) > MAX_PROCESS_PARAM_PER_SET:
            raise ValueError(
                f"process_param_names has more than {MAX_PROCESS_PARAM_PER_SET} entries"
            )

        cleaned = [name.strip() for name in self.process_param_names]
        if any(name == "" for name in cleaned):
            raise ValueError("process_param_names must not contain empty names")

        if len(set(cleaned)) != len(cleaned):
            raise ValueError("process_param_names must be unique")

        self.process_param_names = cleaned
        return self


class TrajectoryMeta(BaseModel):
    """Metadata stored in ``meta.json``."""

    name: str = Field(..., description="Trajectory name")
    version: str = Field("2.0", description=".trajcenter format version")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Creation timestamp UTC",
    )
    source_file: str | None = Field(None, description="Original source file")
    source_format: SourceFormat = Field(SourceFormat.MANUAL)
    robot_model: str | None = Field(None, description="ABB robot model")
    point_count: int = Field(0, description="Updated automatically at save time")
    external_axes: dict[str, ExternalAxisConfig] = Field(default_factory=dict)
    autocompleted: list[str] = Field(default_factory=list)
    process: TrajectoryProcess = Field(
        default_factory=lambda: TrajectoryProcess(),
    )
    extra: dict[str, str | int | float | bool | None] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_eax_keys(self) -> TrajectoryMeta:
        """Verify that external axis keys belong to ``eax_a``…``eax_f``.

        ABB Route:
            N/A — local metadata validation.

        ABB Constraints:
            No ABB controller access.

        Args:
            None.

        Returns:
            The validated metadata.

        Raises:
            ValueError: If an external axis key is invalid.

        Example:
            ::

                meta = TrajectoryMeta(name="demo")
        """
        valid = {f"eax_{c}" for c in "abcdef"}
        for key in self.external_axes:
            if key not in valid:
                raise ValueError(
                    msg(
                        "INVALID_EAX_KEY",
                        key=key,
                        valid=sorted(valid),
                    )
                )
        return self


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------


class Trajectory:
    """TrajCenter v2 trajectory.

    Args:
        meta: Trajectory metadata.
        points: Point table. Must contain at least
            ``x, y, z, q1, q2, q3, q4``.
        process_params: Optional process parameter table. Required when
            ``meta.process.process_type > 0``.

    Raises:
        ValueError: If point columns or process data are inconsistent.
    """

    meta: TrajectoryMeta
    points: pd.DataFrame
    process_params: pd.DataFrame | None

    def __init__(
        self,
        meta: TrajectoryMeta,
        points: pd.DataFrame,
        process_params: pd.DataFrame | None = None,
    ) -> None:
        """Initialise a trajectory with schema validation.

        ABB Route:
            N/A — local trajectory construction.

        ABB Constraints:
            No ABB controller access.

        Args:
            meta: Trajectory metadata.
            points: Point DataFrame.
            process_params: Optional process parameter DataFrame.

        Returns:
            None.

        Raises:
            ValueError: If the trajectory is not valid.

        Example:
            ::

                traj = Trajectory(meta=meta, points=points)
        """
        self.meta = meta
        self.points = self._validate_and_cast_points(points)
        self.process_params = self._validate_and_cast_process_params(process_params)
        self._validate_process_consistency()

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_and_cast_points(df: pd.DataFrame) -> pd.DataFrame:
        """Validate mandatory point columns and cast known dtypes.

        ABB Route:
            N/A — local DataFrame validation.

        ABB Constraints:
            No ABB controller access.

        Args:
            df: Raw point DataFrame.

        Returns:
            Validated and cast copy of the input DataFrame.

        Raises:
            ValueError: If mandatory columns are missing or casting fails.

        Example:
            ::

                points = Trajectory._validate_and_cast_points(points)
        """
        missing = set(REQUIRED_COLUMNS) - set(str(c) for c in df.columns)
        if missing:
            raise ValueError(msg("MANDATORY_COLUMNS_MISSING", cols=sorted(missing)))

        out = df.copy()

        for col in out.columns:
            col_str = str(col)

            if col_str in COLUMN_DTYPES:
                target = COLUMN_DTYPES[col_str]
                try:
                    out[col] = out[col].astype(target)
                except (ValueError, TypeError) as exc:
                    raise ValueError(
                        msg("CANNOT_CAST_COLUMN", col=col_str, dtype=target, exc=exc)
                    ) from exc

            elif col_str in CONFDATA_COLUMNS:
                try:
                    out[col] = out[col].astype(pd.Int8Dtype())
                except (ValueError, TypeError) as exc:
                    raise ValueError(
                        msg("CANNOT_CAST_COLUMN", col=col_str, dtype="Int8", exc=exc)
                    ) from exc

            elif col_str in {"zone_type", "process_param_index"}:
                try:
                    out[col] = out[col].astype(pd.Int16Dtype())
                except (ValueError, TypeError) as exc:
                    raise ValueError(
                        msg("CANNOT_CAST_COLUMN", col=col_str, dtype="Int16", exc=exc)
                    ) from exc

            elif col_str == "readconfs":
                try:
                    out[col] = out[col].astype("boolean")
                except (ValueError, TypeError) as exc:
                    raise ValueError(
                        msg("CANNOT_CAST_COLUMN", col=col_str, dtype="boolean", exc=exc)
                    ) from exc

        return out

    def _validate_and_cast_process_params(
        self,
        df: pd.DataFrame | None,
    ) -> pd.DataFrame | None:
        """Validate and cast process parameter table.

        ABB Route:
            N/A — local process parameter validation.

        ABB Constraints:
            No ABB controller access.

        Args:
            df: Optional raw process parameter table.

        Returns:
            A validated DataFrame or ``None``.

        Raises:
            ValueError: If the process parameter table is invalid.

        Example:
            ::

                process_params = traj._validate_and_cast_process_params(df)
        """
        if df is None:
            return None

        out = df.copy()

        if _PROCESS_PARAM_INDEX_COLUMN not in out.columns:
            raise ValueError(
                "process_params must contain a 'process_param_index' column"
            )

        if len(out) > MAX_PROCESS_PARAM_SET_COUNT:
            raise ValueError(
                f"process_params has {len(out)} rows, "
                f"max is {MAX_PROCESS_PARAM_SET_COUNT}"
            )

        try:
            out[_PROCESS_PARAM_INDEX_COLUMN] = out[_PROCESS_PARAM_INDEX_COLUMN].astype(
                pd.Int16Dtype()
            )
        except (ValueError, TypeError) as exc:
            raise ValueError("Cannot cast process_param_index to Int16") from exc

        indexes = out[_PROCESS_PARAM_INDEX_COLUMN].dropna().astype(int)
        if ((indexes < 1) | (indexes > MAX_PROCESS_PARAM_SET_COUNT)).any():
            raise ValueError(
                "process_param_index values in process_params must be in 1..256"
            )

        if indexes.duplicated().any():
            raise ValueError(
                "process_param_index values in process_params must be unique"
            )

        param_cols = [
            str(col) for col in out.columns if str(col) != _PROCESS_PARAM_INDEX_COLUMN
        ]
        if len(param_cols) > MAX_PROCESS_PARAM_PER_SET:
            raise ValueError(
                f"process_params has more than {MAX_PROCESS_PARAM_PER_SET} "
                "parameter columns"
            )

        for col in param_cols:
            try:
                out[col] = out[col].astype("float64")
            except (ValueError, TypeError) as exc:
                raise ValueError(
                    f"Cannot cast process parameter column {col!r} to float64"
                ) from exc

        return out

    def _validate_process_consistency(self) -> None:
        """Validate consistency between metadata, points and process params.

        ABB Route:
            N/A — local trajectory validation.

        ABB Constraints:
            A non-zero process type means the process is active and must
            provide parameter names, point references and a parameter table.

        Args:
            None.

        Returns:
            None.

        Raises:
            ValueError: If process metadata and data are inconsistent.

        Example:
            ::

                traj._validate_process_consistency()
        """
        process = self.meta.process

        if process.process_type == 0:
            if self.process_params is not None:
                raise ValueError("process_params must be None when process_type is 0")
            return

        if not process.process_param_names:
            raise ValueError("process_param_names is required when process_type > 0")

        if _PROCESS_PARAM_INDEX_COLUMN not in self.points.columns:
            raise ValueError(
                "points must contain process_param_index when process_type > 0"
            )

        if self.process_params is None:
            raise ValueError("process_params is required when process_type > 0")

        expected_cols = set(process.process_param_names)
        actual_cols = {
            str(col)
            for col in self.process_params.columns
            if str(col) != _PROCESS_PARAM_INDEX_COLUMN
        }
        if actual_cols != expected_cols:
            raise ValueError(
                "process_params parameter columns must match "
                "meta.process.process_param_names"
            )

        point_indexes = self.points[_PROCESS_PARAM_INDEX_COLUMN].fillna(0).astype(int)
        if ((point_indexes < 0) | (point_indexes > MAX_PROCESS_PARAM_SET_COUNT)).any():
            raise ValueError("process_param_index values in points must be in 0..256")

        available_indexes = set(
            self.process_params[_PROCESS_PARAM_INDEX_COLUMN].dropna().astype(int)
        )
        used_indexes = set(int(v) for v in point_indexes if int(v) != 0)
        missing = sorted(used_indexes - available_indexes)
        if missing:
            raise ValueError(
                f"points reference missing process_param_index values: {missing}"
            )

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def point_count(self) -> int:
        """Number of trajectory points.

        Returns:
            Number of rows in ``points``.
        """
        return len(self.points)

    @property
    def active_external_axes(self) -> list[str]:
        """Active external axis columns present in the point table.

        Returns:
            Sorted list of ``eax_*`` columns.
        """
        eax_cols = set(EXTERNAL_AXIS_COLUMNS)
        return sorted(str(c) for c in self.points.columns if str(c) in eax_cols)

    @property
    def has_confdata(self) -> bool:
        """Whether all confdata columns are present.

        Returns:
            ``True`` when ``cf1/cf4/cf6/cfx`` are all present.
        """
        return all(col in self.points.columns for col in CONFDATA_COLUMNS)

    @property
    def has_move_type(self) -> bool:
        """Whether the ``move_type`` column is present.

        Returns:
            ``True`` if ``move_type`` exists.
        """
        return "move_type" in self.points.columns

    @property
    def has_process(self) -> bool:
        """Whether this trajectory carries process data.

        Returns:
            ``True`` when ``process_type > 0``.
        """
        return self.meta.process.process_type > 0

    @property
    def has_process_params(self) -> bool:
        """Whether a process parameter table is attached.

        Returns:
            ``True`` when ``process_params`` is not ``None``.
        """
        return self.process_params is not None

    @property
    def is_exportable(self) -> bool:
        """Whether the trajectory contains the required geometry columns.

        Returns:
            Always ``True`` for a constructed instance, because required
            geometry is validated at initialisation.
        """
        return all(col in self.points.columns for col in REQUIRED_COLUMNS)

    @property
    def has_converter_columns(self) -> bool:
        """Whether converter-safe columns are present.

        Returns:
            ``True`` when all ``CONVERTER_COLUMNS`` are present.
        """
        return all(col in self.points.columns for col in CONVERTER_COLUMNS)

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def save(self, path: str | Path) -> Path:
        """Save the trajectory to a ``.trajcenter`` archive.

        ABB Route:
            N/A — local ``.trajcenter`` archive write.

        ABB Constraints:
            The inactive external-axis sentinel ``9E+9`` must not be
            injected here.

        Args:
            path: Destination path.

        Returns:
            Absolute path of the created archive.

        Raises:
            OSError: If the archive cannot be written.
            ValueError: If a DataFrame cannot be converted to Parquet.

        Example:
            ::

                path = traj.save("trajectory_store/demo.trajcenter")
        """
        dest = Path(path)
        dest.parent.mkdir(parents=True, exist_ok=True)

        self.meta.point_count = self.point_count

        point_table = self._dataframe_to_table(self.points)

        with zipfile.ZipFile(dest, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("meta.json", self.meta.model_dump_json(indent=2))

            point_buf = io.BytesIO()
            _write_parquet_table(point_table, point_buf, compression="zstd")
            zf.writestr("points.parquet", point_buf.getvalue())

            if self.process_params is not None:
                process_table = self._dataframe_to_table(self.process_params)
                process_buf = io.BytesIO()
                _write_parquet_table(process_table, process_buf, compression="zstd")
                zf.writestr(_PROCESS_PARAMS_ENTRY, process_buf.getvalue())

        return dest.resolve()

    @classmethod
    def load(cls, path: str | Path) -> Trajectory:
        """Load a trajectory from a ``.trajcenter`` archive.

        ABB Route:
            N/A — local ``.trajcenter`` archive read.

        ABB Constraints:
            No ABB controller access.

        Args:
            path: Path to the archive.

        Returns:
            Loaded trajectory.

        Raises:
            FileNotFoundError: If the archive does not exist.
            ValueError: If mandatory archive entries are missing or if
                trajectory validation fails.

        Example:
            ::

                traj = Trajectory.load("trajectory_store/demo.trajcenter")
        """
        src = Path(path)
        if not src.exists():
            raise FileNotFoundError(msg("FILE_NOT_FOUND", path=src))

        with zipfile.ZipFile(src, "r") as zf:
            names = set(zf.namelist())
            missing_entries = _REQUIRED_ZIP_ENTRIES - names
            if missing_entries:
                raise ValueError(
                    "Invalid .trajcenter archive — missing entries "
                    f"{sorted(missing_entries)}: {src}"
                )

            meta = TrajectoryMeta.model_validate_json(zf.read("meta.json"))

            point_buf = io.BytesIO(zf.read("points.parquet"))
            points = _read_parquet_table(point_buf)

            process_params: pd.DataFrame | None = None
            if _PROCESS_PARAMS_ENTRY in names:
                process_buf = io.BytesIO(zf.read(_PROCESS_PARAMS_ENTRY))
                process_params = _read_parquet_table(process_buf)

        return cls(meta=meta, points=points, process_params=process_params)

    @staticmethod
    def _dataframe_to_table(df: pd.DataFrame) -> pa.Table:
        """Convert a DataFrame to a typed PyArrow table.

        Known TrajCenter columns use explicit schema types. Unknown
        columns are inferred from pandas dtypes, which is required for
        process parameter columns such as ``force`` or ``travel_speed``.

        ABB Route:
            Local ``.trajcenter`` archive serialisation. No RWS route is
            called by this function.

        ABB Constraints:
            The inactive external-axis sentinel ``9E+9`` must not be
            injected here. It belongs only to the RWS serialisation layer.

        Args:
            df: DataFrame to convert.

        Returns:
            PyArrow table with explicit or inferred column types.

        Raises:
            ValueError: If a column dtype cannot be mapped to a PyArrow
                type.

        Example:
            ::

                table = Trajectory._dataframe_to_table(points)
        """
        fields: list[pa.Field] = []

        for col in df.columns:
            col_name = str(col)

            if col_name in _PA_TYPE_MAP:
                fields.append(pa.field(col_name, _PA_TYPE_MAP[col_name]))
                continue

            dtype = df[col].dtype

            if pd.api.types.is_float_dtype(dtype):
                fields.append(pa.field(col_name, pa.float64()))
            elif pd.api.types.is_integer_dtype(dtype):
                fields.append(pa.field(col_name, pa.int64()))
            elif pd.api.types.is_bool_dtype(dtype):
                fields.append(pa.field(col_name, pa.bool_()))
            elif pd.api.types.is_string_dtype(dtype) or pd.api.types.is_object_dtype(
                dtype
            ):
                fields.append(pa.field(col_name, pa.string()))
            else:
                raise ValueError(
                    f"Cannot infer PyArrow type for column {col_name!r} "
                    f"with pandas dtype {dtype!r}"
                )

        schema = pa.schema(fields)
        return pa.Table.from_pandas(df, schema=schema, preserve_index=False)

    # ------------------------------------------------------------------
    # Representation
    # ------------------------------------------------------------------

    @override
    def __repr__(self) -> str:
        """Return a concise debug representation.

        Returns:
            Human-readable trajectory summary.
        """
        eax = self.active_external_axes
        return (
            "Trajectory("
            f"name={self.meta.name!r}, "
            f"points={self.point_count:,}, "
            f"eax={eax if eax else 'none'}, "
            f"process_type={self.meta.process.process_type}, "
            f"process_params={self.has_process_params}, "
            f"exportable={self.is_exportable}"
            ")"
        )
