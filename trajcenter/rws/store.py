#!/usr/bin/env python3
# trajcenter/rws/store.py
"""Local trajectory store scanner for TrajCenter ABB RWS integration.

Author: Clement RACINET

This module scans a local directory containing ``.trajcenter`` archives and
builds immutable ``TrajectoryStoreEntry`` objects. These entries are then used
to refresh robot-side metadata and to map ``selectedTrajIndex`` to a local
archive during transfer.

ABB Route:
    N/A — local filesystem operations only.

ABB Constraints:
    - ``TrajectoryStoreEntry.index`` is RAPID base-1.
    - Store ordering must be stable because robot ``selectedTrajIndex`` maps
      directly to this order.
    - The scanner sorts archives by path/name, not by ``meta.name``.
    - ``9E+9`` inactive-axis sentinel is never injected while scanning local
      archives.

Example:
    ::

        entries = scan_trajectory_store("trajectory_store")
        names, counts, process_types = store_entries_to_metadata(entries)
"""

from __future__ import annotations

import zipfile
from collections.abc import Sequence
from pathlib import Path

from trajcenter.core.logger import get_logger
from trajcenter.core.trajectory import Trajectory
from trajcenter.rws.constants import MAX_TRAJ
from trajcenter.rws.models import TrajectoryStoreEntry

logger = get_logger(__name__)

_TRAJCENTER_SUFFIX = ".trajcenter"


def scan_trajectory_store(root: str | Path) -> tuple[TrajectoryStoreEntry, ...]:
    """Scan a directory and return sorted trajectory store entries.

    ABB Route:
        N/A — local filesystem scanner.

    ABB Constraints:
        The returned indexes are RAPID base-1 and must match the order exposed
        to ``TRAJCENTER_WebServices/trajectories``. Archives are sorted by file
        name/path for deterministic selection.

    Args:
        root: Directory containing ``.trajcenter`` archives.

    Returns:
        Tuple of store entries sorted by archive path.

    Raises:
        FileNotFoundError: If ``root`` does not exist.
        NotADirectoryError: If ``root`` is not a directory.
        ValueError: If more than ``MAX_TRAJ`` archives are found or if one
            archive is invalid.

    Example:
        ::

            entries = scan_trajectory_store("trajectory_store")
    """
    store_root = Path(root)

    if not store_root.exists():
        raise FileNotFoundError(
            f"Trajectory store directory does not exist: {store_root}"
        )

    if not store_root.is_dir():
        raise NotADirectoryError(
            f"Trajectory store path is not a directory: {store_root}"
        )

    paths = tuple(
        sorted(
            (
                path
                for path in store_root.iterdir()
                if path.is_file() and path.suffix.lower() == _TRAJCENTER_SUFFIX
            ),
            key=lambda path: path.name.lower(),
        )
    )

    if len(paths) > MAX_TRAJ:
        raise ValueError(
            f"Trajectory store contains {len(paths)} archives but MAX_TRAJ={MAX_TRAJ}"
        )

    entries: list[TrajectoryStoreEntry] = []
    for index, path in enumerate(paths, start=1):
        try:
            trajectory = Trajectory.load(path)
        except zipfile.BadZipFile as exc:
            raise ValueError(f"Invalid .trajcenter archive: {path}") from exc

        entries.append(
            TrajectoryStoreEntry(
                index=index,
                path=path.resolve(),
                name=trajectory.meta.name,
                point_count=trajectory.point_count,
                process_type=trajectory.meta.process.process_type,
            )
        )

    logger.info("Scanned %d trajectory archives from %s", len(entries), store_root)
    return tuple(entries)


def store_entries_to_metadata(
    entries: Sequence[TrajectoryStoreEntry],
) -> tuple[list[str], list[int], list[int]]:
    """Convert store entries to writer metadata lists.

    ABB Route:
        N/A — local adapter for ``write_store_metadata``.

    ABB Constraints:
        The order must be preserved because list position maps to RAPID
        ``trajectories{i}``.

    Args:
        entries: Store entries produced by ``scan_trajectory_store``.

    Returns:
        Tuple ``(names, point_counts, process_types)``.

    Raises:
        ValueError: If more than ``MAX_TRAJ`` entries are provided.

    Example:
        ::

            names, counts, process_types = store_entries_to_metadata(entries)
    """
    if len(entries) > MAX_TRAJ:
        raise ValueError(f"Got {len(entries)} entries but MAX_TRAJ={MAX_TRAJ}")

    names = [entry.name for entry in entries]
    point_counts = [entry.point_count for entry in entries]
    process_types = [entry.process_type for entry in entries]

    return names, point_counts, process_types
