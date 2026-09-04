#!/usr/bin/env python3
"""Unit tests for :mod:`trajcenter.store.local`.

The scanner tests create real temporary ``.trajcenter`` archives and never
contact an ABB controller.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from trajcenter.core.trajectory import (
    Trajectory,
    TrajectoryMeta,
    TrajectoryProcess,
)
from trajcenter.store.local import scan_trajectory_store


def _make_points(
    *,
    n: int = 1,
    process_param_indexes: list[int] | None = None,
) -> pd.DataFrame:
    """Build a valid points table for store scanner tests."""
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
    """Build a valid process parameter table."""
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
    """Create one temporary ``.trajcenter`` archive."""
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
    """Tests for :func:`trajcenter.store.local.scan_trajectory_store`."""

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
        """Store entries expose archive metadata."""
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
        """Invalid ``.trajcenter`` archives raise ``ValueError``."""
        invalid = tmp_path / "bad.trajcenter"
        invalid.write_text("not a zip archive", encoding="utf-8")

        with pytest.raises(ValueError):
            scan_trajectory_store(tmp_path)

    def test_too_many_archives_raises_when_max_entries_is_set(
        self,
        tmp_path: Path,
    ) -> None:
        """More than ``max_entries`` archives are rejected before loading."""
        for index in range(3):
            path = tmp_path / f"{index:03d}.trajcenter"
            path.write_text("placeholder", encoding="utf-8")

        with pytest.raises(ValueError, match="max_entries=2"):
            scan_trajectory_store(tmp_path, max_entries=2)
