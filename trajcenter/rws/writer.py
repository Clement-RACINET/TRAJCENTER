#!/usr/bin/env python3
# trajcenter/rws/writer.py
"""RWS writer — writes TrajCenter v2 data to ABB RAPID variables.

> **Author**: Clément RACINET

This module writes variables declared in ``TRAJCENTER_WebServices``.

The writer uses ``set_variables_with_mastership`` from
``abb_rws_client_python_rw6.highlevel.rapid`` so each public write
operation holds RAPID Mastership once for the whole batch.

ABB Route:
    ``POST /rw/mastership/rapid`` with ``action=request``.
    ``POST /rw/rapid/symbol/data/{symbolurl}`` with ``action=set``.
    ``POST /rw/mastership/rapid`` with ``action=release``.

ABB Constraints:
    - All PC writes must be performed under Mastership.
    - RAPID arrays are one-based and use braces in RAPID syntax.
    - RWS symbol URLs must percent-encode RAPID array braces.
    - ``trajData`` entries are ``trajCenterPointData`` records.
    - ``9E+9`` is injected only during RWS serialization for inactive
      external axes. It must never be stored in ``.trajcenter`` files.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Final

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
        RAPID ``num`` accepts integer-looking values without a decimal
        suffix.

    Args:
        value: Numeric value to format.

    Returns:
        String representation with no trailing ``.0`` for integral
        floats.

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
        RAPID record layout is ``[string name, num pointCount,
        num processType]``.

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


def _row_to_robtarget(
    row: pd.Series,
    eax_present: tuple[bool, ...],
) -> RobTarget:
    """Convert a trajectory point row to a RWS ``RobTarget``.

    ABB Route:
        Used before writing a ``trajCenterPointData.point`` field or
        record value through RWS.

    ABB Constraints:
        ``9E+9`` is injected for inactive or NaN external axes only at
        RWS serialization time.

    Args:
        row: A single row from ``Trajectory.points``.
        eax_present: Tuple of 6 booleans indicating which
            ``eax_a`` … ``eax_f`` columns exist in the DataFrame.

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
        Missing external axes are serialized as ``9E+9`` at RWS write
        time.

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
        One batched call to
        ``POST /rw/rapid/symbol/data/{symbolurl}?action=set`` per
        symbol, under one RAPID Mastership session delegated to
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

        RAPID arrays are one-based and braces are percent-encoded in
        symbol URLs.

    Args:
        client: Open RWS client.
        names: Ordered trajectory display names.
        point_counts: Ordered point counts matching ``names``.
        task: RAPID task name.
        module: RAPID module name. Defaults to
            ``TRAJCENTER_WebServices``.
        process_types: Optional process type codes matching ``names``.
            If ``None``, all entries use ``0`` (NONE).
        mastership_retries: Number of retries if Mastership is denied.

    Returns:
        None.

    Raises:
        ValueError: If input lengths mismatch or count exceeds
            ``MAX_TRAJ``.
        MastershipDenied: If Mastership cannot be acquired after all
            retries.
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
        The full v2 trajectory writer is migrated in RWS-4. This
        placeholder intentionally raises to avoid silently using the
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
        NotImplementedError: Always, until RWS-4 is implemented.

    Example:
        ::

            await write_trajectory(client, traj)
    """
    _ = (client, traj, task, module, on_progress, mastership_retries)
    raise NotImplementedError("RWS v2 trajectory transfer is implemented in RWS-4.")


async def _retry_mastership(
    coro_fn: Callable[[], object],
    retries: int,
    *,
    retry_delay_s: float = 1.0,
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
            await coro_fn()  # type: ignore[misc]
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

    raise last_exc  # type: ignore[misc]
