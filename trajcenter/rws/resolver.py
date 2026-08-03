#!/usr/bin/env python3
# trajcenter/rws/resolver.py
"""Trajectory resolver for TrajCenter ABB RWS transfers.

Author: Clement RACINET

This module converts a local :class:`trajcenter.core.trajectory.Trajectory`
archive into a fully resolved :class:`trajcenter.rws.models.ResolvedTrajectory`
payload.

The resolver is intentionally independent from RWS HTTP calls. It receives the
robot-side context already read by ``trajcenter.rws.reader`` and produces typed
objects ready for the future RWS writer.

ABB Route:
    N/A — local resolution only. The resolved payload is later written through:
    ``POST /rw/rapid/symbol/data/RAPID/{task}/TRAJCENTER_WebServices/...``.

ABB Constraints:
    - RAPID arrays are one-based.
    - ``toolIndex`` and ``wobjIndex`` are one-based indexes resolved from the
      robot-side ``trajTools`` and ``trajWobjs`` arrays.
    - ``processParamIndex = 0`` means no process parameter set.
    - ``processParams`` second dimension contains exactly 10 parameter slots.
    - External inactive axes are kept as ``None`` here. The ``9E+9`` sentinel
      is injected only by the RWS serialization layer.
    - Robot defaults may only be applied when the matching ``hasDefault*`` flag
      is enabled.

Example:
    ```python
    context = await read_robot_context(client)
    resolved = resolve_trajectory(trajectory, context)
    ```
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any, TypeAlias, cast

import pandas as pd

from trajcenter.core.logger import get_logger
from trajcenter.core.trajectory import (
    CONFDATA_COLUMNS,
    EXTERNAL_AXIS_COLUMNS,
    MoveType,
    Trajectory,
)
from trajcenter.rws.constants import (
    ALLOWED_ZONE_TYPES,
    MAX_PROCESS_PARAM_PER_SET,
    MAX_PROCESS_PARAM_SET_COUNT,
    MAX_TRAJ_POINTS,
    MOVE_TYPE_ALIASES,
    MOVE_TYPE_C,
    MOVE_TYPE_J,
    MOVE_TYPE_L,
    PROCESS_NONE,
    ROBTARGET_COLUMNS,
)
from trajcenter.rws.models import (
    ResolvedPoint,
    ResolvedProcessParam,
    ResolvedProcessParamSet,
    ResolvedRobTarget,
    ResolvedTrajectory,
    RobotContext,
)

logger = get_logger(__name__)

ProcessParamTuple: TypeAlias = tuple[
    ResolvedProcessParam,
    ResolvedProcessParam,
    ResolvedProcessParam,
    ResolvedProcessParam,
    ResolvedProcessParam,
    ResolvedProcessParam,
    ResolvedProcessParam,
    ResolvedProcessParam,
    ResolvedProcessParam,
    ResolvedProcessParam,
]

_PROCESS_PARAM_INDEX_COLUMN = "process_param_index"
_READ_CONFS_COLUMN = "readconfs"


def resolve_trajectory(
    trajectory: Trajectory,
    context: RobotContext,
) -> ResolvedTrajectory:
    """Resolve a local trajectory against robot-side context.

    ABB Route:
        N/A — local resolution only.

    ABB Constraints:
        The returned object uses RAPID-ready indexes:
        - ``tool_index`` is base-1.
        - ``wobj_index`` is base-1.
        - ``process_param_index`` is base-1 or ``0``.
        - External inactive axes are represented as ``None``.

    Args:
        trajectory: Local trajectory loaded from a ``.trajcenter`` archive.
        context: Robot-side context read through RWS.

    Returns:
        Resolved trajectory payload ready for RWS writing.

    Raises:
        ValueError: If trajectory data cannot be resolved against robot context.

    Example:
        ```python
        resolved = resolve_trajectory(trajectory, context)
        ```
    """
    _validate_global_constraints(trajectory, context)

    process_index_by_source = _resolve_process_param_sets(trajectory)
    points = tuple(
        _resolve_point(
            row=row,
            context=context,
            process_type=trajectory.meta.process.process_type,
            process_index_by_source=process_index_by_source,
        )
        for _, row in trajectory.points.iterrows()
    )

    process_param_sets = _unique_process_param_sets(process_index_by_source.values())

    resolved = ResolvedTrajectory(
        name=trajectory.meta.name,
        process_type=trajectory.meta.process.process_type,
        points=points,
        process_param_sets=process_param_sets,
    )
    logger.debug(
        "Resolved trajectory %r: %d points, %d process parameter sets",
        resolved.name,
        resolved.point_count,
        len(resolved.process_param_sets),
    )
    return resolved


def _unique_process_param_sets(
    sets: Iterable[ResolvedProcessParamSet],
) -> tuple[ResolvedProcessParamSet, ...]:
    """Return unique process parameter sets ordered by RAPID index.

    ABB Route:
        N/A — local resolution helper.

    ABB Constraints:
        Multiple source ``process_param_index`` values may resolve to the same
        RAPID process parameter set when their parameter values are identical.
        The writer must receive each resolved set only once.

    Args:
        sets: Resolved process parameter sets, possibly with duplicates.

    Returns:
        Unique process parameter sets ordered by base-1 RAPID index.


    Example:
        ```python
        unique = _unique_process_param_sets(mapping.values())
        ```
    """
    unique_by_index: dict[int, ResolvedProcessParamSet] = {}
    for param_set in sets:
        unique_by_index[param_set.index] = param_set

    return tuple(unique_by_index[index] for index in sorted(unique_by_index))


def _validate_global_constraints(
    trajectory: Trajectory,
    context: RobotContext,
) -> None:
    """Validate trajectory-level constraints before point resolution.

    ABB Route:
        N/A — local validation.

    ABB Constraints:
        The robot-side process catalog is authoritative. The PC must not
        transfer a process type unknown by the connected controller.

    Args:
        trajectory: Local trajectory.
        context: Robot-side context.

    Returns:
        None.

    Raises:
        ValueError: If the trajectory exceeds protocol limits or process catalog.

    Example:
        ```python
        _validate_global_constraints(trajectory, context)
        ```
    """
    if trajectory.point_count > MAX_TRAJ_POINTS:
        raise ValueError(
            f"Trajectory has {trajectory.point_count} points but "
            f"MAX_TRAJ_POINTS={MAX_TRAJ_POINTS}"
        )

    process_type = trajectory.meta.process.process_type
    if process_type not in context.process_ids:
        raise ValueError(
            f"Process type {process_type} is not declared in robot process catalog"
        )


def _resolve_point(
    *,
    row: pd.Series,
    context: RobotContext,
    process_type: int,
    process_index_by_source: Mapping[int, ResolvedProcessParamSet],
) -> ResolvedPoint:
    """Resolve one point row into a RAPID-ready point record.

    ABB Route:
        N/A — local resolution only.

    ABB Constraints:
        Missing speed, zone, tool and wobj may only be completed from robot
        defaults when the matching flag is enabled.

    Args:
        row: One trajectory point row.
        context: Robot-side context.
        process_type: Numeric process type.
        process_index_by_source: Mapping from source process parameter index
            to resolved RAPID parameter set.

    Returns:
        Resolved point.

    Raises:
        ValueError: If a required field cannot be resolved.

    Example:
        ```python
        point = _resolve_point(
            row=row,
            context=context,
            process_type=0,
            process_index_by_source={},
        )
        ```
    """
    robtarget = _resolve_robtarget(row)
    move_type = _resolve_move_type(row, context)
    tcp_speed = _resolve_tcp_speed(row, context)
    zone_type = _resolve_zone_type(row, context)
    read_confs = _resolve_read_confs(row, context)
    tool_index = _resolve_tool_index(row, context)
    wobj_index = _resolve_wobj_index(row, context)
    process_param_index = _resolve_point_process_index(
        row=row,
        process_type=process_type,
        process_index_by_source=process_index_by_source,
    )

    return ResolvedPoint(
        move_type=move_type,
        robtarget=robtarget,
        tcp_speed=tcp_speed,
        zone_type=zone_type,
        read_confs=read_confs,
        tool_index=tool_index,
        wobj_index=wobj_index,
        process_param_index=process_param_index,
    )


def _resolve_robtarget(row: pd.Series) -> ResolvedRobTarget:
    """Resolve robtarget coordinates, quaternion, confdata and external axes.

    ABB Route:
        N/A — local resolution only.

    ABB Constraints:
        ``9E+9`` is not injected here. Missing or NaN external axes are kept as
        ``None`` for the writer serialization step.

    Args:
        row: One trajectory point row.

    Returns:
        Resolved robtarget.

    Raises:
        ValueError: If one mandatory geometry value is missing.

    Example:
        ```python
        robtarget = _resolve_robtarget(row)
        ```
    """
    missing = [column for column in ROBTARGET_COLUMNS if _is_missing(row.get(column))]
    if missing:
        raise ValueError(
            f"Cannot resolve robtarget, missing columns or values: {missing}"
        )

    return ResolvedRobTarget(
        x=_to_float(row["x"], name="x"),
        y=_to_float(row["y"], name="y"),
        z=_to_float(row["z"], name="z"),
        q1=_to_float(row["q1"], name="q1"),
        q2=_to_float(row["q2"], name="q2"),
        q3=_to_float(row["q3"], name="q3"),
        q4=_to_float(row["q4"], name="q4"),
        cf1=_resolve_confdata_value(row, "cf1"),
        cf4=_resolve_confdata_value(row, "cf4"),
        cf6=_resolve_confdata_value(row, "cf6"),
        cfx=_resolve_confdata_value(row, "cfx"),
        eax=(
            _resolve_optional_float(row, "eax_a"),
            _resolve_optional_float(row, "eax_b"),
            _resolve_optional_float(row, "eax_c"),
            _resolve_optional_float(row, "eax_d"),
            _resolve_optional_float(row, "eax_e"),
            _resolve_optional_float(row, "eax_f"),
        ),
    )


def _resolve_confdata_value(row: pd.Series, column: str) -> int:
    """Resolve one confdata value.

    ABB Route:
        N/A — local resolution only.

    ABB Constraints:
        Missing confdata defaults to ``0``. The ``read_confs`` flag controls
        whether RAPID should use confdata.

    Args:
        row: One trajectory point row.
        column: Confdata column name.

    Returns:
        Integer confdata component.

    Raises:
        ValueError: If the value cannot be converted to integer.

    Example:
        ```python
        cf1 = _resolve_confdata_value(row, "cf1")
        ```
    """
    if column not in CONFDATA_COLUMNS:
        raise ValueError(f"Unsupported confdata column {column!r}")

    value = row.get(column)
    if _is_missing(value):
        return 0
    return _to_int(value, name=column)


def _resolve_optional_float(row: pd.Series, column: str) -> float | None:
    """Resolve an optional floating point column.

    ABB Route:
        N/A — local resolution only.

    ABB Constraints:
        External inactive axes are represented as ``None`` until RWS
        serialization.

    Args:
        row: One trajectory point row.
        column: Optional float column.

    Returns:
        Float value or ``None``.

    Raises:
        ValueError: If the column name is not an external axis column.

    Example:
        ```python
        eax_a = _resolve_optional_float(row, "eax_a")
        ```
    """
    if column not in EXTERNAL_AXIS_COLUMNS:
        raise ValueError(f"Unsupported external axis column {column!r}")

    value = row.get(column)
    if _is_missing(value):
        return None
    return _to_float(value, name=column)


def _resolve_move_type(row: pd.Series, context: RobotContext) -> int:
    """Resolve the movement type code.

    ABB Route:
        N/A — local resolution only.

    ABB Constraints:
        TrajCenter canonical strings are ``MoveJ``, ``MoveL`` and ``MoveC``.
        Missing values use the robot default movement type.

    Args:
        row: One trajectory point row.
        context: Robot-side context.

    Returns:
        Movement type code.

    Raises:
        ValueError: If the movement type is unsupported.

    Example:
        ```python
        move_type = _resolve_move_type(row, context)
        ```
    """
    value = row.get("move_type")
    if _is_missing(value):
        return context.defaults.move_type

    if isinstance(value, MoveType):
        value = value.value

    normalized = str(value).strip().lower()
    if normalized in MOVE_TYPE_ALIASES:
        return MOVE_TYPE_ALIASES[normalized]

    raise ValueError(f"Unsupported move_type {value!r}")


def _resolve_tcp_speed(row: pd.Series, context: RobotContext) -> float:
    """Resolve TCP speed.

    ABB Route:
        N/A — local resolution only.

    ABB Constraints:
        If missing, ``defaultTcpSpeed`` may only be used when
        ``hasDefaultTcpSpeed`` is ``TRUE`` on the robot.

    Args:
        row: One trajectory point row.
        context: Robot-side context.

    Returns:
        TCP speed in mm/s.

    Raises:
        ValueError: If no speed can be resolved.

    Example:
        ```python
        speed = _resolve_tcp_speed(row, context)
        ```
    """
    value = row.get("tcp_speed")
    if not _is_missing(value):
        return _to_float(value, name="tcp_speed")

    if context.defaults.has_tcp_speed and context.defaults.tcp_speed is not None:
        return context.defaults.tcp_speed

    raise ValueError("Missing tcp_speed and robot defaultTcpSpeed is disabled")


def _resolve_zone_type(row: pd.Series, context: RobotContext) -> int:
    """Resolve ABB zone type.

    ABB Route:
        N/A — local resolution only.

    ABB Constraints:
        If missing, ``defaultZoneType`` may only be used when
        ``hasDefaultZoneType`` is ``TRUE`` on the robot.

    Args:
        row: One trajectory point row.
        context: Robot-side context.

    Returns:
        Zone type code.

    Raises:
        ValueError: If no zone can be resolved or if the zone is unsupported.

    Example:
        ```python
        zone = _resolve_zone_type(row, context)
        ```
    """
    value = row.get("zone_type")
    if not _is_missing(value):
        zone_type = _to_int(value, name="zone_type")
    elif context.defaults.has_zone_type and context.defaults.zone_type is not None:
        zone_type = context.defaults.zone_type
    else:
        raise ValueError("Missing zone_type and robot defaultZoneType is disabled")

    if zone_type not in ALLOWED_ZONE_TYPES:
        raise ValueError(f"Unsupported zone_type {zone_type}")

    return zone_type


def _resolve_read_confs(row: pd.Series, context: RobotContext) -> bool:
    """Resolve ``readConfs`` flag.

    ABB Route:
        N/A — local resolution only.

    ABB Constraints:
        Missing ``readconfs`` values use the robot default.

    Args:
        row: One trajectory point row.
        context: Robot-side context.

    Returns:
        Boolean readConfs value.

    Raises:
        ValueError: If the value cannot be interpreted as boolean.

    Example:
        ```python
        read_confs = _resolve_read_confs(row, context)
        ```
    """
    value = row.get(_READ_CONFS_COLUMN)
    if _is_missing(value):
        return context.defaults.read_confs

    if isinstance(value, bool):
        return value

    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes"}:
            return True
        if normalized in {"false", "0", "no"}:
            return False

    return bool(value)


def _resolve_tool_index(row: pd.Series, context: RobotContext) -> int:
    """Resolve tool name to RAPID base-1 index.

    ABB Route:
        N/A — local resolution only.

    ABB Constraints:
        ``toolIndex`` is a base-1 index in ``trajTools``. Missing tool name
        may only use ``defaultToolName`` when enabled on the robot.

    Args:
        row: One trajectory point row.
        context: Robot-side context.

    Returns:
        Base-1 tool index.

    Raises:
        ValueError: If no valid tool can be resolved.

    Example:
        ```python
        tool_index = _resolve_tool_index(row, context)
        ```
    """
    value = row.get("tool_name")
    if _is_missing(value):
        if context.defaults.has_tool_name and context.defaults.tool_name is not None:
            value = context.defaults.tool_name
        else:
            raise ValueError("Missing tool_name and robot defaultToolName is disabled")

    tool_name = str(value).strip()
    try:
        return context.tool_index_by_name[tool_name]
    except KeyError as exc:
        raise ValueError(
            f"Tool {tool_name!r} is not declared in robot trajTools"
        ) from exc


def _resolve_wobj_index(row: pd.Series, context: RobotContext) -> int:
    """Resolve workobject name to RAPID base-1 index.

    ABB Route:
        N/A — local resolution only.

    ABB Constraints:
        ``wobjIndex`` is a base-1 index in ``trajWobjs``. Missing workobject
        may only use ``defaultWobjName`` when enabled on the robot.

    Args:
        row: One trajectory point row.
        context: Robot-side context.

    Returns:
        Base-1 workobject index.

    Raises:
        ValueError: If no valid workobject can be resolved.

    Example:
        ```python
        wobj_index = _resolve_wobj_index(row, context)
        ```
    """
    value = row.get("wobj_name")
    if _is_missing(value):
        if context.defaults.has_wobj_name and context.defaults.wobj_name is not None:
            value = context.defaults.wobj_name
        else:
            raise ValueError("Missing wobj_name and robot defaultWobjName is disabled")

    wobj_name = str(value).strip()
    try:
        return context.wobj_index_by_name[wobj_name]
    except KeyError as exc:
        raise ValueError(
            f"Workobject {wobj_name!r} is not declared in robot trajWobjs"
        ) from exc


def _resolve_point_process_index(
    *,
    row: pd.Series,
    process_type: int,
    process_index_by_source: Mapping[int, ResolvedProcessParamSet],
) -> int:
    """Resolve one point process parameter index.

    ABB Route:
        N/A — local resolution only.

    ABB Constraints:
        ``processParamIndex = 0`` means no process parameters.

    Args:
        row: One trajectory point row.
        process_type: Numeric process type.
        process_index_by_source: Mapping from source index to resolved set.

    Returns:
        Resolved process parameter index.

    Raises:
        ValueError: If a point references an unresolved process parameter set.

    Example:
        ```python
        index = _resolve_point_process_index(
            row=row,
            process_type=1,
            process_index_by_source={1: param_set},
        )
        ```
    """
    if process_type == PROCESS_NONE:
        return 0

    value = row.get(_PROCESS_PARAM_INDEX_COLUMN)
    if _is_missing(value):
        return 0

    source_index = _to_int(value, name="process_param_index")
    if source_index == 0:
        return 0

    try:
        return process_index_by_source[source_index].index
    except KeyError as exc:
        raise ValueError(
            f"Point references unresolved process_param_index {source_index}"
        ) from exc


def _resolve_process_param_sets(
    trajectory: Trajectory,
) -> dict[int, ResolvedProcessParamSet]:
    """Resolve and deduplicate process parameter sets.

    ABB Route:
        N/A — local resolution only.

    ABB Constraints:
        - No process means no parameter sets.
        - Only parameter sets referenced by points are transferred.
        - Sets with identical parameter values share the same RAPID index.
        - Parameter slot order follows ``meta.process.process_param_names``.
          This is the order stored in ``meta.json`` and documented by the
          local archive format.

    Args:
        trajectory: Local trajectory.

    Returns:
        Mapping from source ``process_param_index`` to resolved parameter set.

    Raises:
        ValueError: If process tables are inconsistent or limits are exceeded.

    Example:
        ```python
        mapping = _resolve_process_param_sets(trajectory)
        ```
    """
    if trajectory.meta.process.process_type == PROCESS_NONE:
        return {}

    if trajectory.process_params is None:
        raise ValueError("process_params is required when process_type > 0")

    param_names = tuple(trajectory.meta.process.process_param_names)
    if len(param_names) > MAX_PROCESS_PARAM_PER_SET:
        raise ValueError(
            f"Process has {len(param_names)} params but "
            f"MAX_PROCESS_PARAM_PER_SET={MAX_PROCESS_PARAM_PER_SET}"
        )

    used_source_indexes = _used_process_source_indexes(trajectory.points)
    if not used_source_indexes:
        return {}

    row_by_source_index = _process_param_rows_by_index(trajectory.process_params)

    key_to_resolved_set: dict[tuple[float, ...], ResolvedProcessParamSet] = {}
    source_to_resolved_set: dict[int, ResolvedProcessParamSet] = {}

    for source_index in used_source_indexes:
        try:
            process_row = row_by_source_index[source_index]
        except KeyError as exc:
            raise ValueError(
                f"Missing process parameter row for process_param_index {source_index}"
            ) from exc

        values = tuple(_to_float(process_row[name], name=name) for name in param_names)

        if values not in key_to_resolved_set:
            next_index = len(key_to_resolved_set) + 1
            if next_index > MAX_PROCESS_PARAM_SET_COUNT:
                raise ValueError(
                    "Resolved process parameter set count exceeds "
                    f"{MAX_PROCESS_PARAM_SET_COUNT}"
                )
            key_to_resolved_set[values] = ResolvedProcessParamSet(
                index=next_index,
                params=_build_process_param_slots(param_names, values),
            )

        source_to_resolved_set[source_index] = key_to_resolved_set[values]

    return source_to_resolved_set


def _used_process_source_indexes(points: pd.DataFrame) -> list[int]:
    """Return sorted non-zero process parameter indexes used by points.

    ABB Route:
        N/A — local resolution only.

    ABB Constraints:
        ``0`` means no process parameter set and is not transferred.

    Args:
        points: Trajectory point table.

    Returns:
        Sorted list of source process parameter indexes.

    Raises:
        ValueError: If the process index column is missing.

    Example:
        ```python
        indexes = _used_process_source_indexes(points)
        ```
    """
    if _PROCESS_PARAM_INDEX_COLUMN not in points.columns:
        raise ValueError(
            "points must contain process_param_index when process is active"
        )

    values = points[_PROCESS_PARAM_INDEX_COLUMN].fillna(0).astype(int)
    return sorted({int(value) for value in values if int(value) != 0})


def _process_param_rows_by_index(
    process_params: pd.DataFrame,
) -> dict[int, pd.Series]:
    """Build a mapping from source process index to process parameter row.

    ABB Route:
        N/A — local resolution only.

    ABB Constraints:
        Source indexes are stored in ``process_params.process_param_index``.

    Args:
        process_params: Process parameter table.

    Returns:
        Mapping from source process index to row.

    Raises:
        ValueError: If the index column is missing.

    Example:
        ```python
        rows = _process_param_rows_by_index(process_params)
        ```
    """
    if _PROCESS_PARAM_INDEX_COLUMN not in process_params.columns:
        raise ValueError("process_params must contain process_param_index")

    rows: dict[int, pd.Series] = {}
    for _, row in process_params.iterrows():
        index = _to_int(
            row[_PROCESS_PARAM_INDEX_COLUMN], name=_PROCESS_PARAM_INDEX_COLUMN
        )
        rows[index] = row
    return rows


def _build_process_param_slots(
    names: tuple[str, ...],
    values: tuple[float, ...],
) -> ProcessParamTuple:
    """Build exactly ten process parameter slots.

    ABB Route:
        N/A — local resolution only.

    ABB Constraints:
        RAPID ``processParams`` second dimension contains exactly 10 slots.
        Unused slots are represented by ``name=""`` and ``value=0.0``.

    Args:
        names: Ordered process parameter names.
        values: Ordered process parameter values.

    Returns:
        Tuple of exactly ten process parameter slots.

    Raises:
        ValueError: If names and values lengths mismatch or exceed 10.

    Example:
        ```python
        slots = _build_process_param_slots(("force",), (120.0,))
        ```
    """
    if len(names) != len(values):
        raise ValueError(
            f"Process parameter names/value length mismatch: {len(names)} vs "
            f"{len(values)}"
        )

    if len(names) > MAX_PROCESS_PARAM_PER_SET:
        raise ValueError(f"Process parameter count exceeds {MAX_PROCESS_PARAM_PER_SET}")

    slots = [
        ResolvedProcessParam(name=name, value=value)
        for name, value in zip(names, values, strict=True)
    ]
    slots.extend(
        ResolvedProcessParam(name="", value=0.0)
        for _ in range(MAX_PROCESS_PARAM_PER_SET - len(slots))
    )

    return (
        slots[0],
        slots[1],
        slots[2],
        slots[3],
        slots[4],
        slots[5],
        slots[6],
        slots[7],
        slots[8],
        slots[9],
    )


def _to_float(value: object, *, name: str) -> float:
    """Convert a non-missing value to float.

    ABB Route:
        N/A — local conversion helper.

    ABB Constraints:
        Missing values must be rejected before RAPID serialization.

    Args:
        value: Value to convert.
        name: Field name used in error messages.

    Returns:
        Converted float.

    Raises:
        ValueError: If the value is missing or cannot be converted.

    Example:
        ```python
        assert _to_float("12.5", name="tcp_speed") == 12.5
        ```
    """
    if _is_missing(value):
        raise ValueError(f"Missing numeric value for {name}")

    try:
        return float(cast(Any, value))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Cannot convert {name}={value!r} to float") from exc


def _to_int(value: object, *, name: str) -> int:
    """Convert a non-missing value to int.

    ABB Route:
        N/A — local conversion helper.

    ABB Constraints:
        Missing values must be rejected before RAPID serialization.

    Args:
        value: Value to convert.
        name: Field name used in error messages.

    Returns:
        Converted integer.

    Raises:
        ValueError: If the value is missing or cannot be converted.

    Example:
        ```python
        assert _to_int("10", name="zone_type") == 10
        ```
    """
    if _is_missing(value):
        raise ValueError(f"Missing integer value for {name}")

    try:
        return int(cast(Any, value))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Cannot convert {name}={value!r} to int") from exc


def _is_missing(value: object) -> bool:
    """Return whether a cell value should be considered missing.

    ABB Route:
        N/A — local helper.

    ABB Constraints:
        Pandas missing values and blank strings are treated as absent fields.

    Args:
        value: Cell value.

    Returns:
        ``True`` when value is missing.


    Example:
        ```python
        assert _is_missing(None)
        ```
    """
    if value is None:
        return True

    try:
        if bool(pd.isna(cast(Any, value))):
            return True
    except (TypeError, ValueError):
        return False

    return bool(isinstance(value, str) and not value.strip())


def move_type_code_to_name(move_type: int) -> str:
    """Return a human-readable movement type name.

    ABB Route:
        N/A — local helper.

    ABB Constraints:
        Only TrajCenter v2 movement codes are supported.

    Args:
        move_type: Numeric movement type code.

    Returns:
        Canonical movement name.

    Raises:
        ValueError: If movement type is unsupported.

    Example:
        ```python
        assert move_type_code_to_name(0) == "MoveL"
        ```
    """
    if move_type == MOVE_TYPE_L:
        return "MoveL"
    if move_type == MOVE_TYPE_J:
        return "MoveJ"
    if move_type == MOVE_TYPE_C:
        return "MoveC"
    raise ValueError(f"Unsupported move type code {move_type}")
