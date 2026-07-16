#!/usr/bin/env python3
# trajcenter/rws/writer.py
"""RWS writer — transfers a :class:`~trajcenter.core.trajectory.Trajectory`
to the ABB controller via RWS RAPID symbol writes.

Author: Clement RACINET

This module is the **only** place in TrajCenter that calls
``set_variable_with_mastership``. It owns the full Mastership lifecycle:
acquire → write all variables → release (always, even on error).

RAPID variable map (module ``TRAJCENTER``, task ``T_ROB1`` by default)
----------------------------------------------------------------------

Metadata block (written once per store refresh):

=====  ========================  ===========  ================================
Ref    RAPID variable            RAPID type   Python source
=====  ========================  ===========  ================================
W1     NbTrajDispo               num          ``len(store.names)``
W2     NomsTraj{1..MAX_TRAJ}     string       ``store.names`` (padded)
W3     NbPointsTraj{1..MAX_TRAJ} num          ``store.point_counts`` (padded)
=====  ========================  ===========  ================================

Trajectory block (written on each transfer):

=====  ========================  ===========  ================================
Ref    RAPID variable            RAPID type   Python source
=====  ========================  ===========  ================================
W4     NbRobtargetsTraj          num          ``len(traj.points)``
W5     RobtTRAJCENTER{1..N}      robtarget    rows of ``traj.points``
W6     NbTool                    num          ``len(traj.tools)``
W7     ToolNames{1..MAX_TOOLS}    string       ``traj.tools`` (padded)
W8     NbWobj                    num          ``len(traj.wobjs)``
W9     WobjNames{1..MAX_WOBJS}    string       ``traj.wobjs`` (padded)
W10    TrajReady                 bool         ``TRUE`` (written last)
=====  ========================  ===========  ================================

All writes happen under a **single Mastership acquisition** per call to
:func:`write_trajectory` or :func:`write_store_metadata`. The
``try / finally`` pattern guarantees Mastership release even on error.

ABB constraints
---------------
- ``POST /rw/rapid/symbol/data/{symbolurl}?action=set`` with form body
  ``value=<rapid_string>`` — handled by ``set_variable_with_mastership``.
- RAPID arrays are 1-based on the controller side.
- ``9E+9`` sentinel for inactive external axes is injected here via
  :func:`~abb_rws_client_python_rw6.robtarget_to_rws`; it is **never**
  stored in the Parquet file.
- ``MAX_TRAJ``, ``MAX_TOOLS``, ``MAX_WOBJS`` must match the RAPID array
  declarations in ``TRAJCENTER.sys``.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Final

import pandas as pd

from abb_rws_client_python_rw6 import (
    MastershipDenied,
    RWSClient,
    RobTarget,
    robtarget_to_rws,
)
from abb_rws_client_python_rw6.highlevel.rapid import set_variable_with_mastership

from trajcenter.core.logger import get_logger
from trajcenter.core.trajectory import Trajectory
from trajcenter.rws._utils import symbol


logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Constants — must match TRAJCENTER.sys RAPID declarations
# ---------------------------------------------------------------------------

#: Maximum number of trajectories in the store (RAPID array size).
MAX_TRAJ: Final[int] = 50

#: Maximum number of tools per trajectory (RAPID array size).
MAX_TOOLS: Final[int] = 10

#: Maximum number of wobjs per trajectory (RAPID array size).
MAX_WOBJS: Final[int] = 10

#: External axis column names in the Parquet schema (ordered).
_EAX_COLUMNS: Final[tuple[str, ...]] = (
    "eax_a",
    "eax_b",
    "eax_c",
    "eax_d",
    "eax_e",
    "eax_f",
)

# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _fmt_num(value: int | float) -> str:
    """Format a number for a RAPID ``num`` variable.

    Args:
        value: Numeric value to format.

    Returns:
        String representation with no trailing ``.0`` for integers.

    Example:
        ::

            >>> _fmt_num(42)
            '42'
            >>> _fmt_num(3.14)
            '3.14'
    """
    if isinstance(value, float) and value == int(value):
        return str(int(value))
    return str(value)


def _fmt_bool(value: bool) -> str:  # noqa: FBT001
    """Format a Python bool as a RAPID boolean literal.

    Args:
        value: Boolean value.

    Returns:
        ``"TRUE"`` or ``"FALSE"``.

    Example:
        ::

            >>> _fmt_bool(True)
            'TRUE'
    """
    return "TRUE" if value else "FALSE"


def _fmt_string(value: str) -> str:
    """Wrap a string in RAPID double-quotes.

    Args:
        value: Raw string value (must not contain embedded
            double-quotes).

    Returns:
        RAPID string literal, e.g. ``'"Tool_formage"'``.

    Example:
        ::

            >>> _fmt_string("Tool_formage")
            '"Tool_formage"'
    """
    return f'"{value}"'


def _row_to_robtarget(
    row: pd.Series,  # type: ignore[type-arg]
    eax_present: tuple[bool, ...],
) -> RobTarget:
    """Convert a single Parquet row to a :class:`~abb_rws_client_python_rw6.RobTarget`.

    Column mapping (Parquet → RobTarget):

    - ``x, y, z``            → ``x, y, z``
    - ``q1, q2, q3, q4``     → ``qw, qx, qy, qz`` (ABB: scalar first)
    - ``cf1, cf4, cf6, cfx`` → ``cf1, cf4, cf6, cfx``
    - ``eax_a…eax_f``        → ``eax[0]…eax[5]`` (``9e9`` if column absent)

    ABB constraints:
        Quaternion convention ``[q1, q2, q3, q4] = [w, x, y, z]`` is
        identical in both the Parquet schema and ``RobTarget`` — no
        reordering needed.

    Args:
        row: A single row from ``Trajectory.points`` (via ``iterrows``).
        eax_present: Tuple of 6 booleans indicating which
            ``eax_a…eax_f`` columns exist in the ``DataFrame``.

    Returns:
        A fully populated
        :class:`~abb_rws_client_python_rw6.RobTarget` instance.
        Inactive external axes carry the sentinel value ``9e9``.

    Raises:
        KeyError: If a mandatory column (``x``, ``y``, ``z``,
            ``q1``…``q4``, ``cf1``, ``cf4``, ``cf6``, ``cfx``) is
            missing from *row*.

    Example:
        ::

            import pandas as pd
            row = pd.Series({
                "x": 100.0, "y": 200.0, "z": 300.0,
                "q1": 1.0, "q2": 0.0, "q3": 0.0, "q4": 0.0,
                "cf1": 0, "cf4": 0, "cf6": 0, "cfx": 0,
            })
            rt = _row_to_robtarget(row, (False,) * 6)
            assert rt.x == 100.0
    """
    _INACTIVE: Final[float] = 9e9

    eax: list[float] = [
        float(row[col]) if present else _INACTIVE
        for col, present in zip(_EAX_COLUMNS, eax_present)
    ]

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
    """Detect which external axis columns are present in *df*.

    Args:
        df: The ``Trajectory.points`` ``DataFrame``.

    Returns:
        Tuple of 6 booleans, one per axis ``eax_a``…``eax_f``.

    Example:
        ::

            import pandas as pd
            df = pd.DataFrame({"eax_a": [100.0]})
            assert _eax_presence(df) == (True, False, False, False, False, False)
    """
    return tuple(col in df.columns for col in _EAX_COLUMNS)  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def write_store_metadata(
    client: RWSClient,
    names: list[str],
    point_counts: list[int],
    *,
    task: str = "T_ROB1",
    module: str = "TRAJCENTER",
    mastership_retries: int = 3,
) -> None:
    """Write store metadata (W1, W2, W3) to the controller under Mastership.

    Writes the number of available trajectories, their names, and their
    point counts into the RAPID persistent variables. This must be called
    once at startup and whenever the trajectory store changes.

    Route (delegated):
        ``POST /rw/rapid/symbol/data/{symbolurl}?action=set``

    ABB constraints:
        Mastership is acquired once for all writes and released in a
        ``finally`` block. Retries up to *mastership_retries* times on
        :exc:`~abb_rws_client_python_rw6.MastershipDenied`.

    Args:
        client: Open :class:`~abb_rws_client_python_rw6.RWSClient`
            instance.
        names: Ordered list of trajectory names
            (max :data:`MAX_TRAJ`).
        point_counts: Ordered list of point counts matching *names*.
        task: RAPID task name. Defaults to ``"T_ROB1"``.
        module: RAPID module name. Defaults to ``"TRAJCENTER"``.
        mastership_retries: Number of Mastership acquisition retries
            before raising. Defaults to ``3``.

    Raises:
        ValueError: If ``len(names) != len(point_counts)`` or if
            ``len(names) > MAX_TRAJ``.
        MastershipDenied: If Mastership cannot be acquired after all
            retries.
        RWSHTTPError: On any unexpected HTTP error from the controller.

    Example:
        ::

            await write_store_metadata(
                client,
                names=["Traj1", "Traj2"],
                point_counts=[320, 150],
            )
    """
    if len(names) != len(point_counts):
        raise ValueError(
            f"names and point_counts must have the same length, "
            f"got {len(names)} vs {len(point_counts)}"
        )
    if len(names) > MAX_TRAJ:
        raise ValueError(f"Store has {len(names)} trajectories but MAX_TRAJ={MAX_TRAJ}")

    nb = len(names)
    logger.info(
        "Writing store metadata: %d trajectories → controller [%s/%s]",
        nb,
        task,
        module,
    )

    padded_names = names + [""] * (MAX_TRAJ - nb)
    padded_counts = point_counts + [0] * (MAX_TRAJ - nb)

    async def _do_write() -> None:
        sym = lambda var: symbol(task, module, var)  # noqa: E731

        # W1 — NbTrajDispo
        await set_variable_with_mastership(
            client,
            symbolurl=sym("NbTrajDispo"),
            value=_fmt_num(nb),
        )

        # W2 — NomsTraj{i} (1-based RAPID array)
        for i, name in enumerate(padded_names, start=1):
            await set_variable_with_mastership(
                client,
                symbolurl=sym(f"NomsTraj/[{i}]"),
                value=_fmt_string(name),
            )

        # W3 — NbPointsTraj{i} (1-based RAPID array)
        for i, count in enumerate(padded_counts, start=1):
            await set_variable_with_mastership(
                client,
                symbolurl=sym(f"NbPointsTraj/[{i}]"),
                value=_fmt_num(count),
            )

    await _retry_mastership(_do_write, mastership_retries)
    logger.info("Store metadata written successfully.")


async def write_trajectory(
    client: RWSClient,
    traj: Trajectory,
    *,
    task: str = "T_ROB1",
    module: str = "TRAJCENTER",
    on_progress: Callable[[int, int], None] | None = None,
    mastership_retries: int = 3,
) -> None:
    """Transfer a full trajectory to the controller (W4 → W10).

    Writes all robtargets and associated metadata (tool names, wobj
    names, counts) then sets ``TrajReady = TRUE`` as the final atomic
    signal to RAPID.

    Route (delegated):
        ``POST /rw/rapid/symbol/data/{symbolurl}?action=set``

    ABB constraints:
        - A **single** Mastership is held for the entire write sequence.
        - ``TrajReady`` is written **last** so RAPID never sees a
          partially transferred trajectory.
        - Mastership is **always** released in a ``finally`` block.
        - ``9E+9`` sentinel for inactive external axes is injected here
          via :func:`~abb_rws_client_python_rw6.robtarget_to_rws`; it
          is never stored in the Parquet file.

    Args:
        client: Open :class:`~abb_rws_client_python_rw6.RWSClient`
            instance.
        traj: :class:`~trajcenter.core.trajectory.Trajectory` to
            transfer.
        task: RAPID task name. Defaults to ``"T_ROB1"``.
        module: RAPID module name. Defaults to ``"TRAJCENTER"``.
        on_progress: Optional callback ``(current_index, total)``
            called after each robtarget write. Useful for progress
            bars.
        mastership_retries: Number of Mastership acquisition retries
            before raising. Defaults to ``3``.

    Raises:
        MastershipDenied: If Mastership cannot be acquired after all
            retries.
        RWSHTTPError: On any unexpected HTTP error from the controller.
        ValueError: If the trajectory has no points, or if the number
            of tools or wobjs exceeds the declared RAPID array sizes.

    Example:
        ::

            await write_trajectory(
                client,
                traj,
                on_progress=lambda i, n: print(f"{i}/{n}"),
            )
    """
    n_points = len(traj.points)
    if n_points == 0:
        raise ValueError(f"Trajectory '{traj.meta.name}' has no points.")

    n_tools = len(traj.tools)
    n_wobjs = len(traj.wobjs)

    if n_tools > MAX_TOOLS:
        raise ValueError(f"Trajectory has {n_tools} tools but MAX_TOOLS={MAX_TOOLS}")
    if n_wobjs > MAX_WOBJS:
        raise ValueError(f"Trajectory has {n_wobjs} wobjs but MAX_WOBJS={MAX_WOBJS}")

    logger.info(
        "Transferring trajectory '%s': %d points, %d tools, %d wobjs → [%s/%s]",
        traj.meta.name,
        n_points,
        n_tools,
        n_wobjs,
        task,
        module,
    )

    eax_present = _eax_presence(traj.points)
    sym = lambda var: symbol(task, module, var)  # noqa: E731

    padded_tools = traj.tools + [""] * (MAX_TOOLS - n_tools)
    padded_wobjs = traj.wobjs + [""] * (MAX_WOBJS - n_wobjs)

    async def _do_write() -> None:
        # W4 — NbRobtargetsTraj
        await set_variable_with_mastership(
            client,
            symbolurl=sym("NbRobtargetsTraj"),
            value=_fmt_num(n_points),
        )

        # W6 — NbTool
        await set_variable_with_mastership(
            client,
            symbolurl=sym("NbTool"),
            value=_fmt_num(n_tools),
        )

        # W7 — ToolNames{i}
        for i, name in enumerate(padded_tools, start=1):
            await set_variable_with_mastership(
                client,
                symbolurl=sym(f"ToolNames/[{i}]"),
                value=_fmt_string(name),
            )

        # W8 — NbWobj
        await set_variable_with_mastership(
            client,
            symbolurl=sym("NbWobj"),
            value=_fmt_num(n_wobjs),
        )

        # W9 — WobjNames{i}
        for i, name in enumerate(padded_wobjs, start=1):
            await set_variable_with_mastership(
                client,
                symbolurl=sym(f"WobjNames/[{i}]"),
                value=_fmt_string(name),
            )

        # W5 — RobtTRAJCENTER{i} (written after counts, before TrajReady)
        for i, (_, row) in enumerate(traj.points.iterrows(), start=1):
            rt = _row_to_robtarget(row, eax_present)
            rws_value = robtarget_to_rws(rt)
            await set_variable_with_mastership(
                client,
                symbolurl=sym(f"RobtTRAJCENTER/[{i}]"),
                value=rws_value,
            )
            logger.debug("W5 [%d/%d] %s", i, n_points, rws_value)
            if on_progress is not None:
                on_progress(i, n_points)

        # W10 — TrajReady = TRUE  (atomic signal — written LAST)
        await set_variable_with_mastership(
            client,
            symbolurl=sym("TrajReady"),
            value=_fmt_bool(True),
        )
        logger.info("TrajReady = TRUE — transfer complete.")

    await _retry_mastership(_do_write, mastership_retries)
    logger.info(
        "Trajectory '%s' transferred successfully (%d points).",
        traj.meta.name,
        n_points,
    )


# ---------------------------------------------------------------------------
# Internal — Mastership retry wrapper
# ---------------------------------------------------------------------------


async def _retry_mastership(
    coro_fn: Callable[[], object],
    retries: int,
    *,
    retry_delay_s: float = 1.0,
) -> None:
    """Execute *coro_fn* retrying on :exc:`~abb_rws_client_python_rw6.MastershipDenied`.

    ``set_variable_with_mastership`` internally acquires and releases
    Mastership for each call. If the controller refuses Mastership
    (another client holds it), we wait *retry_delay_s* seconds and
    retry.

    ABB constraints:
        Mastership is managed by ``set_variable_with_mastership`` from
        the ``highlevel`` layer — this wrapper only handles the retry
        loop.

    Args:
        coro_fn: Zero-argument async callable to execute.
        retries: Maximum number of attempts (must be >= 1).
        retry_delay_s: Delay in seconds between attempts. Defaults to
            ``1.0``.

    Raises:
        MastershipDenied: If all *retries* attempts fail.
        RWSHTTPError: On any non-Mastership HTTP error (not retried).

    Example:
        ::

            await _retry_mastership(my_write_fn, retries=3)
    """
    last_exc: MastershipDenied | None = None
    for attempt in range(1, retries + 1):
        try:
            await coro_fn()  # type: ignore[misc]
            return
        except MastershipDenied as exc:
            last_exc = exc
            logger.warning(
                "Mastership denied (attempt %d/%d) — retrying in %.1fs …",
                attempt,
                retries,
                retry_delay_s,
            )
            if attempt < retries:
                await asyncio.sleep(retry_delay_s)

    raise last_exc  # type: ignore[misc]
