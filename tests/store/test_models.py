#!/usr/bin/env python3
"""Unit tests for :mod:`trajcenter.store.models`."""

from __future__ import annotations

from pathlib import Path

from trajcenter.store.models import TrajectoryStoreEntry


class TestTrajectoryStoreEntry:
    """Tests for :class:`trajcenter.store.models.TrajectoryStoreEntry`."""

    def test_store_entry(self) -> None:
        """A store entry maps one-based index to a trajectory archive path."""
        entry = TrajectoryStoreEntry(
            index=1,
            path=Path("trajectory_store/demo.trajcenter"),
            name="demo",
            point_count=10,
            process_type=0,
        )

        assert entry.index == 1
        assert entry.path == Path("trajectory_store/demo.trajcenter")
        assert entry.name == "demo"
        assert entry.point_count == 10
        assert entry.process_type == 0
