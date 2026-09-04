"""Typed models for local TrajCenter trajectory stores."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class TrajectoryStoreEntry:
    """One trajectory archive discovered in a local TrajCenter store.

    Args:
        index: One-based stable store index.
        path: Path to the ``.trajcenter`` archive.
        name: Trajectory display name from archive metadata.
        point_count: Number of trajectory points.
        process_type: Trajectory process type.
    """

    index: int
    path: Path
    name: str
    point_count: int
    process_type: int
