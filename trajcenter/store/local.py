"""Local trajectory store scanner for TrajCenter."""

from __future__ import annotations

import zipfile
from collections.abc import Sequence
from pathlib import Path

from trajcenter.core.logger import get_logger
from trajcenter.core.trajectory import Trajectory
from trajcenter.store.constants import TRAJCENTER_SUFFIX
from trajcenter.store.models import TrajectoryStoreEntry

logger = get_logger(__name__)


def scan_trajectory_store(
    root: str | Path,
    *,
    max_entries: int | None = None,
) -> tuple[TrajectoryStoreEntry, ...]:
    """Scan a directory and return sorted trajectory store entries.

    Args:
        root: Directory containing ``.trajcenter`` archives.
        max_entries: Optional maximum number of accepted archives.

    Returns:
        Tuple of store entries sorted by archive file name.

    Raises:
        FileNotFoundError: If ``root`` does not exist.
        NotADirectoryError: If ``root`` is not a directory.
        ValueError: If too many archives are found or if one archive is invalid.
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
                if path.is_file() and path.suffix.lower() == TRAJCENTER_SUFFIX
            ),
            key=lambda path: path.name.lower(),
        )
    )

    if max_entries is not None and len(paths) > max_entries:
        raise ValueError(
            f"Trajectory store contains {len(paths)} archives "
            f"but max_entries={max_entries}"
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


def find_store_entry(
    entries: Sequence[TrajectoryStoreEntry],
    query: str,
) -> TrajectoryStoreEntry:
    """Find one store entry by index, metadata name, filename or stem.

    Args:
        entries: Store entries to search.
        query: User query.

    Returns:
        Matching store entry.

    Raises:
        LookupError: If no entry matches the query or if the query is ambiguous.
    """
    normalized_query = query.casefold()

    if query.isdecimal():
        index = int(query)
        for entry in entries:
            if entry.index == index:
                return entry

    matches = [
        entry
        for entry in entries
        if normalized_query
        in {
            entry.name.casefold(),
            entry.path.name.casefold(),
            entry.path.stem.casefold(),
        }
    ]

    if len(matches) == 1:
        return matches[0]

    if len(matches) > 1:
        names = ", ".join(f"{entry.index}:{entry.name}" for entry in matches)
        raise LookupError(f"Ambiguous trajectory query '{query}': {names}")

    raise LookupError(f"Trajectory not found in store: {query}")
