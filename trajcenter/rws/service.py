#!/usr/bin/env python3
# trajcenter/rws/service.py
"""RWS service orchestration for TrajCenter v2 trajectory transfers.

Author: Clement RACINET

This module coordinates the full PC-side RWS transfer workflow:

1. read the selected trajectory index from ``TRAJCENTER_WebServices``;
2. map this RAPID base-1 index to a local ``TrajectoryStoreEntry``;
3. load the selected ``.trajcenter`` archive;
4. read the robot-side context;
5. resolve the local trajectory against the robot context;
6. write the resolved trajectory to RAPID variables.

ABB Route:
    Reads:
        ``GET /rw/rapid/symbol/data/RAPID/{task}/TRAJCENTER_WebServices/selectedTrajIndex``

    Context reads:
        Multiple ``GET /rw/rapid/symbol/data/{symbolurl}`` and symbol property
        reads through ``trajcenter.rws.reader.read_robot_context``.

    Writes:
        Delegated to ``trajcenter.rws.writer.write_resolved_trajectory`` using
        Mastership-protected RWS writes.

ABB Constraints:
    - ``selectedTrajIndex`` is RAPID base-1.
    - ``0`` means no selected trajectory and is rejected by this transfer entry
      point.
    - The local store order must match the metadata previously written to
      ``trajectories{1..nbTrajAvailable}``.
    - No RAPID write is performed directly in this module.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path

from abb_rws_client_python_rw6 import RWSClient

from trajcenter.core.logger import get_logger
from trajcenter.core.trajectory import Trajectory
from trajcenter.rws.constants import (
    DEFAULT_MASTERSHIP_RETRIES,
    DEFAULT_MASTERSHIP_RETRY_DELAY_S,
    DEFAULT_PROGRESS_UPDATE_STEP_PERCENT,
    DEFAULT_TASK,
    WEB_MODULE,
)
from trajcenter.rws.models import ResolvedTrajectory, TrajectoryStoreEntry
from trajcenter.rws.reader import read_robot_context, read_selected_traj_index
from trajcenter.rws.resolver import resolve_trajectory
from trajcenter.rws.store import scan_trajectory_store, store_entries_to_metadata
from trajcenter.rws.writer import write_resolved_trajectory, write_store_metadata

logger = get_logger(__name__)


async def refresh_store_metadata(
    client: RWSClient,
    store_root: str | Path,
    *,
    task: str = DEFAULT_TASK,
    module: str = WEB_MODULE,
    mastership_retries: int = 3,
) -> tuple[TrajectoryStoreEntry, ...]:
    """Refresh robot-side trajectory store metadata from a local directory.

    ABB Route:
        Writes through ``write_store_metadata``:

        - ``POST /rw/mastership/rapid`` with ``action=request``;
        - ``POST /rw/rapid/symbol/data/{symbolurl}`` with ``action=set``;
        - ``POST /rw/mastership/rapid`` with ``action=release``.

    ABB Constraints:
        - Local archives are sorted by file name/path through
          ``scan_trajectory_store``.
        - Returned ``TrajectoryStoreEntry.index`` values are RAPID base-1.
        - Metadata order must remain stable because ``selectedTrajIndex`` maps
          directly to this order.
        - ``9E+9`` is not read from or written to ``.trajcenter`` archives.
        - RAPID writes are delegated to ``write_store_metadata``, which acquires
          Mastership and releases it through the ABB RWS client helper.

    Args:
        client: Open RWS client.
        store_root: Directory containing local ``.trajcenter`` archives.
        task: RAPID task name.
        module: RAPID module name containing TrajCenter web-service variables.
        mastership_retries: Number of retries if RAPID Mastership is denied.

    Returns:
        Store entries that were written to robot metadata.

    Raises:
        FileNotFoundError: If ``store_root`` does not exist.
        NotADirectoryError: If ``store_root`` is not a directory.
        ValueError: If the store is invalid or exceeds RAPID limits.
        MastershipDenied: If Mastership cannot be acquired after all retries.
        RWSHTTPError: On unexpected controller HTTP errors.

    Example:
        ::

            entries = await refresh_store_metadata(client, "trajectory_store")
    """
    entries = scan_trajectory_store(store_root)
    names, point_counts, process_types = store_entries_to_metadata(entries)

    logger.info(
        "Refreshing store metadata from %s: %d trajectories",
        Path(store_root),
        len(entries),
    )

    await write_store_metadata(
        client,
        names,
        point_counts,
        task=task,
        module=module,
        process_types=process_types,
        mastership_retries=mastership_retries,
    )

    logger.info("Store metadata refresh completed: %d trajectories", len(entries))
    return entries


def get_store_entry_by_selected_index(
    entries: Sequence[TrajectoryStoreEntry],
    selected_index: int,
) -> TrajectoryStoreEntry:
    """Return the local store entry matching ``selectedTrajIndex``.

    ABB Route:
        N/A — local store lookup.

    ABB Constraints:
        ``selectedTrajIndex`` is a RAPID base-1 index. ``0`` means no selected
        trajectory and is invalid for a transfer request.

    Args:
        entries: Ordered local trajectory store entries.
        selected_index: RAPID base-1 selected trajectory index.

    Returns:
        Matching trajectory store entry.

    Raises:
        ValueError: If ``selected_index`` is lower than ``1``.
        IndexError: If no entry matches the selected index.

    Example:
        ::

            entry = get_store_entry_by_selected_index(entries, 1)
    """
    if selected_index < 1:
        raise ValueError(
            "selectedTrajIndex must be >= 1 for trajectory transfer, "
            f"got {selected_index}"
        )

    for entry in entries:
        if entry.index == selected_index:
            return entry

    raise IndexError(
        "selectedTrajIndex does not match any local trajectory store entry: "
        f"{selected_index}"
    )


async def transfer_selected_trajectory(
    client: RWSClient,
    entries: Sequence[TrajectoryStoreEntry],
    *,
    task: str = DEFAULT_TASK,
    module: str = WEB_MODULE,
    on_progress: Callable[[int, int], None] | None = None,
    mastership_retries: int = DEFAULT_MASTERSHIP_RETRIES,
    retry_delay_s: float = DEFAULT_MASTERSHIP_RETRY_DELAY_S,
    progress_step_percent: int = DEFAULT_PROGRESS_UPDATE_STEP_PERCENT,
) -> ResolvedTrajectory:
    """Transfer the trajectory selected by the robot HMI to RAPID variables.

    ABB Route:
        Reads:
            ``GET /rw/rapid/symbol/data/RAPID/{task}/{module}/selectedTrajIndex``.

        Writes:
            Delegated to ``write_resolved_trajectory``:
            ``POST /rw/rapid/symbol/data/{symbolurl}?action=set`` under RAPID
            Mastership.

    ABB Constraints:
        - ``selectedTrajIndex`` is base-1.
        - ``selectedTrajIndex == 0`` is rejected because no trajectory is
          selected.
        - The selected local ``.trajcenter`` archive is loaded through
          ``Trajectory.load``.
        - Resolver and writer enforce the final RAPID protocol constraints.

    Args:
        client: Open RWS client.
        entries: Local trajectory store entries ordered as exposed to the robot.
        task: RAPID task name.
        module: Web-services RAPID module containing ``selectedTrajIndex``.
        on_progress: Optional progress callback forwarded to the writer.
        mastership_retries: Number of writer Mastership retry attempts.
        retry_delay_s: Delay between Mastership retry attempts.
        progress_step_percent: Minimum writer progress step.

    Returns:
        Resolved trajectory that was written to the controller.

    Raises:
        ValueError: If no valid trajectory is selected.
        IndexError: If the selected index is not present in ``entries``.
        FileNotFoundError: If the selected local archive does not exist.
        RWSHTTPError: On unexpected controller HTTP errors.
        MastershipDenied: If writer Mastership cannot be acquired.

    Example:
        ::

            resolved = await transfer_selected_trajectory(client, entries)
    """
    selected_index = await read_selected_traj_index(
        client,
        task=task,
        module=module,
    )
    entry = get_store_entry_by_selected_index(entries, selected_index)

    logger.info(
        "Selected trajectory index %d maps to local archive %s",
        selected_index,
        entry.path,
    )

    trajectory = _load_store_entry_trajectory(entry)
    context = await read_robot_context(client, task=task)
    resolved = resolve_trajectory(trajectory, context)

    await write_resolved_trajectory(
        client,
        resolved,
        task=task,
        module=module,
        on_progress=on_progress,
        mastership_retries=mastership_retries,
        retry_delay_s=retry_delay_s,
        progress_step_percent=progress_step_percent,
    )

    logger.info(
        "Selected trajectory '%s' transferred successfully from %s",
        resolved.name,
        entry.path,
    )
    return resolved


def _load_store_entry_trajectory(entry: TrajectoryStoreEntry) -> Trajectory:
    """Load the ``.trajcenter`` archive referenced by a store entry.

    ABB Route:
        N/A — local archive loading.

    ABB Constraints:
        The inactive external-axis sentinel ``9E+9`` is not injected while
        loading a local archive. It belongs only to RWS writer serialization.

    Args:
        entry: Store entry selected by RAPID ``selectedTrajIndex``.

    Returns:
        Loaded trajectory.

    Raises:
        FileNotFoundError: If the archive does not exist.
        ValueError: If the archive is invalid.

    Example:
        ::

            trajectory = _load_store_entry_trajectory(entry)
    """
    path = Path(entry.path)
    logger.debug("Loading selected trajectory archive: %s", path)
    return Trajectory.load(path)
