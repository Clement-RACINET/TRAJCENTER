#!/usr/bin/env python3
# tests/rws/test_store.py
"""Unit tests for :mod:`trajcenter.rws.store`.

Author: Clement RACINET

The scanner tests create real temporary ``.trajcenter`` archives and never
contact an ABB controller.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from trajcenter.core.trajectory import (
    MAX_PROCESS_PARAM_SET_COUNT,
    Trajectory,
    TrajectoryMeta,
    TrajectoryProcess,
)
from trajcenter.rws.constants import MAX_TRAJ
from trajcenter.rws.store import scan_trajectory_store, store_entries_to_metadata


def _make_points(
    *,
    n: int = 1,
    process_param_indexes: list[int] | None = None,
) -> pd.DataFrame:
    """Build a valid points table for store scanner tests.

    ABB Route:
        N/A — local test helper.

    ABB Constraints:
        No ``9E+9`` sentinel is stored in local trajectory archives.

    Args:
        n: Number of points.
        process_param_indexes: Optional process parameter indexes.

    Returns:
        Points DataFrame.

    Raises:
        None.

    Example:
        ::

            points = _make_points(n=2)
    """
    data: dict[str, object] = {
        "x": [100.0 + i for i in range(n)],
        "y": [200.0] * n,
        "z": [300.0] * n,
        "q1": [1.0] * n,
        "q2": [0.0] * n,
        "q3": [0.0] * n,
        "q4": [0.0] * n,
        "cf1": [0] * n,
        "cf4": [0] * n,
        "cf6": [0] * n,
        "cfx": [0] * n,
        "move_type": ["MoveL"] * n,
        "tcp_speed": [500.0] * n,
        "zone_type": [10] * n,
        "readconfs": [True] * n,
        "tool_name": ["tool0"] * n,
        "wobj_name": ["wobj0"] * n,
    }

    if process_param_indexes is not None:
        data["process_param_index"] = process_param_indexes

    return pd.DataFrame(data)


def _make_process_params() -> pd.DataFrame:
    """Build a valid process parameter table.

    ABB Route:
        N/A — local test helper.

    ABB Constraints:
        ``process_param_index`` uses base-1 local source indexes.

    Args:
        None.

    Returns:
        Process parameter DataFrame.

    Raises:
        None.

    Example:
        ::

            params = _make_process_params()
    """
    return pd.DataFrame(
        {
            "process_param_index": [1],
            "force": [120.0],
            "speed": [42.5],
        }
    )


def _save_archive(
    tmp_path: Path,
    *,
    filename: str,
    meta_name: str,
    point_count: int = 1,
    process_type: int = 0,
) -> Path:
    """Create one temporary ``.trajcenter`` archive.

    ABB Route:
        N/A — local test helper.

    ABB Constraints:
        Archive creation goes through the real ``Trajectory.save`` method.

    Args:
        tmp_path: Pytest temporary directory.
        filename: Archive file name.
        meta_name: Trajectory metadata name.
        point_count: Number of points.
        process_type: Process type.

    Returns:
        Path to the archive.

    Raises:
        ValueError: If test trajectory data is inconsistent.
        OSError: If the archive cannot be written.

    Example:
        ::

            path = _save_archive(tmp_path, filename="a.trajcenter", meta_name="A")
    """
    if process_type == 0:
        trajectory = Trajectory(
            meta=TrajectoryMeta(name=meta_name),
            points=_make_points(n=point_count),
        )
    else:
        trajectory = Trajectory(
            meta=TrajectoryMeta(
                name=meta_name,
                process=TrajectoryProcess(
                    process_type=process_type,
                    process_param_names=["force", "speed"],
                ),
            ),
            points=_make_points(
                n=point_count,
                process_param_indexes=[1] * point_count,
            ),
            process_params=_make_process_params(),
        )

    return trajectory.save(tmp_path / filename)


class TestScanTrajectoryStore:
    """Tests for :func:`trajcenter.rws.store.scan_trajectory_store`."""

    def test_empty_directory_returns_empty_tuple(self, tmp_path: Path) -> None:
        """An empty store returns no entries."""
        assert scan_trajectory_store(tmp_path) == ()

    def test_missing_directory_raises(self, tmp_path: Path) -> None:
        """A missing store directory raises ``FileNotFoundError``."""
        missing = tmp_path / "missing"

        with pytest.raises(FileNotFoundError, match="does not exist"):
            scan_trajectory_store(missing)

    def test_file_instead_of_directory_raises(self, tmp_path: Path) -> None:
        """A file path instead of a directory raises ``NotADirectoryError``."""
        file_path = tmp_path / "not_a_dir.txt"
        file_path.write_text("x", encoding="utf-8")

        with pytest.raises(NotADirectoryError, match="not a directory"):
            scan_trajectory_store(file_path)

    def test_scans_archives_sorted_by_filename(self, tmp_path: Path) -> None:
        """Archives are sorted by filename, not by metadata name."""
        path_b = _save_archive(
            tmp_path,
            filename="b.trajcenter",
            meta_name="Meta B",
        )
        path_a = _save_archive(
            tmp_path,
            filename="a.trajcenter",
            meta_name="Meta A",
        )

        entries = scan_trajectory_store(tmp_path)

        assert len(entries) == 2
        assert entries[0].index == 1
        assert entries[0].path == path_a.resolve()
        assert entries[0].name == "Meta A"
        assert entries[1].index == 2
        assert entries[1].path == path_b.resolve()
        assert entries[1].name == "Meta B"

    def test_sort_is_case_insensitive(self, tmp_path: Path) -> None:
        """Filename sorting uses lowercase keys for stable ordering."""
        _save_archive(tmp_path, filename="b.trajcenter", meta_name="B")
        _save_archive(tmp_path, filename="A.trajcenter", meta_name="A")

        entries = scan_trajectory_store(tmp_path)

        assert [entry.path.name for entry in entries] == [
            "A.trajcenter",
            "b.trajcenter",
        ]

    def test_ignores_non_trajcenter_files(self, tmp_path: Path) -> None:
        """Only files ending with ``.trajcenter`` are scanned."""
        _save_archive(tmp_path, filename="a.trajcenter", meta_name="A")
        (tmp_path / "notes.txt").write_text("ignored", encoding="utf-8")
        (tmp_path / "b.zip").write_text("ignored", encoding="utf-8")

        entries = scan_trajectory_store(tmp_path)

        assert len(entries) == 1
        assert entries[0].name == "A"

    def test_suffix_is_case_insensitive(self, tmp_path: Path) -> None:
        """Uppercase ``.TRAJCENTER`` suffix is accepted."""
        _save_archive(tmp_path, filename="a.TRAJCENTER", meta_name="A")

        entries = scan_trajectory_store(tmp_path)

        assert len(entries) == 1
        assert entries[0].name == "A"

    def test_subdirectories_are_ignored(self, tmp_path: Path) -> None:
        """Nested directories are ignored by the flat store scanner."""
        _save_archive(tmp_path, filename="a.trajcenter", meta_name="A")
        nested = tmp_path / "nested"
        nested.mkdir()
        _save_archive(nested, filename="b.trajcenter", meta_name="B")

        entries = scan_trajectory_store(tmp_path)

        assert len(entries) == 1
        assert entries[0].name == "A"

    def test_entry_contains_point_count_and_process_type(self, tmp_path: Path) -> None:
        """Store entries expose metadata required by ``write_store_metadata``."""
        _save_archive(
            tmp_path,
            filename="process.trajcenter",
            meta_name="Process",
            point_count=3,
            process_type=1,
        )

        entries = scan_trajectory_store(tmp_path)

        assert len(entries) == 1
        assert entries[0].point_count == 3
        assert entries[0].process_type == 1

    def test_invalid_archive_raises_value_error(self, tmp_path: Path) -> None:
        """Invalid ``.trajcenter`` archives propagate validation errors."""
        invalid = tmp_path / "bad.trajcenter"
        invalid.write_text("not a zip archive", encoding="utf-8")

        with pytest.raises(ValueError):
            scan_trajectory_store(tmp_path)

    def test_too_many_archives_raises(self, tmp_path: Path) -> None:
        """More than ``MAX_TRAJ`` archives are rejected before loading."""
        for index in range(MAX_TRAJ + 1):
            path = tmp_path / f"{index:03d}.trajcenter"
            path.write_text("placeholder", encoding="utf-8")

        with pytest.raises(ValueError, match="MAX_TRAJ"):
            scan_trajectory_store(tmp_path)

    def test_max_process_param_set_count_constant_is_available(self) -> None:
        """The imported process limit remains aligned with trajectory tests."""
        assert MAX_PROCESS_PARAM_SET_COUNT == 256


class TestStoreEntriesToMetadata:
    """Tests for :func:`trajcenter.rws.store.store_entries_to_metadata`."""

    def test_empty_entries(self) -> None:
        """Empty entries produce empty metadata lists."""
        names, counts, process_types = store_entries_to_metadata(())

        assert names == []
        assert counts == []
        assert process_types == []

    def test_converts_entries_preserving_order(self, tmp_path: Path) -> None:
        """Entry order is preserved for RAPID metadata mapping."""
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

    def test_too_many_entries_raises(self, tmp_path: Path) -> None:
        """More than ``MAX_TRAJ`` entries are rejected."""
        entries = tuple(
            _entry(
                index=index + 1,
                path=tmp_path / f"{index}.trajcenter",
                name=f"T{index}",
                point_count=1,
                process_type=0,
            )
            for index in range(MAX_TRAJ + 1)
        )

        with pytest.raises(ValueError, match="MAX_TRAJ"):
            store_entries_to_metadata(entries)


def _entry(
    *,
    index: int,
    path: Path,
    name: str,
    point_count: int,
    process_type: int,
):
    """Build a ``TrajectoryStoreEntry`` without importing it at top level.

    ABB Route:
        N/A — local test helper.

    ABB Constraints:
        ``index`` is RAPID base-1.

    Args:
        index: Store index.
        path: Archive path.
        name: Display name.
        point_count: Number of points.
        process_type: Process type.

    Returns:
        Store entry.

    Raises:
        None.

    Example:
        ::

            entry = _entry(index=1, path=path, name="A", point_count=1, process_type=0)
    """
    from trajcenter.rws.models import TrajectoryStoreEntry

    return TrajectoryStoreEntry(
        index=index,
        path=path,
        name=name,
        point_count=point_count,
        process_type=process_type,
    )
