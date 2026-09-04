"""Metadata helpers for local TrajCenter trajectory stores."""

from __future__ import annotations

from collections.abc import Sequence

from trajcenter.store.models import TrajectoryStoreEntry


def store_entries_to_metadata(
    entries: Sequence[TrajectoryStoreEntry],
    *,
    max_entries: int | None = None,
) -> tuple[list[str], list[int], list[int]]:
    """Convert store entries to metadata lists.

    Args:
        entries: Store entries produced by ``scan_trajectory_store``.
        max_entries: Optional maximum number of accepted entries.

    Returns:
        Tuple ``(names, point_counts, process_types)``.

    Raises:
        ValueError: If more than ``max_entries`` entries are provided.
    """
    if max_entries is not None and len(entries) > max_entries:
        raise ValueError(f"Got {len(entries)} entries but max_entries={max_entries}")

    names = [entry.name for entry in entries]
    point_counts = [entry.point_count for entry in entries]
    process_types = [entry.process_type for entry in entries]

    return names, point_counts, process_types
