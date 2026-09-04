#!/usr/bin/env python3
"""Unit tests for :mod:`trajcenter.store.metadata`."""

from __future__ import annotations

from pathlib import Path

import pytest

from trajcenter.store.metadata import store_entries_to_metadata
from trajcenter.store.models import TrajectoryStoreEntry


def _entry(
    *,
    index: int,
    path: Path,
    name: str,
    point_count: int,
    process_type: int,
) -> TrajectoryStoreEntry:
    """Build a trajectory store entry."""
    return TrajectoryStoreEntry(
        index=index,
        path=path,
        name=name,
        point_count=point_count,
        process_type=process_type,
    )


class TestStoreEntriesToMetadata:
    """Tests for :func:`trajcenter.store.metadata.store_entries_to_metadata`."""

    def test_empty_entries(self) -> None:
        """Empty entries produce empty metadata lists."""
        names, counts, process_types = store_entries_to_metadata(())

        assert names == []
        assert counts == []
        assert process_types == []

    def test_converts_entries_preserving_order(self, tmp_path: Path) -> None:
        """Entry order is preserved."""
        path_a = tmp_path / "a.trajcenter"
        path_b = tmp_path / "b.trajcenter"

        entries = (
            _entry(
                index=1,
                path=path_a,
                name="A",
                point_count=10,
                process_type=0,
            ),
            _entry(
                index=2,
                path=path_b,
                name="B",
                point_count=20,
                process_type=1,
            ),
        )

        names, counts, process_types = store_entries_to_metadata(entries)

        assert names == ["A", "B"]
        assert counts == [10, 20]
        assert process_types == [0, 1]

    def test_too_many_entries_raises_when_max_entries_is_set(
        self,
        tmp_path: Path,
    ) -> None:
        """More than ``max_entries`` entries are rejected."""
        entries = tuple(
            _entry(
                index=index + 1,
                path=tmp_path / f"{index}.trajcenter",
                name=f"T{index}",
                point_count=1,
                process_type=0,
            )
            for index in range(3)
        )

        with pytest.raises(ValueError, match="max_entries=2"):
            store_entries_to_metadata(entries, max_entries=2)
