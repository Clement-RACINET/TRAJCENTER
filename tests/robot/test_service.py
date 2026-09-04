#!/usr/bin/env python3
# tests/robot/abb/test_service.py
"""Unit tests for :mod:`trajcenter.robot.service`.

Author: Clement RACINET

All RWS reader and writer operations are mocked. Local archive loading is tested
with real ``.trajcenter`` files generated in temporary directories.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest
from abb_rws_client_python_rw6 import MastershipDenied

from trajcenter.core.trajectory import Trajectory, TrajectoryMeta
from trajcenter.robot.constants import MAX_TRAJ
from trajcenter.robot.models import (
    ProcessTypeEntry,
    RobotContext,
    RobotDefaults,
)
from trajcenter.robot.service import (
    get_store_entry_by_selected_index,
    refresh_store_metadata,
    transfer_selected_trajectory,
)
from trajcenter.store.models import TrajectoryStoreEntry

_MODULE = "trajcenter.robot.service"


@pytest.fixture
def client() -> MagicMock:
    """Return a bare ``MagicMock`` acting as ``RWSClient``.

    ABB Route:
        N/A — test fixture.

    ABB Constraints:
        No controller access is performed.

    Args:
        None.

    Returns:
        Mock RWS client.


    Example:
        ::

            client = MagicMock()
    """
    return MagicMock()


def _make_points() -> pd.DataFrame:
    """Build a minimal valid trajectory points table.

    ABB Route:
        N/A — local test helper.

    ABB Constraints:
        The table uses TrajCenter v2 columns and stores no ``9E+9`` sentinel.

    Args:
        None.

    Returns:
        Points DataFrame.


    Example:
        ::

            points = _make_points()
    """
    return pd.DataFrame(
        {
            "x": [100.0],
            "y": [200.0],
            "z": [300.0],
            "q1": [1.0],
            "q2": [0.0],
            "q3": [0.0],
            "q4": [0.0],
            "cf1": [0],
            "cf4": [0],
            "cf6": [0],
            "cfx": [0],
            "move_type": ["MoveL"],
            "tcp_speed": [500.0],
            "zone_type": [10],
            "readconfs": [True],
            "tool_name": ["tool0"],
            "wobj_name": ["wobj0"],
        }
    )


def _make_trajectory(name: str = "demo") -> Trajectory:
    """Build a minimal no-process trajectory.

    ABB Route:
        N/A — local test helper.

    ABB Constraints:
        No process parameters are attached because ``process_type == 0``.

    Args:
        name: Trajectory display name.

    Returns:
        Trajectory instance.

    Raises:
        ValueError: If the test data is invalid.

    Example:
        ::

            trajectory = _make_trajectory()
    """
    return Trajectory(
        meta=TrajectoryMeta(name=name),
        points=_make_points(),
    )


def _save_trajectory(tmp_path: Path, name: str = "demo") -> Path:
    """Save one temporary ``.trajcenter`` archive.

    ABB Route:
        N/A — local test helper.

    ABB Constraints:
        The archive is saved through the real ``Trajectory.save`` path.

    Args:
        tmp_path: Pytest temporary directory.
        name: Trajectory display name.

    Returns:
        Path to the saved archive.

    Raises:
        OSError: If the archive cannot be written.
        ValueError: If serialization fails.

    Example:
        ::

            path = _save_trajectory(tmp_path)
    """
    return _make_trajectory(name=name).save(tmp_path / f"{name}.trajcenter")


def _make_entry(
    path: Path,
    *,
    index: int = 1,
    name: str = "demo",
) -> TrajectoryStoreEntry:
    """Build a trajectory store entry for tests.

    ABB Route:
        N/A — local test helper.

    ABB Constraints:
        ``index`` is RAPID base-1 and maps to ``selectedTrajIndex``.

    Args:
        path: Path to the local ``.trajcenter`` archive.
        index: One-based store index.
        name: Trajectory display name.

    Returns:
        Store entry.


    Example:
        ::

            entry = _make_entry(path)
    """
    return TrajectoryStoreEntry(
        index=index,
        path=path,
        name=name,
        point_count=1,
        process_type=0,
    )


def _make_context() -> RobotContext:
    """Build a minimal robot context accepted by the resolver.

    ABB Route:
        N/A — local test helper.

    ABB Constraints:
        Tool and workobject names are ordered as RAPID base-1 arrays.

    Args:
        None.

    Returns:
        Robot context.


    Example:
        ::

            context = _make_context()
    """
    return RobotContext(
        defaults=RobotDefaults(
            has_tcp_speed=True,
            tcp_speed=500.0,
            has_zone_type=True,
            zone_type=10,
            has_tool_name=True,
            tool_name="tool0",
            has_wobj_name=True,
            wobj_name="wobj0",
            move_type=0,
            read_confs=True,
        ),
        tool_names=("tool0",),
        wobj_names=("wobj0",),
        process_types=(ProcessTypeEntry(id=0, name="NONE"),),
    )


class TestGetStoreEntryBySelectedIndex:
    """Tests for store entry lookup from RAPID selected index."""

    def test_nominal(self, tmp_path: Path) -> None:
        """A base-1 selected index returns the matching entry."""
        entry_1 = _make_entry(tmp_path / "a.trajcenter", index=1, name="a")
        entry_2 = _make_entry(tmp_path / "b.trajcenter", index=2, name="b")

        assert get_store_entry_by_selected_index((entry_1, entry_2), 2) == entry_2

    def test_zero_rejected(self, tmp_path: Path) -> None:
        """``selectedTrajIndex == 0`` means no selected trajectory."""
        entry = _make_entry(tmp_path / "a.trajcenter", index=1, name="a")

        with pytest.raises(ValueError, match="selectedTrajIndex"):
            get_store_entry_by_selected_index((entry,), 0)

    def test_negative_rejected(self, tmp_path: Path) -> None:
        """Negative selected indexes are rejected."""
        entry = _make_entry(tmp_path / "a.trajcenter", index=1, name="a")

        with pytest.raises(ValueError, match="selectedTrajIndex"):
            get_store_entry_by_selected_index((entry,), -1)

    def test_missing_index_raises(self, tmp_path: Path) -> None:
        """An unknown selected index raises ``IndexError``."""
        entry = _make_entry(tmp_path / "a.trajcenter", index=1, name="a")

        with pytest.raises(IndexError, match="does not match"):
            get_store_entry_by_selected_index((entry,), 2)


class TestTransferSelectedTrajectory:
    """Tests for full selected trajectory transfer orchestration."""

    @pytest.mark.asyncio
    async def test_nominal_with_real_archive(
        self,
        client: MagicMock,
        tmp_path: Path,
    ) -> None:
        """The service loads, resolves and writes the selected trajectory."""
        path = _save_trajectory(tmp_path, name="demo")
        entry = _make_entry(path, index=1, name="demo")

        mock_read_index = AsyncMock(return_value=1)
        mock_read_context = AsyncMock(return_value=_make_context())
        mock_write = AsyncMock()

        with (
            patch(f"{_MODULE}.read_selected_traj_index", mock_read_index),
            patch(f"{_MODULE}.read_robot_context", mock_read_context),
            patch(f"{_MODULE}.write_resolved_trajectory", mock_write),
        ):
            resolved = await transfer_selected_trajectory(client, (entry,))

        assert resolved.name == "demo"
        assert resolved.point_count == 1
        mock_read_index.assert_awaited_once_with(
            client,
            task="T_ROB1",
            module="TRAJCENTER",
        )
        mock_read_context.assert_awaited_once_with(client, task="T_ROB1")
        mock_write.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_selected_index_zero_raises(
        self,
        client: MagicMock,
        tmp_path: Path,
    ) -> None:
        """No selected trajectory raises before loading or writing."""
        path = _save_trajectory(tmp_path, name="demo")
        entry = _make_entry(path, index=1, name="demo")

        with (
            patch(f"{_MODULE}.read_selected_traj_index", AsyncMock(return_value=0)),
            pytest.raises(ValueError, match="selectedTrajIndex"),
        ):
            await transfer_selected_trajectory(client, (entry,))

    @pytest.mark.asyncio
    async def test_selected_index_out_of_store_raises(
        self,
        client: MagicMock,
        tmp_path: Path,
    ) -> None:
        """A selected index missing from the local store raises ``IndexError``."""
        path = _save_trajectory(tmp_path, name="demo")
        entry = _make_entry(path, index=1, name="demo")

        with (
            patch(f"{_MODULE}.read_selected_traj_index", AsyncMock(return_value=2)),
            pytest.raises(IndexError, match="does not match"),
        ):
            await transfer_selected_trajectory(client, (entry,))

    @pytest.mark.asyncio
    async def test_missing_archive_raises(
        self,
        client: MagicMock,
        tmp_path: Path,
    ) -> None:
        """A missing selected archive propagates ``FileNotFoundError``."""
        entry = _make_entry(tmp_path / "missing.trajcenter", index=1, name="missing")

        with (
            patch(f"{_MODULE}.read_selected_traj_index", AsyncMock(return_value=1)),
            pytest.raises(FileNotFoundError),
        ):
            await transfer_selected_trajectory(client, (entry,))

    @pytest.mark.asyncio
    async def test_reader_error_is_propagated(
        self,
        client: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Errors from robot context reading are propagated."""
        path = _save_trajectory(tmp_path, name="demo")
        entry = _make_entry(path, index=1, name="demo")

        mock_read_index = AsyncMock(return_value=1)
        mock_read_context = AsyncMock(side_effect=ValueError("bad context"))

        with (
            patch(f"{_MODULE}.read_selected_traj_index", mock_read_index),
            patch(f"{_MODULE}.read_robot_context", mock_read_context),
            pytest.raises(ValueError, match="bad context"),
        ):
            await transfer_selected_trajectory(client, (entry,))

    @pytest.mark.asyncio
    async def test_resolver_error_is_propagated(
        self,
        client: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Errors from the resolver are propagated."""
        path = _save_trajectory(tmp_path, name="demo")
        entry = _make_entry(path, index=1, name="demo")

        with (
            patch(f"{_MODULE}.read_selected_traj_index", AsyncMock(return_value=1)),
            patch(
                f"{_MODULE}.read_robot_context",
                AsyncMock(return_value=_make_context()),
            ),
            patch(
                f"{_MODULE}.resolve_trajectory",
                MagicMock(side_effect=ValueError("resolve failed")),
            ),
            pytest.raises(ValueError, match="resolve failed"),
        ):
            await transfer_selected_trajectory(client, (entry,))

    @pytest.mark.asyncio
    async def test_writer_error_is_propagated(
        self,
        client: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Errors from the writer are propagated."""
        path = _save_trajectory(tmp_path, name="demo")
        entry = _make_entry(path, index=1, name="demo")

        mock_write = AsyncMock(side_effect=MastershipDenied("denied"))

        with (
            patch(f"{_MODULE}.read_selected_traj_index", AsyncMock(return_value=1)),
            patch(
                f"{_MODULE}.read_robot_context",
                AsyncMock(return_value=_make_context()),
            ),
            patch(f"{_MODULE}.write_resolved_trajectory", mock_write),
            pytest.raises(MastershipDenied),
        ):
            await transfer_selected_trajectory(client, (entry,))

    @pytest.mark.asyncio
    async def test_writer_receives_progress_and_transfer_options(
        self,
        client: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Progress callback and transfer options are forwarded to the writer."""
        path = _save_trajectory(tmp_path, name="demo")
        entry = _make_entry(path, index=1, name="demo")
        progress = MagicMock()
        mock_write = AsyncMock()

        with (
            patch(f"{_MODULE}.read_selected_traj_index", AsyncMock(return_value=1)),
            patch(
                f"{_MODULE}.read_robot_context",
                AsyncMock(return_value=_make_context()),
            ),
            patch(f"{_MODULE}.write_resolved_trajectory", mock_write),
        ):
            await transfer_selected_trajectory(
                client,
                (entry,),
                task="T_ROB2",
                module="MY_WEB",
                on_progress=progress,
                mastership_retries=5,
                retry_delay_s=0.25,
                progress_step_percent=10,
            )

        kwargs = mock_write.call_args.kwargs
        assert kwargs["task"] == "T_ROB2"
        assert kwargs["module"] == "MY_WEB"
        assert kwargs["on_progress"] is progress
        assert kwargs["mastership_retries"] == 5
        assert kwargs["retry_delay_s"] == 0.25
        assert kwargs["progress_step_percent"] == 10

    @pytest.mark.asyncio
    async def test_custom_task_and_module_are_used_for_selected_index(
        self,
        client: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Custom task and module are used when reading selected index."""
        path = _save_trajectory(tmp_path, name="demo")
        entry = _make_entry(path, index=1, name="demo")
        mock_read_index = AsyncMock(return_value=1)

        with (
            patch(f"{_MODULE}.read_selected_traj_index", mock_read_index),
            patch(
                f"{_MODULE}.read_robot_context",
                AsyncMock(return_value=_make_context()),
            ),
            patch(f"{_MODULE}.write_resolved_trajectory", AsyncMock()),
        ):
            await transfer_selected_trajectory(
                client,
                (entry,),
                task="T_ROB2",
                module="MY_WEB",
            )

        mock_read_index.assert_awaited_once_with(
            client,
            task="T_ROB2",
            module="MY_WEB",
        )


class TestRefreshStoreMetadata:
    """Tests for store metadata refresh orchestration."""

    @pytest.mark.asyncio
    async def test_nominal_refresh(
        self,
        client: MagicMock,
        tmp_path: Path,
    ) -> None:
        """The service scans local store and writes robot metadata."""
        path = _save_trajectory(tmp_path, name="demo")
        entry = _make_entry(path.resolve(), index=1, name="demo")
        mock_scan = MagicMock(return_value=(entry,))
        mock_to_metadata = MagicMock(return_value=(["demo"], [1], [0]))
        mock_write = AsyncMock()

        with (
            patch(f"{_MODULE}.scan_trajectory_store", mock_scan),
            patch(f"{_MODULE}.store_entries_to_metadata", mock_to_metadata),
            patch(f"{_MODULE}.write_store_metadata", mock_write),
        ):
            entries = await refresh_store_metadata(client, tmp_path)

        assert entries == (entry,)
        mock_scan.assert_called_once_with(tmp_path, max_entries=MAX_TRAJ)
        mock_to_metadata.assert_called_once_with((entry,), max_entries=MAX_TRAJ)
        mock_write.assert_awaited_once_with(
            client,
            ["demo"],
            [1],
            task="T_ROB1",
            module="TRAJCENTER",
            process_types=[0],
            mastership_retries=3,
        )

    @pytest.mark.asyncio
    async def test_custom_task_module_and_retries_forwarded(
        self,
        client: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Custom RWS write options are forwarded to metadata writer."""
        path = _save_trajectory(tmp_path, name="demo")
        entry = _make_entry(path.resolve(), index=1, name="demo")
        mock_scan = MagicMock(return_value=(entry,))
        mock_to_metadata = MagicMock(return_value=(["demo"], [1], [0]))
        mock_write = AsyncMock()

        with (
            patch(f"{_MODULE}.scan_trajectory_store", mock_scan),
            patch(f"{_MODULE}.store_entries_to_metadata", mock_to_metadata),
            patch(f"{_MODULE}.write_store_metadata", mock_write),
        ):
            await refresh_store_metadata(
                client,
                tmp_path,
                task="T_ROB2",
                module="MY_WEB",
                mastership_retries=5,
            )

        mock_scan.assert_called_once_with(tmp_path, max_entries=MAX_TRAJ)
        mock_to_metadata.assert_called_once_with((entry,), max_entries=MAX_TRAJ)
        mock_write.assert_awaited_once_with(
            client,
            ["demo"],
            [1],
            task="T_ROB2",
            module="MY_WEB",
            process_types=[0],
            mastership_retries=5,
        )

    @pytest.mark.asyncio
    async def test_empty_store_is_written(
        self,
        client: MagicMock,
        tmp_path: Path,
    ) -> None:
        """An empty local store writes empty robot metadata."""
        mock_write = AsyncMock()

        with patch(f"{_MODULE}.write_store_metadata", mock_write):
            entries = await refresh_store_metadata(client, tmp_path)

        assert entries == ()
        mock_write.assert_awaited_once_with(
            client,
            [],
            [],
            task="T_ROB1",
            module="TRAJCENTER",
            process_types=[],
            mastership_retries=3,
        )

    @pytest.mark.asyncio
    async def test_scan_error_is_propagated(
        self,
        client: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Store scanner errors are propagated before any RWS write."""
        mock_scan = MagicMock(side_effect=FileNotFoundError("missing store"))
        mock_write = AsyncMock()

        with (
            patch(f"{_MODULE}.scan_trajectory_store", mock_scan),
            patch(f"{_MODULE}.write_store_metadata", mock_write),
            pytest.raises(FileNotFoundError, match="missing store"),
        ):
            await refresh_store_metadata(client, tmp_path)

        mock_scan.assert_called_once_with(tmp_path, max_entries=MAX_TRAJ)
        mock_write.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_metadata_conversion_error_is_propagated(
        self,
        client: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Metadata conversion errors are propagated before RWS write."""
        path = _save_trajectory(tmp_path, name="demo")
        entry = _make_entry(path.resolve(), index=1, name="demo")
        mock_scan = MagicMock(return_value=(entry,))
        mock_to_metadata = MagicMock(side_effect=ValueError("bad metadata"))
        mock_write = AsyncMock()

        with (
            patch(f"{_MODULE}.scan_trajectory_store", mock_scan),
            patch(f"{_MODULE}.store_entries_to_metadata", mock_to_metadata),
            patch(f"{_MODULE}.write_store_metadata", mock_write),
            pytest.raises(ValueError, match="bad metadata"),
        ):
            await refresh_store_metadata(client, tmp_path)

        mock_scan.assert_called_once_with(tmp_path, max_entries=MAX_TRAJ)
        mock_to_metadata.assert_called_once_with((entry,), max_entries=MAX_TRAJ)
        mock_write.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_writer_error_is_propagated(
        self,
        client: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Metadata writer errors are propagated."""
        path = _save_trajectory(tmp_path, name="demo")
        entry = _make_entry(path.resolve(), index=1, name="demo")
        mock_scan = MagicMock(return_value=(entry,))
        mock_to_metadata = MagicMock(return_value=(["demo"], [1], [0]))
        mock_write = AsyncMock(side_effect=ValueError("write failed"))

        with (
            patch(f"{_MODULE}.scan_trajectory_store", mock_scan),
            patch(f"{_MODULE}.store_entries_to_metadata", mock_to_metadata),
            patch(f"{_MODULE}.write_store_metadata", mock_write),
            pytest.raises(ValueError, match="write failed"),
        ):
            await refresh_store_metadata(client, tmp_path)

        mock_scan.assert_called_once_with(tmp_path, max_entries=MAX_TRAJ)
        mock_to_metadata.assert_called_once_with((entry,), max_entries=MAX_TRAJ)
        mock_write.assert_awaited_once_with(
            client,
            ["demo"],
            [1],
            task="T_ROB1",
            module="TRAJCENTER",
            process_types=[0],
            mastership_retries=3,
        )
