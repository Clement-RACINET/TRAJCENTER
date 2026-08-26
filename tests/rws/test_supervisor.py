#!/usr/bin/env python3
# tests/rws/test_supervisor.py
"""Unit tests for :mod:`trajcenter.rws.supervisor`.

Author: Clement RACINET

The ABB WebSocket subscription layer is mocked. Tests validate only the local
supervisor orchestration and event dispatching logic.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from trajcenter.rws.models import TrajectoryStoreEntry
from trajcenter.rws.supervisor import (
    RWSSupervisorConfig,
    RWSSupervisorState,
    build_trajcenter_subscription_resources,
    handle_supervisor_event,
    run_rws_subscription_supervisor,
)

_MODULE = "trajcenter.rws.supervisor"


@pytest.fixture
def client() -> MagicMock:
    """Return a mock RWS client.

    ABB Route:
        N/A — test fixture.

    ABB Constraints:
        No ABB controller access is performed.

    Args:
        None.

    Returns:
        Mock RWS client.


    Example:
        ::

            client = MagicMock()
    """
    return MagicMock()


@pytest.fixture
def config(tmp_path: Path) -> RWSSupervisorConfig:
    """Return a default supervisor configuration.

    ABB Route:
        N/A — test fixture.

    ABB Constraints:
        Uses the default TrajCenter task and module.

    Args:
        tmp_path: Pytest temporary directory.

    Returns:
        Supervisor configuration.


    Example:
        ::

            config = RWSSupervisorConfig(store_root=tmp_path)
    """
    return RWSSupervisorConfig(store_root=tmp_path)


def _entry(tmp_path: Path) -> TrajectoryStoreEntry:
    """Build one local trajectory store entry.

    ABB Route:
        N/A — local test helper.

    ABB Constraints:
        ``index`` is RAPID base-1.

    Args:
        tmp_path: Pytest temporary directory.

    Returns:
        Store entry.


    Example:
        ::

            entry = _entry(tmp_path)
    """
    return TrajectoryStoreEntry(
        index=1,
        path=tmp_path / "demo.trajcenter",
        name="demo",
        point_count=1,
        process_type=0,
    )


class _FakeEventStream:
    """Async context-compatible event stream helper for supervisor tests."""

    def __init__(self, events: tuple[tuple[str, str], ...]) -> None:
        """Initialize fake events.

        ABB Route:
            N/A — test helper.

        ABB Constraints:
            Events mimic ``watch_resources`` plain ``(name, value)`` tuples.

        Args:
            events: Events yielded by the async iterator.

        Returns:
            None.


        Example:
            ::

                stream = _FakeEventStream((("refreshMetaRequest", "TRUE"),))
        """
        self._events = events
        self.closed = False

    def __aiter__(self) -> _FakeEventStream:
        """Return the async iterator.

        ABB Route:
            N/A — test helper.

        ABB Constraints:
            None.


        Returns:
            Async iterator.


        Example:
            ::

                async for event in stream:
                    ...
        """
        self._index = 0
        return self

    async def __anext__(self) -> tuple[str, str]:
        """Return the next fake event.

        ABB Route:
            N/A — test helper.

        ABB Constraints:
            None.


        Returns:
            Next event tuple.

        Raises:
            StopAsyncIteration: When all events have been consumed.

        Example:
            ::

                event = await stream.__anext__()
        """
        if self._index >= len(self._events):
            raise StopAsyncIteration

        event = self._events[self._index]
        self._index += 1
        return event

    async def aclose(self) -> None:
        """Mark the stream as closed.

        ABB Route:
            N/A — test helper.

        ABB Constraints:
            Mimics async generator cleanup used by ``contextlib.aclosing``.


        Returns:
            None.


        Example:
            ::

                await stream.aclose()
        """
        self.closed = True


class TestBuildTrajcenterSubscriptionResources:
    """Tests for subscription resource construction."""

    def test_builds_expected_resources(self, tmp_path: Path) -> None:
        """Resources target the two TrajCenter RAPID request flags."""
        cfg = RWSSupervisorConfig(
            store_root=tmp_path,
            task="T_ROB2",
            module="MY_WEB",
            refresh_priority="1",
            transfer_priority="2",
        )

        resources = build_trajcenter_subscription_resources(cfg)

        assert len(resources) == 2
        assert resources[0].name == "refreshMetaRequest"
        assert resources[0].priority == "1"
        assert "T_ROB2" in resources[0].resource_uri
        assert "MY_WEB" in resources[0].resource_uri
        assert "refreshMetaRequest" in resources[0].resource_uri

        assert resources[1].name == "sendTrajRequest"
        assert resources[1].priority == "2"
        assert "sendTrajRequest" in resources[1].resource_uri


class TestHandleSupervisorEvent:
    """Tests for single event dispatching."""

    @pytest.mark.asyncio
    async def test_false_event_is_ignored(
        self,
        client: MagicMock,
        config: RWSSupervisorConfig,
    ) -> None:
        """FALSE events do not trigger service calls."""
        state = RWSSupervisorState()

        with patch(f"{_MODULE}.refresh_store_metadata", AsyncMock()) as refresh_mock:
            await handle_supervisor_event(
                client,
                config,
                state,
                "refreshMetaRequest",
                "FALSE",
            )

        refresh_mock.assert_not_awaited()
        assert state.refresh_count == 0

    @pytest.mark.asyncio
    async def test_refresh_event_updates_state(
        self,
        client: MagicMock,
        config: RWSSupervisorConfig,
        tmp_path: Path,
    ) -> None:
        """A TRUE refresh event scans/writes metadata and stores entries."""
        entry = _entry(tmp_path)
        refresh_mock = AsyncMock(return_value=(entry,))
        state = RWSSupervisorState()

        with patch(f"{_MODULE}.refresh_store_metadata", refresh_mock):
            await handle_supervisor_event(
                client,
                config,
                state,
                "refreshMetaRequest",
                "TRUE",
            )

        refresh_mock.assert_awaited_once_with(
            client,
            config.store_root,
            task="T_ROB1",
            module="TRAJCENTER",
            mastership_retries=3,
        )
        assert state.entries == (entry,)
        assert state.refresh_count == 1

    @pytest.mark.asyncio
    async def test_transfer_event_uses_current_entries(
        self,
        client: MagicMock,
        config: RWSSupervisorConfig,
        tmp_path: Path,
    ) -> None:
        """A TRUE transfer event transfers the selected trajectory."""
        entry = _entry(tmp_path)
        transfer_mock = AsyncMock()
        state = RWSSupervisorState(entries=(entry,))

        with patch(f"{_MODULE}.transfer_selected_trajectory", transfer_mock):
            await handle_supervisor_event(
                client,
                config,
                state,
                "sendTrajRequest",
                "TRUE",
            )

        transfer_mock.assert_awaited_once_with(
            client,
            (entry,),
            task="T_ROB1",
            module="TRAJCENTER",
            mastership_retries=3,
        )
        assert state.transfer_count == 1

    @pytest.mark.asyncio
    async def test_transfer_before_refresh_raises(
        self,
        client: MagicMock,
        config: RWSSupervisorConfig,
    ) -> None:
        """A transfer request without known entries is rejected."""
        state = RWSSupervisorState()

        with pytest.raises(ValueError, match="before store metadata"):
            await handle_supervisor_event(
                client,
                config,
                state,
                "sendTrajRequest",
                "TRUE",
            )

    @pytest.mark.asyncio
    async def test_unknown_event_is_ignored(
        self,
        client: MagicMock,
        config: RWSSupervisorConfig,
    ) -> None:
        """Unknown subscription resources are ignored."""
        state = RWSSupervisorState()

        await handle_supervisor_event(client, config, state, "other", "TRUE")

        assert state.refresh_count == 0
        assert state.transfer_count == 0


class TestRunRwsSubscriptionSupervisor:
    """Tests for the subscription supervisor runner."""

    @pytest.mark.asyncio
    async def test_runs_events_and_closes_stream(
        self,
        client: MagicMock,
        config: RWSSupervisorConfig,
        tmp_path: Path,
    ) -> None:
        """The supervisor consumes subscription events and closes the stream."""
        entry = _entry(tmp_path)
        stream = _FakeEventStream(
            (
                ("refreshMetaRequest", "TRUE"),
                ("sendTrajRequest", "TRUE"),
            )
        )

        refresh_mock = AsyncMock(return_value=(entry,))
        transfer_mock = AsyncMock()

        with patch(f"{_MODULE}.watch_resources", MagicMock(return_value=stream)):
            with patch(f"{_MODULE}.refresh_store_metadata", refresh_mock):
                with patch(f"{_MODULE}.transfer_selected_trajectory", transfer_mock):
                    state = await run_rws_subscription_supervisor(client, config)

        assert stream.closed
        assert state.entries == (entry,)
        assert state.refresh_count == 1
        assert state.transfer_count == 1
        refresh_mock.assert_awaited_once()
        transfer_mock.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_stop_event_set_after_first_event(
        self,
        client: MagicMock,
        config: RWSSupervisorConfig,
        tmp_path: Path,
    ) -> None:
        """A stop event set by a service call stops the supervisor."""
        entry = _entry(tmp_path)
        stop_event = asyncio.Event()
        stream = _FakeEventStream(
            (
                ("refreshMetaRequest", "TRUE"),
                ("sendTrajRequest", "TRUE"),
            )
        )

        async def refresh_side_effect(*_: object, **__: object):
            stop_event.set()
            return (entry,)

        refresh_mock = AsyncMock(side_effect=refresh_side_effect)
        transfer_mock = AsyncMock()

        with patch(f"{_MODULE}.watch_resources", MagicMock(return_value=stream)):
            with patch(f"{_MODULE}.refresh_store_metadata", refresh_mock):
                with patch(f"{_MODULE}.transfer_selected_trajectory", transfer_mock):
                    state = await run_rws_subscription_supervisor(
                        client,
                        config,
                        stop_event=stop_event,
                    )

        assert stream.closed
        assert state.refresh_count == 1
        assert state.transfer_count == 0
        transfer_mock.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_existing_state_is_reused(
        self,
        client: MagicMock,
        config: RWSSupervisorConfig,
        tmp_path: Path,
    ) -> None:
        """An existing state can be reused by the supervisor."""
        entry = _entry(tmp_path)
        initial_state = RWSSupervisorState(entries=(entry,))
        stream = _FakeEventStream((("sendTrajRequest", "TRUE"),))
        transfer_mock = AsyncMock()

        with patch(f"{_MODULE}.watch_resources", MagicMock(return_value=stream)):
            with patch(f"{_MODULE}.transfer_selected_trajectory", transfer_mock):
                state = await run_rws_subscription_supervisor(
                    client,
                    config,
                    state=initial_state,
                )

        assert state is initial_state
        assert state.transfer_count == 1
        transfer_mock.assert_awaited_once()
