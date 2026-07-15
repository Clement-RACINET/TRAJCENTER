#!/usr/bin/env python3
# trajcenter/rws/reader.py
"""RWS reader — reads RAPID variables from the ABB controller.

Author: Clement RACINET

This module is the **only** place in TrajCenter that calls
``get_rapidsymbol_data``. It provides typed accessors for the
RAPID persistent variables written by the TRAJCENTER module.

RAPID variable map (read operations):

=====  ========================  ===========  ================================
Ref    RAPID variable            RAPID type   Python return
=====  ========================  ===========  ================================
R1     TrajSelectedIndex         num          ``int`` — 1-based RAPID index
R2     TrajReady                 bool         ``bool``
R3     NbRobtargetsTraj          num          ``int``
R4     NbTrajDispo               num          ``int``
R5     NomsTraj{1..MAX_TRAJ}     string       ``list[str]`` (stripped)
=====  ========================  ===========  ================================

All reads use ``GET /rw/rapid/symbol/data/{symbolurl}`` via
``get_rapidsymbol_data`` from the low-level RWS layer.
Parsing is delegated to ``get_variable`` from ``highlevel.rapid``.

ABB constraints
---------------
- Symbol URL format: ``RAPID/{task}/{module}/{var}``
- RAPID arrays are 1-based on the controller side.
- ``TrajReady`` is a RAPID ``bool`` — controller returns ``"TRUE"``
  or ``"FALSE"`` (case-insensitive).
- ``NomsTraj`` entries may contain trailing spaces — stripped here.
"""

from __future__ import annotations

from abb_rws_client_python_rw6 import RWSClient
from abb_rws_client_python_rw6.highlevel.rapid import get_variable

from trajcenter.core.logger import get_logger
from trajcenter.rws._utils import symbol
from trajcenter.rws.writer import MAX_TRAJ


logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def read_selected_traj_index(
    client: RWSClient,
    *,
    task: str = "T_ROB1",
    module: str = "TRAJCENTER",
) -> int:
    """Read the trajectory index currently selected by RAPID.

    Reads ``TrajSelectedIndex`` — a RAPID ``num`` variable set by the
    robot program to indicate which trajectory it wants TrajCenter to
    transfer next. The value is **1-based** (RAPID convention).

    Route (delegated):
        ``GET /rw/rapid/symbol/data/{symbolurl}``

    ABB constraints:
        ``TrajSelectedIndex`` must be declared as ``PERS num`` in the
        TRAJCENTER module. Returns ``0`` if RAPID has not yet written
        a selection.

    Args:
        client: Open :class:`~abb_rws_client_python_rw6.RWSClient`
            instance.
        task: RAPID task name. Defaults to ``"T_ROB1"``.
        module: RAPID module name. Defaults to ``"TRAJCENTER"``.

    Returns:
        The selected trajectory index as a Python ``int`` (1-based).
        Returns ``0`` if the variable holds ``0`` (no selection).

    Raises:
        RWSHTTPError: On any unexpected HTTP error from the controller.
        ValueError: If the raw value cannot be converted to ``int``.

    Example:
        ::

            idx = await read_selected_traj_index(client)
            print(idx)  # e.g. 3  → RAPID wants trajectory #3
    """
    symbolurl = symbol(task, module, "TrajSelectedIndex")
    raw = await get_variable(client, symbolurl=symbolurl)
    logger.debug("TrajSelectedIndex = %r", raw)
    try:
        return int(float(raw))
    except ValueError as exc:
        raise ValueError(
            f"Cannot parse TrajSelectedIndex value {raw!r} as int"
        ) from exc


async def read_traj_ready(
    client: RWSClient,
    *,
    task: str = "T_ROB1",
    module: str = "TRAJCENTER",
) -> bool:
    """Read the ``TrajReady`` flag from the controller.

    ``TrajReady`` is set to ``TRUE`` by
    :func:`~trajcenter.rws.writer.write_trajectory` as the final
    atomic signal after a full transfer. RAPID resets it to ``FALSE``
    once it has consumed the trajectory.

    Route (delegated):
        ``GET /rw/rapid/symbol/data/{symbolurl}``

    ABB constraints:
        ``TrajReady`` must be declared as ``PERS bool`` in the
        TRAJCENTER module. The controller returns ``"TRUE"`` or
        ``"FALSE"`` (case-insensitive).

    Args:
        client: Open :class:`~abb_rws_client_python_rw6.RWSClient`
            instance.
        task: RAPID task name. Defaults to ``"T_ROB1"``.
        module: RAPID module name. Defaults to ``"TRAJCENTER"``.

    Returns:
        ``True`` if ``TrajReady == TRUE`` on the controller,
        ``False`` otherwise.

    Raises:
        RWSHTTPError: On any unexpected HTTP error from the controller.
        ValueError: If the raw value is neither ``"TRUE"`` nor
            ``"FALSE"``.

    Example:
        ::

            ready = await read_traj_ready(client)
            if ready:
                print("Controller has consumed the trajectory.")
    """
    symbolurl = symbol(task, module, "TrajReady")
    raw = await get_variable(client, symbolurl=symbolurl)
    logger.debug("TrajReady = %r", raw)
    normalized = raw.strip().upper()
    if normalized == "TRUE":
        return True
    if normalized == "FALSE":
        return False
    raise ValueError(f"Unexpected TrajReady value {raw!r}: expected 'TRUE' or 'FALSE'")


async def read_nb_robtargets(
    client: RWSClient,
    *,
    task: str = "T_ROB1",
    module: str = "TRAJCENTER",
) -> int:
    """Read the number of robtargets currently loaded on the controller.

    Reads ``NbRobtargetsTraj`` — written by
    :func:`~trajcenter.rws.writer.write_trajectory` as step W4.

    Route (delegated):
        ``GET /rw/rapid/symbol/data/{symbolurl}``

    ABB constraints:
        ``NbRobtargetsTraj`` must be declared as ``PERS num`` in the
        TRAJCENTER module.

    Args:
        client: Open :class:`~abb_rws_client_python_rw6.RWSClient`
            instance.
        task: RAPID task name. Defaults to ``"T_ROB1"``.
        module: RAPID module name. Defaults to ``"TRAJCENTER"``.

    Returns:
        Number of robtargets currently declared on the controller
        (``int``).

    Raises:
        RWSHTTPError: On any unexpected HTTP error from the controller.
        ValueError: If the raw value cannot be converted to ``int``.

    Example:
        ::

            n = await read_nb_robtargets(client)
            print(f"{n} points loaded on controller")
    """
    symbolurl = symbol(task, module, "NbRobtargetsTraj")
    raw = await get_variable(client, symbolurl=symbolurl)
    logger.debug("NbRobtargetsTraj = %r", raw)
    try:
        return int(float(raw))
    except ValueError as exc:
        raise ValueError(f"Cannot parse NbRobtargetsTraj value {raw!r} as int") from exc


async def read_nb_traj_dispo(
    client: RWSClient,
    *,
    task: str = "T_ROB1",
    module: str = "TRAJCENTER",
) -> int:
    """Read the number of trajectories declared in the store metadata.

    Reads ``NbTrajDispo`` — written by
    :func:`~trajcenter.rws.writer.write_store_metadata` as step W1.

    Route (delegated):
        ``GET /rw/rapid/symbol/data/{symbolurl}``

    ABB constraints:
        ``NbTrajDispo`` must be declared as ``PERS num`` in the
        TRAJCENTER module.

    Args:
        client: Open :class:`~abb_rws_client_python_rw6.RWSClient`
            instance.
        task: RAPID task name. Defaults to ``"T_ROB1"``.
        module: RAPID module name. Defaults to ``"TRAJCENTER"``.

    Returns:
        Number of trajectories available in the store (``int``).

    Raises:
        RWSHTTPError: On any unexpected HTTP error from the controller.
        ValueError: If the raw value cannot be converted to ``int``.

    Example:
        ::

            n = await read_nb_traj_dispo(client)
            print(f"{n} trajectories available")
    """
    symbolurl = symbol(task, module, "NbTrajDispo")
    raw = await get_variable(client, symbolurl=symbolurl)
    logger.debug("NbTrajDispo = %r", raw)
    try:
        return int(float(raw))
    except ValueError as exc:
        raise ValueError(f"Cannot parse NbTrajDispo value {raw!r} as int") from exc


async def read_traj_names(
    client: RWSClient,
    *,
    task: str = "T_ROB1",
    module: str = "TRAJCENTER",
    count: int | None = None,
) -> list[str]:
    """Read trajectory names from the controller store metadata.

    Reads ``NomsTraj[1]`` … ``NomsTraj[count]`` (1-based RAPID array).
    If *count* is ``None``, first reads ``NbTrajDispo`` to determine
    how many names to fetch.

    Route (delegated):
        ``GET /rw/rapid/symbol/data/{symbolurl}``

    ABB constraints:
        - ``NomsTraj`` must be declared as ``PERS string{MAX_TRAJ}``
          in the TRAJCENTER module.
        - Only the first *count* entries are read — padded empty
          strings beyond *count* are never fetched.
        - Trailing spaces and RAPID double-quotes are stripped.

    Args:
        client: Open :class:`~abb_rws_client_python_rw6.RWSClient`
            instance.
        task: RAPID task name. Defaults to ``"T_ROB1"``.
        module: RAPID module name. Defaults to ``"TRAJCENTER"``.
        count: Number of names to read. If ``None``, reads
            ``NbTrajDispo`` first. Must be ``<= MAX_TRAJ``.

    Returns:
        Ordered list of trajectory name strings (stripped, unquoted).
        Empty list if *count* is ``0``.

    Raises:
        ValueError: If *count* >
            :data:`~trajcenter.rws.writer.MAX_TRAJ` or if a raw
            value cannot be parsed.
        RWSHTTPError: On any unexpected HTTP error from the controller.

    Example:
        ::

            names = await read_traj_names(client, count=3)
            print(names)  # ['Traj1', 'Traj2', 'Traj3']
    """
    if count is None:
        count = await read_nb_traj_dispo(client, task=task, module=module)

    if count > MAX_TRAJ:
        raise ValueError(f"Requested {count} names but MAX_TRAJ={MAX_TRAJ}")

    if count == 0:
        return []

    names: list[str] = []
    for i in range(1, count + 1):
        symbolurl = symbol(task, module, f"NomsTraj/[{i}]")
        raw = await get_variable(client, symbolurl=symbolurl)
        # Strip RAPID double-quotes and whitespace: '"Traj1"' → 'Traj1'
        names.append(raw.strip().strip('"'))

    logger.debug("Read %d trajectory names from controller", len(names))
    return names
