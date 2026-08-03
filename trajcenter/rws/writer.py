#!/usr/bin/env python3
# trajcenter/rws/writer.py
"""RWS writer — writes TrajCenter v2 data to ABB RAPID variables.

Author: Clement RACINET

This module writes variables declared in ``TRAJCENTER_WebServices``.

The writer uses ``set_variables_with_mastership`` from
``abb_rws_client_python_rw6.highlevel.variables`` so each public write operation
holds RAPID Mastership once for the whole batch.

ABB Route:
    ``POST /rw/mastership/rapid`` with ``action=request``.
    ``POST /rw/rapid/symbol/data/{symbolurl}`` with ``action=set``.
    ``POST /rw/mastership/rapid`` with ``action=release``.

ABB Constraints:
    - All PC writes must be performed under Mastership.
    - RAPID arrays are one-based and use braces in RAPID syntax.
    - RWS symbol URLs must percent-encode RAPID array braces.
    - ``trajData`` entries are ``trajCenterPointData`` records.
    - ``processParams`` entries are ``trajCenterProcessParameter`` records.
    - ``9E+9`` is injected only during RWS serialization for inactive external
      axes. It must never be stored in ``.trajcenter`` files.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Final
from urllib.parse import quote

import pandas as pd
from abb_rws_client_python_rw6 import (
    MastershipDenied,
    RobTarget,
    RWSClient,
)
from abb_rws_client_python_rw6.highlevel.variables import set_variables_with_mastership

from trajcenter.core.logger import get_logger
from trajcenter.core.trajectory import Trajectory
from trajcenter.rws._utils import symbol, symbol_array_element
from trajcenter.rws.models import (
    ResolvedPoint,
    ResolvedProcessParam,
    ResolvedRobTarget,
    ResolvedTrajectory,
)

logger = get_logger(__name__)

DEFAULT_TASK: Final[str] = "T_ROB1"
WEB_MODULE: Final[str] = "TRAJCENTER_WebServices"

STATUS_OK: Final[int] = 200000
STATUS_METADATA_REFRESHED: Final[int] = 200001
STATUS_TRAJECTORY_TRANSFERRED: Final[int] = 200002

MAX_TRAJ: Final[int] = 256
MAX_TRAJ_POINTS: Final[int] = 100000
MAX_PROCESS_PARAM_SET_COUNT: Final[int] = 256
MAX_PROCESS_PARAM_PER_SET: Final[int] = 10

DEFAULT_MASTERship_RETRY_DELAY_S: Final[float] = 1.0
DEFAULT_PROGRESS_UPDATE_STEP_PERCENT: Final[int] = 5

_EAX_COLUMNS: Final[tuple[str, ...]] = (
    "eax_a",
    "eax_b",
    "eax_c",
    "eax_d",
    "eax_e",
    "eax_f",
)

_INACTIVE_EAX: Final[float] = 9e9


def _fmt_num(value: float) -> str:
    """Format a number for a RAPID ``num`` variable.

    ABB Route:
        N/A — local formatting helper.

    ABB Constraints:
        RAPID ``num`` accepts integer-looking values without a decimal suffix.

    Args:
        value: Numeric value to format.

    Returns:
        String representation with no trailing ``.0`` for integral floats.


    Example:
        ::

            assert _fmt_num(42.0) == "42"
    """
    if isinstance(value, float) and value == int(value):
        return str(int(value))
    return str(value)


def _fmt_bool(value: bool) -> str:
    """Format a Python bool as a RAPID boolean literal.

    ABB Route:
        N/A — local formatting helper.

    ABB Constraints:
        RAPID bool literals are uppercase ``TRUE`` and ``FALSE``.

    Args:
        value: Boolean value.

    Returns:
        ``"TRUE"`` or ``"FALSE"``.


    Example:
        ::

            assert _fmt_bool(True) == "TRUE"
    """
    return "TRUE" if value else "FALSE"


def _fmt_string(value: str) -> str:
    """Wrap a string in RAPID double quotes.

    ABB Route:
        N/A — local formatting helper.

    ABB Constraints:
        Embedded double quotes are escaped for RAPID string literals.

    Args:
        value: Raw string value.

    Returns:
        RAPID string literal.


    Example:
        ::

            assert _fmt_string("Tool_A") == '"Tool_A"'
    """
    escaped = value.replace('"', '\\"')
    return f'"{escaped}"'


def _fmt_traj_meta_record(
    name: str,
    point_count: int,
    process_type: int = 0,
) -> str:
    """Format a ``trajCenterTrajMeta`` RAPID record literal.

    ABB Route:
        Used as value for
        ``POST /rw/rapid/symbol/data/.../trajectories%7Bi%7D``.

    ABB Constraints:
        RAPID record layout is ``[string name, num pointCount, num processType]``.

    Args:
        name: Trajectory display name.
        point_count: Number of trajectory points.
        process_type: Process type code. Defaults to ``0`` (NONE).

    Returns:
        RAPID record literal, e.g. ``'["TrajA",100,0]'``.


    Example:
        ::

            assert _fmt_traj_meta_record("A", 10) == '["A",10,0]'
    """
    return f"[{_fmt_string(name)},{_fmt_num(point_count)},{_fmt_num(process_type)}]"


def _fmt_robtarget(robtarget: ResolvedRobTarget) -> str:
    """Format a resolved robtarget as an ABB RAPID ``robtarget`` literal.

    ABB Route:
        Used as nested value inside ``TRAJCENTER_WebServices/trajData{i}``.

    ABB Constraints:
        RAPID ``robtarget`` layout is:
        ``[[x,y,z],[q1,q2,q3,q4],[cf1,cf4,cf6,cfx],[eax1..eax6]]``.
        Inactive external axes are stored as ``None`` in Python and serialized
        as ``9E+9`` only at RWS write time.

    Args:
        robtarget: Resolved robtarget payload.

    Returns:
        RAPID ``robtarget`` literal.


    Example:
        ::

            text = _fmt_robtarget(robtarget)
    """
    eax_values = [
        _fmt_num(_INACTIVE_EAX if value is None else value) for value in robtarget.eax
    ]

    return (
        "["
        f"[{_fmt_num(robtarget.x)},{_fmt_num(robtarget.y)},{_fmt_num(robtarget.z)}],"
        f"[{_fmt_num(robtarget.q1)},{_fmt_num(robtarget.q2)},"
        f"{_fmt_num(robtarget.q3)},{_fmt_num(robtarget.q4)}],"
        f"[{_fmt_num(robtarget.cf1)},{_fmt_num(robtarget.cf4)},"
        f"{_fmt_num(robtarget.cf6)},{_fmt_num(robtarget.cfx)}],"
        f"[{','.join(eax_values)}]"
        "]"
    )


def _fmt_process_param_record(param: ResolvedProcessParam) -> str:
    """Format a ``trajCenterProcessParameter`` RAPID record literal.

    ABB Route:
        Used as value for
        ``POST /rw/rapid/symbol/data/.../processParams%7Bi,j%7D``.

    ABB Constraints:
        RAPID record layout is ``[string name, num value]``.
        Empty name means unused slot.

    Args:
        param: Resolved process parameter slot.

    Returns:
        RAPID record literal.


    Example:
        ::

            assert _fmt_process_param_record(param) == '["force",120]'
    """
    return f"[{_fmt_string(param.name)},{_fmt_num(param.value)}]"


def _fmt_point_record(point: ResolvedPoint) -> str:
    """Format a ``trajCenterPointData`` RAPID record literal.

    ABB Route:
        Used as value for
        ``POST /rw/rapid/symbol/data/.../trajData%7Bi%7D``.

    ABB Constraints:
        RAPID record layout is:
        ``[moveType, point, tcpSpeed, zoneType, readConfs, toolIndex,
        wobjIndex, processParamIndex]``.

    Args:
        point: Resolved trajectory point.

    Returns:
        RAPID ``trajCenterPointData`` record literal.


    Example:
        ::

            text = _fmt_point_record(point)
    """
    return (
        "["
        f"{_fmt_num(point.move_type)},"
        f"{_fmt_robtarget(point.robtarget)},"
        f"{_fmt_num(point.tcp_speed)},"
        f"{_fmt_num(point.zone_type)},"
        f"{_fmt_bool(point.read_confs)},"
        f"{_fmt_num(point.tool_index)},"
        f"{_fmt_num(point.wobj_index)},"
        f"{_fmt_num(point.process_param_index)}"
        "]"
    )


def _symbol_2d_array_element(
    task: str,
    module: str,
    variable: str,
    first_index: int,
    second_index: int,
) -> str:
    """Build a RWS symbol URL for one RAPID two-dimensional array element.

    ABB Route:
        Used with ``POST /rw/rapid/symbol/data/{symbolurl}?action=set``.

    ABB Constraints:
        RAPID arrays are one-based. Braces and comma are percent-encoded in RWS
        symbol URLs. The RAPID source form is ``variable{first,second}``.

    Args:
        task: RAPID task name.
        module: RAPID module name.
        variable: RAPID array variable name.
        first_index: First one-based RAPID index.
        second_index: Second one-based RAPID index.

    Returns:
        URL-safe RWS symbol path.

    Raises:
        ValueError: If one index is lower than ``1``.

    Example:
        ::

            url = _symbol_2d_array_element("T_ROB1", "M", "a", 1, 2)
    """
    if first_index < 1:
        raise ValueError(f"RAPID first array index must be >= 1, got {first_index}")
    if second_index < 1:
        raise ValueError(f"RAPID second array index must be >= 1, got {second_index}")

    raw_symbolurl = f"RAPID/{task}/{module}/{variable}{{{first_index},{second_index}}}"
    return quote(raw_symbolurl, safe="/")


def _row_to_robtarget(
    row: pd.Series,
    eax_present: tuple[bool, ...],
) -> RobTarget:
    """Convert a trajectory point row to a RWS ``RobTarget``.

    ABB Route:
        Used before writing a ``trajCenterPointData.point`` field or record
        value through RWS.

    ABB Constraints:
        ``9E+9`` is injected for inactive or NaN external axes only at RWS
        serialization time.

    Args:
        row: A single row from ``Trajectory.points``.
        eax_present: Tuple of 6 booleans indicating which ``eax_a`` … ``eax_f``
            columns exist in the DataFrame.

    Returns:
        Fully populated ``RobTarget``.

    Raises:
        KeyError: If mandatory point columns are missing.

    Example:
        ::

            rt = _row_to_robtarget(row, (False,) * 6)
    """
    eax: list[float] = []
    for col, present in zip(_EAX_COLUMNS, eax_present, strict=True):
        if not present or pd.isna(row[col]):
            eax.append(_INACTIVE_EAX)
        else:
            eax.append(float(row[col]))

    return RobTarget(
        x=float(row["x"]),
        y=float(row["y"]),
        z=float(row["z"]),
        qw=float(row["q1"]),
        qx=float(row["q2"]),
        qy=float(row["q3"]),
        qz=float(row["q4"]),
        cf1=float(row["cf1"]),
        cf4=float(row["cf4"]),
        cf6=float(row["cf6"]),
        cfx=float(row["cfx"]),
        eax=eax,
    )


def _eax_presence(df: pd.DataFrame) -> tuple[bool, ...]:
    """Detect which external axis columns are present in a DataFrame.

    ABB Route:
        N/A — local schema helper.

    ABB Constraints:
        Missing external axes are serialized as ``9E+9`` at RWS write time.

    Args:
        df: Trajectory points DataFrame.

    Returns:
        Tuple of 6 booleans, one per external axis column.


    Example:
        ::

            assert _eax_presence(pd.DataFrame()) == (
                False, False, False, False, False, False
            )
    """
    return tuple(col in df.columns for col in _EAX_COLUMNS)


def _validate_resolved_trajectory(resolved: ResolvedTrajectory) -> None:
    """Validate a resolved trajectory before building RWS write values.

    ABB Route:
        N/A — local defensive validation before RWS writes.

    ABB Constraints:
        - ``trajData`` supports at most ``100000`` entries.
        - ``processParams`` supports at most ``256`` parameter sets.
        - process parameter set indexes are RAPID base-1 indexes.
        - point process indexes must be ``0`` or reference an existing set.

    Args:
        resolved: Resolved trajectory payload.

    Returns:
        None.

    Raises:
        ValueError: If the resolved payload exceeds RAPID protocol limits.

    Example:
        ::

            _validate_resolved_trajectory(resolved)
    """
    if resolved.point_count > MAX_TRAJ_POINTS:
        raise ValueError(
            "Resolved trajectory has "
            f"{resolved.point_count} points but MAX_TRAJ_POINTS={MAX_TRAJ_POINTS}"
        )

    if len(resolved.process_param_sets) > MAX_PROCESS_PARAM_SET_COUNT:
        raise ValueError(
            "Resolved trajectory has "
            f"{len(resolved.process_param_sets)} process parameter sets but "
            f"MAX_PROCESS_PARAM_SET_COUNT={MAX_PROCESS_PARAM_SET_COUNT}"
        )

    process_set_indexes = {param_set.index for param_set in resolved.process_param_sets}

    if len(process_set_indexes) != len(resolved.process_param_sets):
        raise ValueError("Duplicate process parameter set indexes are not allowed")

    for index in process_set_indexes:
        if index < 1 or index > MAX_PROCESS_PARAM_SET_COUNT:
            raise ValueError(
                "Process parameter set index must be in "
                f"1..{MAX_PROCESS_PARAM_SET_COUNT}, got {index}"
            )

    for point_index, point in enumerate(resolved.points, start=1):
        if point.process_param_index == 0:
            continue
        if point.process_param_index not in process_set_indexes:
            raise ValueError(
                "Point "
                f"{point_index} references unknown process parameter set "
                f"{point.process_param_index}"
            )


async def write_store_metadata(
    client: RWSClient,
    names: list[str],
    point_counts: list[int],
    *,
    task: str = DEFAULT_TASK,
    module: str = WEB_MODULE,
    process_types: list[int] | None = None,
    mastership_retries: int = 3,
) -> None:
    """Write trajectory store metadata to ``TRAJCENTER_WebServices``.

    ABB Route:
        One batched call to ``POST /rw/rapid/symbol/data/{symbolurl}?action=set``
        per symbol, under one RAPID Mastership session delegated to
        ``set_variables_with_mastership``.

    ABB Constraints:
        Writes:
            - ``nbTrajAvailable``
            - ``trajectories{1..256}``
            - ``refreshMetaRequest := FALSE``
            - ``transferError := FALSE``
            - ``lastErrorCode := 200001``
            - ``lastError := ""``
            - ``transferProgress := 100``

        RAPID arrays are one-based and braces are percent-encoded in symbol
        URLs.

    Args:
        client: Open RWS client.
        names: Ordered trajectory display names.
        point_counts: Ordered point counts matching ``names``.
        task: RAPID task name.
        module: RAPID module name. Defaults to ``TRAJCENTER_WebServices``.
        process_types: Optional process type codes matching ``names``.
            If ``None``, all entries use ``0`` (NONE).
        mastership_retries: Number of retries if Mastership is denied.

    Returns:
        None.

    Raises:
        ValueError: If input lengths mismatch or count exceeds ``MAX_TRAJ``.
        MastershipDenied: If Mastership cannot be acquired after all retries.
        RWSHTTPError: On unexpected controller HTTP errors.

    Example:
        ::

            await write_store_metadata(
                client,
                names=["TrajA"],
                point_counts=[100],
            )
    """
    if len(names) != len(point_counts):
        raise ValueError(
            "names and point_counts must have the same length, "
            f"got {len(names)} vs {len(point_counts)}"
        )

    if process_types is None:
        process_types = [0] * len(names)

    if len(process_types) != len(names):
        raise ValueError(
            "process_types and names must have the same length, "
            f"got {len(process_types)} vs {len(names)}"
        )

    if len(names) > MAX_TRAJ:
        raise ValueError(f"Store has {len(names)} trajectories but MAX_TRAJ={MAX_TRAJ}")

    nb = len(names)
    logger.info(
        "Writing store metadata: %d trajectories -> controller [%s/%s]",
        nb,
        task,
        module,
    )

    padded_names = names + [""] * (MAX_TRAJ - nb)
    padded_counts = point_counts + [0] * (MAX_TRAJ - nb)
    padded_process_types = process_types + [0] * (MAX_TRAJ - nb)

    async def _do_write() -> None:
        values: dict[str, str] = {}

        values[symbol(task, module, "nbTrajAvailable")] = _fmt_num(nb)

        for index, (name, count, process_type) in enumerate(
            zip(
                padded_names,
                padded_counts,
                padded_process_types,
                strict=True,
            ),
            start=1,
        ):
            values[
                symbol_array_element(
                    task=task,
                    module=module,
                    variable="trajectories",
                    index=index,
                )
            ] = _fmt_traj_meta_record(name, count, process_type)

        values[symbol(task, module, "refreshMetaRequest")] = _fmt_bool(False)
        values[symbol(task, module, "transferError")] = _fmt_bool(False)
        values[symbol(task, module, "lastErrorCode")] = _fmt_num(
            STATUS_METADATA_REFRESHED
        )
        values[symbol(task, module, "lastError")] = _fmt_string("")
        values[symbol(task, module, "transferProgress")] = _fmt_num(100)

        await set_variables_with_mastership(client, values=values, domain="rapid")

    await _retry_mastership(_do_write, mastership_retries)
    logger.info("Store metadata written successfully.")


async def write_resolved_trajectory(
    client: RWSClient,
    resolved: ResolvedTrajectory,
    *,
    task: str = DEFAULT_TASK,
    module: str = WEB_MODULE,
    on_progress: Callable[[int, int], None] | None = None,
    mastership_retries: int = 3,
    retry_delay_s: float = DEFAULT_MASTERship_RETRY_DELAY_S,
    progress_step_percent: int = DEFAULT_PROGRESS_UPDATE_STEP_PERCENT,
) -> None:
    """Transfer a resolved trajectory to ``TRAJCENTER_WebServices``.

    ABB Route:
        One batched call to ``POST /rw/rapid/symbol/data/{symbolurl}?action=set``
        per symbol, under one RAPID Mastership session delegated to
        ``set_variables_with_mastership``.

    ABB Constraints:
        Writes:
            - ``trajReady := FALSE`` before payload update;
            - ``transferError := FALSE``;
            - ``lastErrorCode := 200000``;
            - ``lastError := ""``;
            - ``transferProgress := 0``;
            - ``nbLoadedTrajPoints``;
            - ``processParams{1..256,1..10}``;
            - ``trajData{1..nbLoadedTrajPoints}``;
            - ``transferProgress := 100``;
            - ``lastErrorCode := 200002``;
            - ``sendTrajRequest := FALSE``;
            - ``trajReady := TRUE``.

        RAPID arrays are one-based. ``9E+9`` is injected only for inactive
        external axes during RWS serialization.

    Args:
        client: Open RWS client.
        resolved: Already validated trajectory payload produced by the resolver.
        task: RAPID task name.
        module: RAPID module name. Defaults to ``TRAJCENTER_WebServices``.
        on_progress: Optional callback receiving ``done`` and ``total`` local
            serialization units while the batch is built.
        mastership_retries: Number of retries if Mastership is denied.
        retry_delay_s: Delay between Mastership retry attempts.
        progress_step_percent: Minimum percentage step used for local progress
            computation.

    Returns:
        None.

    Raises:
        ValueError: If the resolved payload exceeds RAPID protocol limits.
        MastershipDenied: If Mastership cannot be acquired after all retries.
        RWSHTTPError: On unexpected controller HTTP errors.

    Example:
        ::

            await write_resolved_trajectory(client, resolved)
    """
    _validate_resolved_trajectory(resolved)

    logger.info(
        "Writing resolved trajectory '%s': %d points, %d process parameter sets "
        "-> controller [%s/%s]",
        resolved.name,
        resolved.point_count,
        len(resolved.process_param_sets),
        task,
        module,
    )

    async def _do_write() -> None:
        values = _build_resolved_trajectory_values(
            resolved=resolved,
            task=task,
            module=module,
            on_progress=on_progress,
            progress_step_percent=progress_step_percent,
        )
        await set_variables_with_mastership(client, values=values, domain="rapid")

    await _retry_mastership(
        _do_write,
        mastership_retries,
        retry_delay_s=retry_delay_s,
    )
    logger.info("Resolved trajectory '%s' written successfully.", resolved.name)


def _build_resolved_trajectory_values(
    *,
    resolved: ResolvedTrajectory,
    task: str,
    module: str,
    on_progress: Callable[[int, int], None] | None,
    progress_step_percent: int,
) -> dict[str, str]:
    """Build the complete RWS symbol/value batch for a resolved trajectory.

    ABB Route:
        Produces values for ``POST /rw/rapid/symbol/data/{symbolurl}?action=set``.

    ABB Constraints:
        The returned mapping is intended to be written under a single RAPID
        Mastership session. RAPID arrays are one-based.

    Args:
        resolved: Resolved trajectory payload.
        task: RAPID task name.
        module: RAPID module name.
        on_progress: Optional local progress callback.
        progress_step_percent: Minimum percentage step for progress callbacks.

    Returns:
        Ordered symbol/value mapping.


    Example:
        ::

            values = _build_resolved_trajectory_values(
                resolved=resolved,
                task="T_ROB1",
                module="TRAJCENTER_WebServices",
                on_progress=None,
                progress_step_percent=5,
            )
    """
    values: dict[str, str] = {}

    values[symbol(task, module, "trajReady")] = _fmt_bool(False)
    values[symbol(task, module, "transferError")] = _fmt_bool(False)
    values[symbol(task, module, "lastErrorCode")] = _fmt_num(STATUS_OK)
    values[symbol(task, module, "lastError")] = _fmt_string("")
    values[symbol(task, module, "transferProgress")] = _fmt_num(0)
    values[symbol(task, module, "nbLoadedTrajPoints")] = _fmt_num(resolved.point_count)

    total_units = resolved.point_count + (
        MAX_PROCESS_PARAM_SET_COUNT * MAX_PROCESS_PARAM_PER_SET
    )
    done_units = 0
    next_progress = progress_step_percent
    empty_param = ResolvedProcessParam(name="", value=0.0)

    param_sets_by_index = {
        param_set.index: param_set for param_set in resolved.process_param_sets
    }

    for set_index in range(1, MAX_PROCESS_PARAM_SET_COUNT + 1):
        param_set = param_sets_by_index.get(set_index)
        params = param_set.params if param_set is not None else (empty_param,) * 10

        for slot_index, param in enumerate(params, start=1):
            values[
                _symbol_2d_array_element(
                    task=task,
                    module=module,
                    variable="processParams",
                    first_index=set_index,
                    second_index=slot_index,
                )
            ] = _fmt_process_param_record(param)

            done_units += 1
            next_progress = _notify_progress(
                done_units=done_units,
                total_units=total_units,
                next_progress=next_progress,
                progress_step_percent=progress_step_percent,
                on_progress=on_progress,
            )

    for point_index, point in enumerate(resolved.points, start=1):
        values[
            symbol_array_element(
                task=task,
                module=module,
                variable="trajData",
                index=point_index,
            )
        ] = _fmt_point_record(point)

        done_units += 1
        next_progress = _notify_progress(
            done_units=done_units,
            total_units=total_units,
            next_progress=next_progress,
            progress_step_percent=progress_step_percent,
            on_progress=on_progress,
        )

    values[symbol(task, module, "transferProgress")] = _fmt_num(100)
    values[symbol(task, module, "lastErrorCode")] = _fmt_num(
        STATUS_TRAJECTORY_TRANSFERRED
    )
    values[symbol(task, module, "lastError")] = _fmt_string("")
    values[symbol(task, module, "sendTrajRequest")] = _fmt_bool(False)
    values[symbol(task, module, "trajReady")] = _fmt_bool(True)

    return values


def _notify_progress(
    *,
    done_units: int,
    total_units: int,
    next_progress: int,
    progress_step_percent: int,
    on_progress: Callable[[int, int], None] | None,
) -> int:
    """Notify local progress and compute the next progress threshold.

    ABB Route:
        N/A — local batching helper.

    ABB Constraints:
        Progress here is local to Python batch construction. The final robot-side
        ``transferProgress`` value is written in the Mastership-protected batch.

    Args:
        done_units: Completed local serialization units.
        total_units: Total local serialization units.
        next_progress: Next percentage threshold.
        progress_step_percent: Minimum progress step.
        on_progress: Optional local progress callback.

    Returns:
        Updated next progress threshold.


    Example:
        ::

            next_progress = _notify_progress(
                done_units=1,
                total_units=10,
                next_progress=5,
                progress_step_percent=5,
                on_progress=None,
            )
    """
    if on_progress is not None:
        on_progress(done_units, total_units)

    if total_units <= 0 or progress_step_percent <= 0:
        return next_progress

    progress = int((done_units / total_units) * 100)
    if progress >= next_progress and progress < 100:
        return next_progress + progress_step_percent

    return next_progress


async def write_trajectory(
    client: RWSClient,
    traj: Trajectory,
    *,
    task: str = DEFAULT_TASK,
    module: str = WEB_MODULE,
    on_progress: Callable[[int, int], None] | None = None,
    mastership_retries: int = 3,
) -> None:
    """Transfer a full trajectory to ``TRAJCENTER_WebServices``.

    ABB Route:
        Planned v2 route:
        ``POST /rw/rapid/symbol/data/RAPID/{task}/{module}/trajData%7Bi%7D``.

    ABB Constraints:
        The full v2 orchestration writer is migrated in the next integration
        step. This placeholder intentionally raises to avoid silently using the
        obsolete v1 protocol.

    Args:
        client: Open RWS client.
        traj: Trajectory to transfer.
        task: RAPID task name.
        module: RAPID module name.
        on_progress: Optional progress callback.
        mastership_retries: Number of Mastership retries.

    Returns:
        None.

    Raises:
        NotImplementedError: Always, until orchestration is connected to the
            resolver and ``write_resolved_trajectory``.

    Example:
        ::

            await write_trajectory(client, traj)
    """
    _ = (client, traj, task, module, on_progress, mastership_retries)
    raise NotImplementedError(
        "RWS v2 trajectory transfer requires resolver orchestration. "
        "Use write_resolved_trajectory with a ResolvedTrajectory payload."
    )


async def _retry_mastership(
    coro_fn: Callable[[], Awaitable[None]],
    retries: int,
    *,
    retry_delay_s: float = DEFAULT_MASTERship_RETRY_DELAY_S,
) -> None:
    """Execute an async write callable retrying on ``MastershipDenied``.

    ABB Route:
        N/A — retry wrapper around high-level RWS write calls.

    ABB Constraints:
        Only ``MastershipDenied`` is retried. Other RWS errors propagate
        immediately.

    Args:
        coro_fn: Zero-argument async callable to execute.
        retries: Maximum number of attempts. Must be at least ``1``.
        retry_delay_s: Delay between attempts in seconds.

    Returns:
        None.

    Raises:
        ValueError: If ``retries < 1``.
        MastershipDenied: If all attempts fail.

    Example:
        ::

            await _retry_mastership(my_write, retries=3)
    """
    if retries < 1:
        raise ValueError(f"retries must be >= 1, got {retries}")

    last_exc: MastershipDenied | None = None
    for attempt in range(1, retries + 1):
        try:
            await coro_fn()
            return
        except MastershipDenied as exc:
            last_exc = exc
            logger.warning(
                "Mastership denied (attempt %d/%d) — retrying in %.1fs ...",
                attempt,
                retries,
                retry_delay_s,
            )
            if attempt < retries:
                await asyncio.sleep(retry_delay_s)

    if last_exc is not None:
        raise last_exc

    raise RuntimeError("Mastership retry loop ended without result")
