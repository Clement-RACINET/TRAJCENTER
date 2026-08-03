#!/usr/bin/env python3
# tests/rws/test_reader.py
"""Tests for :mod:`trajcenter.rws.reader`.

Author: Clement RACINET

All RWS calls are mocked — no HTTP traffic.
Mock target: ``trajcenter.rws.reader.get_variable``.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from trajcenter.rws.constants import MAX_TRAJ
from trajcenter.rws.models import RobotDefaults
from trajcenter.rws.reader import (
    read_last_error,
    read_last_error_code,
    read_nb_robtargets,
    read_nb_traj_dispo,
    read_refresh_meta_request,
    read_robot_defaults,
    read_selected_traj_index,
    read_send_traj_request,
    read_traj_names,
    read_traj_ready,
    read_transfer_error,
    read_transfer_progress,
)

_MODULE = "trajcenter.rws.reader"


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
        Mock client.

    Raises:
        None.

    Example:
        ```python
        client = MagicMock()
        ```
    """
    return MagicMock()


class TestReadSelectedTrajIndex:
    """Tests for :func:`trajcenter.rws.reader.read_selected_traj_index`."""

    @pytest.mark.asyncio
    async def test_nominal(self, client: MagicMock) -> None:
        """Returns an ``int`` parsed from a RAPID ``num`` string."""
        with patch(f"{_MODULE}.get_variable", AsyncMock(return_value="3")):
            result = await read_selected_traj_index(client)
        assert result == 3

    @pytest.mark.asyncio
    async def test_zero(self, client: MagicMock) -> None:
        """Returns ``0`` when no trajectory is selected."""
        with patch(f"{_MODULE}.get_variable", AsyncMock(return_value="0")):
            result = await read_selected_traj_index(client)
        assert result == 0

    @pytest.mark.asyncio
    async def test_float_string(self, client: MagicMock) -> None:
        """A RAPID ``num`` may be returned as ``'3.0'``."""
        with patch(f"{_MODULE}.get_variable", AsyncMock(return_value="3.0")):
            result = await read_selected_traj_index(client)
        assert result == 3

    @pytest.mark.asyncio
    async def test_invalid_value_raises(self, client: MagicMock) -> None:
        """A non-numeric raw value raises ``ValueError``."""
        with patch(f"{_MODULE}.get_variable", AsyncMock(return_value="abc")):
            with pytest.raises(ValueError, match="selectedTrajIndex"):
                await read_selected_traj_index(client)

    @pytest.mark.asyncio
    async def test_symbol_url_format(self, client: MagicMock) -> None:
        """The symbol URL uses the v2 WebServices module and variable name."""
        mock_get = AsyncMock(return_value="1")
        with patch(f"{_MODULE}.get_variable", mock_get):
            await read_selected_traj_index(client)
        _, kwargs = mock_get.call_args
        assert (
            kwargs["symbolurl"]
            == "RAPID/T_ROB1/TRAJCENTER_WebServices/selectedTrajIndex"
        )


class TestBoolReaders:
    """Tests for boolean RWS readers."""

    @pytest.mark.asyncio
    async def test_read_traj_ready_true(self, client: MagicMock) -> None:
        """``trajReady=TRUE`` is parsed as ``True``."""
        with patch(f"{_MODULE}.get_variable", AsyncMock(return_value="TRUE")):
            assert await read_traj_ready(client) is True

    @pytest.mark.asyncio
    async def test_read_traj_ready_false(self, client: MagicMock) -> None:
        """``trajReady=FALSE`` is parsed as ``False``."""
        with patch(f"{_MODULE}.get_variable", AsyncMock(return_value="FALSE")):
            assert await read_traj_ready(client) is False

    @pytest.mark.asyncio
    async def test_case_insensitive(self, client: MagicMock) -> None:
        """Boolean parsing is case-insensitive."""
        with patch(f"{_MODULE}.get_variable", AsyncMock(return_value="true")):
            assert await read_traj_ready(client) is True

    @pytest.mark.asyncio
    async def test_invalid_bool_raises(self, client: MagicMock) -> None:
        """Invalid RAPID bool strings raise ``ValueError``."""
        with patch(f"{_MODULE}.get_variable", AsyncMock(return_value="MAYBE")):
            with pytest.raises(ValueError, match="trajReady"):
                await read_traj_ready(client)

    @pytest.mark.asyncio
    async def test_send_traj_request(self, client: MagicMock) -> None:
        """``sendTrajRequest`` is read from the v2 variable."""
        mock_get = AsyncMock(return_value="TRUE")
        with patch(f"{_MODULE}.get_variable", mock_get):
            assert await read_send_traj_request(client) is True
        assert (
            mock_get.call_args.kwargs["symbolurl"]
            == "RAPID/T_ROB1/TRAJCENTER_WebServices/sendTrajRequest"
        )

    @pytest.mark.asyncio
    async def test_refresh_meta_request(self, client: MagicMock) -> None:
        """``refreshMetaRequest`` is read from the v2 variable."""
        mock_get = AsyncMock(return_value="FALSE")
        with patch(f"{_MODULE}.get_variable", mock_get):
            assert await read_refresh_meta_request(client) is False
        assert (
            mock_get.call_args.kwargs["symbolurl"]
            == "RAPID/T_ROB1/TRAJCENTER_WebServices/refreshMetaRequest"
        )

    @pytest.mark.asyncio
    async def test_transfer_error(self, client: MagicMock) -> None:
        """``transferError`` is parsed as bool."""
        mock_get = AsyncMock(return_value="TRUE")
        with patch(f"{_MODULE}.get_variable", mock_get):
            assert await read_transfer_error(client) is True
        assert (
            mock_get.call_args.kwargs["symbolurl"]
            == "RAPID/T_ROB1/TRAJCENTER_WebServices/transferError"
        )


class TestStatusReaders:
    """Tests for status scalar readers."""

    @pytest.mark.asyncio
    async def test_last_error_code(self, client: MagicMock) -> None:
        """``lastErrorCode`` is parsed as integer."""
        mock_get = AsyncMock(return_value="200002")
        with patch(f"{_MODULE}.get_variable", mock_get):
            assert await read_last_error_code(client) == 200002

    @pytest.mark.asyncio
    async def test_last_error(self, client: MagicMock) -> None:
        """``lastError`` RAPID string quotes are stripped."""
        mock_get = AsyncMock(return_value='"No error"')
        with patch(f"{_MODULE}.get_variable", mock_get):
            assert await read_last_error(client) == "No error"

    @pytest.mark.asyncio
    async def test_last_error_unquoted(self, client: MagicMock) -> None:
        """Unquoted strings are returned stripped."""
        mock_get = AsyncMock(return_value="  No error  ")
        with patch(f"{_MODULE}.get_variable", mock_get):
            assert await read_last_error(client) == "No error"

    @pytest.mark.asyncio
    async def test_transfer_progress(self, client: MagicMock) -> None:
        """``transferProgress`` is parsed as integer."""
        mock_get = AsyncMock(return_value="75.0")
        with patch(f"{_MODULE}.get_variable", mock_get):
            assert await read_transfer_progress(client) == 75


class TestReadNbRobtargets:
    """Tests for :func:`trajcenter.rws.reader.read_nb_robtargets`."""

    @pytest.mark.asyncio
    async def test_nominal(self, client: MagicMock) -> None:
        """Reads ``nbLoadedTrajPoints`` as an ``int``."""
        with patch(f"{_MODULE}.get_variable", AsyncMock(return_value="320")):
            assert await read_nb_robtargets(client) == 320

    @pytest.mark.asyncio
    async def test_float_string(self, client: MagicMock) -> None:
        """``'320.0'`` is converted to ``320``."""
        with patch(f"{_MODULE}.get_variable", AsyncMock(return_value="320.0")):
            assert await read_nb_robtargets(client) == 320

    @pytest.mark.asyncio
    async def test_invalid_raises(self, client: MagicMock) -> None:
        """A non-numeric value raises ``ValueError``."""
        with patch(f"{_MODULE}.get_variable", AsyncMock(return_value="???")):
            with pytest.raises(ValueError, match="nbLoadedTrajPoints"):
                await read_nb_robtargets(client)

    @pytest.mark.asyncio
    async def test_symbol_url(self, client: MagicMock) -> None:
        """The v2 point count variable is used."""
        mock_get = AsyncMock(return_value="1")
        with patch(f"{_MODULE}.get_variable", mock_get):
            await read_nb_robtargets(client)
        assert (
            mock_get.call_args.kwargs["symbolurl"]
            == "RAPID/T_ROB1/TRAJCENTER_WebServices/nbLoadedTrajPoints"
        )


class TestReadNbTrajDispo:
    """Tests for :func:`trajcenter.rws.reader.read_nb_traj_dispo`."""

    @pytest.mark.asyncio
    async def test_nominal(self, client: MagicMock) -> None:
        """Reads ``nbTrajAvailable`` as an ``int``."""
        with patch(f"{_MODULE}.get_variable", AsyncMock(return_value="5")):
            assert await read_nb_traj_dispo(client) == 5

    @pytest.mark.asyncio
    async def test_zero(self, client: MagicMock) -> None:
        """An empty metadata list returns ``0``."""
        with patch(f"{_MODULE}.get_variable", AsyncMock(return_value="0")):
            assert await read_nb_traj_dispo(client) == 0

    @pytest.mark.asyncio
    async def test_symbol_url(self, client: MagicMock) -> None:
        """The v2 metadata count variable is used."""
        mock_get = AsyncMock(return_value="1")
        with patch(f"{_MODULE}.get_variable", mock_get):
            await read_nb_traj_dispo(client)
        assert (
            mock_get.call_args.kwargs["symbolurl"]
            == "RAPID/T_ROB1/TRAJCENTER_WebServices/nbTrajAvailable"
        )


class TestReadTrajNames:
    """Tests for :func:`trajcenter.rws.reader.read_traj_names`."""

    @pytest.mark.asyncio
    async def test_nominal_with_count(self, client: MagicMock) -> None:
        """Returns names parsed from ``trajectories{i}`` records."""
        mock_get = AsyncMock(
            side_effect=[
                '["Traj1",320,0]',
                '["Traj2",150,1]',
                '["Traj3",42,0]',
            ]
        )
        with patch(f"{_MODULE}.get_variable", mock_get):
            names = await read_traj_names(client, count=3)
        assert names == ["Traj1", "Traj2", "Traj3"]

    @pytest.mark.asyncio
    async def test_reads_nb_traj_dispo_when_count_none(self, client: MagicMock) -> None:
        """When ``count=None``, ``nbTrajAvailable`` is read first."""
        mock_get = AsyncMock(
            side_effect=[
                "2",
                '["Alpha",10,0]',
                '["Beta",20,0]',
            ]
        )
        with patch(f"{_MODULE}.get_variable", mock_get):
            names = await read_traj_names(client)
        assert names == ["Alpha", "Beta"]
        assert mock_get.call_count == 3

    @pytest.mark.asyncio
    async def test_empty_store(self, client: MagicMock) -> None:
        """``count=0`` returns an empty list without any RWS call."""
        mock_get = AsyncMock()
        with patch(f"{_MODULE}.get_variable", mock_get):
            names = await read_traj_names(client, count=0)
        assert names == []
        mock_get.assert_not_called()

    @pytest.mark.asyncio
    async def test_count_exceeds_max_raises(self, client: MagicMock) -> None:
        """``count > MAX_TRAJ`` raises ``ValueError`` without any RWS call."""
        with pytest.raises(ValueError, match="MAX_TRAJ"):
            await read_traj_names(client, count=MAX_TRAJ + 1)

    @pytest.mark.asyncio
    async def test_symbol_url_array_format(self, client: MagicMock) -> None:
        """Array element URL uses encoded RAPID braces."""
        mock_get = AsyncMock(return_value='["T1",1,0]')
        with patch(f"{_MODULE}.get_variable", mock_get):
            await read_traj_names(client, count=1)
        _, kwargs = mock_get.call_args
        assert (
            kwargs["symbolurl"]
            == "RAPID/T_ROB1/TRAJCENTER_WebServices/trajectories%7B1%7D"
        )

    @pytest.mark.asyncio
    async def test_invalid_record_raises(self, client: MagicMock) -> None:
        """A malformed metadata record raises ``ValueError``."""
        mock_get = AsyncMock(return_value="[INVALID]")
        with patch(f"{_MODULE}.get_variable", mock_get):
            with pytest.raises(ValueError, match="metadata"):
                await read_traj_names(client, count=1)


class TestReadRobotDefaults:
    """Tests for :func:`trajcenter.rws.reader.read_robot_defaults`."""

    @pytest.mark.asyncio
    async def test_all_defaults_enabled(self, client: MagicMock) -> None:
        """All enabled defaults are parsed into ``RobotDefaults``."""
        mock_get = AsyncMock(
            side_effect=[
                "TRUE",
                "500",
                "TRUE",
                "10",
                "TRUE",
                '"tool0"',
                "TRUE",
                '"wobj0"',
                "0",
                "TRUE",
            ]
        )
        with patch(f"{_MODULE}.get_variable", mock_get):
            defaults = await read_robot_defaults(client)

        assert isinstance(defaults, RobotDefaults)
        assert defaults.has_tcp_speed is True
        assert defaults.tcp_speed == 500.0
        assert defaults.has_zone_type is True
        assert defaults.zone_type == 10
        assert defaults.has_tool_name is True
        assert defaults.tool_name == "tool0"
        assert defaults.has_wobj_name is True
        assert defaults.wobj_name == "wobj0"
        assert defaults.move_type == 0
        assert defaults.read_confs is True

    @pytest.mark.asyncio
    async def test_disabled_optional_defaults_return_none(
        self,
        client: MagicMock,
    ) -> None:
        """Disabled default flags produce ``None`` values."""
        mock_get = AsyncMock(
            side_effect=[
                "FALSE",
                "0",
                "FALSE",
                "255",
                "FALSE",
                '""',
                "FALSE",
                '""',
                "1",
                "FALSE",
            ]
        )
        with patch(f"{_MODULE}.get_variable", mock_get):
            defaults = await read_robot_defaults(client)

        assert defaults.tcp_speed is None
        assert defaults.zone_type is None
        assert defaults.tool_name is None
        assert defaults.wobj_name is None
        assert defaults.move_type == 1
        assert defaults.read_confs is False

    @pytest.mark.asyncio
    async def test_reads_expected_symbols_in_order(self, client: MagicMock) -> None:
        """Defaults are read from the expected v2 variables."""
        mock_get = AsyncMock(
            side_effect=[
                "TRUE",
                "500",
                "TRUE",
                "10",
                "TRUE",
                '"tool0"',
                "TRUE",
                '"wobj0"',
                "0",
                "TRUE",
            ]
        )
        with patch(f"{_MODULE}.get_variable", mock_get):
            await read_robot_defaults(client)

        symbols = [call.kwargs["symbolurl"] for call in mock_get.call_args_list]
        assert symbols == [
            "RAPID/T_ROB1/TRAJCENTER_WebServices/hasDefaultTcpSpeed",
            "RAPID/T_ROB1/TRAJCENTER_WebServices/defaultTcpSpeed",
            "RAPID/T_ROB1/TRAJCENTER_WebServices/hasDefaultZoneType",
            "RAPID/T_ROB1/TRAJCENTER_WebServices/defaultZoneType",
            "RAPID/T_ROB1/TRAJCENTER_WebServices/hasDefaultToolName",
            "RAPID/T_ROB1/TRAJCENTER_WebServices/defaultToolName",
            "RAPID/T_ROB1/TRAJCENTER_WebServices/hasDefaultWobjName",
            "RAPID/T_ROB1/TRAJCENTER_WebServices/defaultWobjName",
            "RAPID/T_ROB1/TRAJCENTER_WebServices/defaultMoveType",
            "RAPID/T_ROB1/TRAJCENTER_WebServices/defaultReadConfs",
        ]

    @pytest.mark.asyncio
    async def test_invalid_default_bool_raises(self, client: MagicMock) -> None:
        """Invalid default bool values raise ``ValueError``."""
        mock_get = AsyncMock(return_value="MAYBE")
        with patch(f"{_MODULE}.get_variable", mock_get):
            with pytest.raises(ValueError, match="hasDefaultTcpSpeed"):
                await read_robot_defaults(client)
