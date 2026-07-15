# tests/rws/test_reader.py
"""Tests for trajcenter.rws.reader.

All RWS calls are mocked — no HTTP traffic.
Mock target: ``trajcenter.rws.reader.get_variable``
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from trajcenter.rws.reader import (
    read_nb_robtargets,
    read_nb_traj_dispo,
    read_selected_traj_index,
    read_traj_names,
    read_traj_ready,
)

_MODULE = "trajcenter.rws.reader"


@pytest.fixture
def client() -> MagicMock:
    """Bare MagicMock acting as RWSClient."""
    return MagicMock()


# ---------------------------------------------------------------------------
# read_selected_traj_index
# ---------------------------------------------------------------------------


class TestReadSelectedTrajIndex:
    """Tests for read_selected_traj_index()."""

    @pytest.mark.asyncio
    async def test_nominal(self, client: MagicMock) -> None:
        """Returns int from RAPID num string."""
        with patch(f"{_MODULE}.get_variable", AsyncMock(return_value="3")):
            result = await read_selected_traj_index(client)
        assert result == 3

    @pytest.mark.asyncio
    async def test_zero(self, client: MagicMock) -> None:
        """Returns 0 when no trajectory is selected."""
        with patch(f"{_MODULE}.get_variable", AsyncMock(return_value="0")):
            result = await read_selected_traj_index(client)
        assert result == 0

    @pytest.mark.asyncio
    async def test_float_string(self, client: MagicMock) -> None:
        """RAPID num may be returned as '3.0' — must convert to int."""
        with patch(f"{_MODULE}.get_variable", AsyncMock(return_value="3.0")):
            result = await read_selected_traj_index(client)
        assert result == 3

    @pytest.mark.asyncio
    async def test_invalid_value_raises(self, client: MagicMock) -> None:
        """Non-numeric raw value raises ValueError."""
        with patch(f"{_MODULE}.get_variable", AsyncMock(return_value="abc")):
            with pytest.raises(ValueError, match="TrajSelectedIndex"):
                await read_selected_traj_index(client)

    @pytest.mark.asyncio
    async def test_symbol_url_format(self, client: MagicMock) -> None:
        """Symbol URL must follow RAPID/{task}/{module}/{var} format."""
        mock_get = AsyncMock(return_value="1")
        with patch(f"{_MODULE}.get_variable", mock_get):
            await read_selected_traj_index(client, task="T_ROB1", module="TRAJCENTER")
        _, kwargs = mock_get.call_args
        assert kwargs["symbolurl"] == "RAPID/T_ROB1/TRAJCENTER/TrajSelectedIndex"


# ---------------------------------------------------------------------------
# read_traj_ready
# ---------------------------------------------------------------------------


class TestReadTrajReady:
    """Tests for read_traj_ready()."""

    @pytest.mark.asyncio
    async def test_true(self, client: MagicMock) -> None:
        """'TRUE' → True."""
        with patch(f"{_MODULE}.get_variable", AsyncMock(return_value="TRUE")):
            assert await read_traj_ready(client) is True

    @pytest.mark.asyncio
    async def test_false(self, client: MagicMock) -> None:
        """'FALSE' → False."""
        with patch(f"{_MODULE}.get_variable", AsyncMock(return_value="FALSE")):
            assert await read_traj_ready(client) is False

    @pytest.mark.asyncio
    async def test_case_insensitive(self, client: MagicMock) -> None:
        """Parsing must be case-insensitive ('true' → True)."""
        with patch(f"{_MODULE}.get_variable", AsyncMock(return_value="true")):
            assert await read_traj_ready(client) is True

    @pytest.mark.asyncio
    async def test_invalid_raises(self, client: MagicMock) -> None:
        """Any value other than TRUE/FALSE raises ValueError."""
        with patch(f"{_MODULE}.get_variable", AsyncMock(return_value="MAYBE")):
            with pytest.raises(ValueError, match="TrajReady"):
                await read_traj_ready(client)

    @pytest.mark.asyncio
    async def test_whitespace_stripped(self, client: MagicMock) -> None:
        """Leading/trailing whitespace must be stripped before comparison."""
        with patch(f"{_MODULE}.get_variable", AsyncMock(return_value="  FALSE  ")):
            assert await read_traj_ready(client) is False


# ---------------------------------------------------------------------------
# read_nb_robtargets
# ---------------------------------------------------------------------------


class TestReadNbRobtargets:
    """Tests for read_nb_robtargets()."""

    @pytest.mark.asyncio
    async def test_nominal(self, client: MagicMock) -> None:
        """Returns int point count."""
        with patch(f"{_MODULE}.get_variable", AsyncMock(return_value="320")):
            assert await read_nb_robtargets(client) == 320

    @pytest.mark.asyncio
    async def test_float_string(self, client: MagicMock) -> None:
        """'320.0' → 320."""
        with patch(f"{_MODULE}.get_variable", AsyncMock(return_value="320.0")):
            assert await read_nb_robtargets(client) == 320

    @pytest.mark.asyncio
    async def test_invalid_raises(self, client: MagicMock) -> None:
        """Non-numeric value raises ValueError."""
        with patch(f"{_MODULE}.get_variable", AsyncMock(return_value="???")):
            with pytest.raises(ValueError, match="NbRobtargetsTraj"):
                await read_nb_robtargets(client)


# ---------------------------------------------------------------------------
# read_nb_traj_dispo
# ---------------------------------------------------------------------------


class TestReadNbTrajDispo:
    """Tests for read_nb_traj_dispo()."""

    @pytest.mark.asyncio
    async def test_nominal(self, client: MagicMock) -> None:
        """Returns int trajectory count."""
        with patch(f"{_MODULE}.get_variable", AsyncMock(return_value="5")):
            assert await read_nb_traj_dispo(client) == 5

    @pytest.mark.asyncio
    async def test_zero(self, client: MagicMock) -> None:
        """Empty store returns 0."""
        with patch(f"{_MODULE}.get_variable", AsyncMock(return_value="0")):
            assert await read_nb_traj_dispo(client) == 0


# ---------------------------------------------------------------------------
# read_traj_names
# ---------------------------------------------------------------------------


class TestReadTrajNames:
    """Tests for read_traj_names()."""

    @pytest.mark.asyncio
    async def test_nominal_with_count(self, client: MagicMock) -> None:
        """Returns stripped names when count is provided explicitly."""
        mock_get = AsyncMock(side_effect=['"Traj1"', '"Traj2"', '"Traj3"'])
        with patch(f"{_MODULE}.get_variable", mock_get):
            names = await read_traj_names(client, count=3)
        assert names == ["Traj1", "Traj2", "Traj3"]

    @pytest.mark.asyncio
    async def test_reads_nb_traj_dispo_when_count_none(self, client: MagicMock) -> None:
        """When count=None, NbTrajDispo is read first then names are fetched."""
        # First call → NbTrajDispo = 2, then 2 name reads
        mock_get = AsyncMock(side_effect=["2", '"Alpha"', '"Beta"'])
        with patch(f"{_MODULE}.get_variable", mock_get):
            names = await read_traj_names(client)
        assert names == ["Alpha", "Beta"]
        assert mock_get.call_count == 3

    @pytest.mark.asyncio
    async def test_empty_store(self, client: MagicMock) -> None:
        """count=0 returns empty list without any RWS call."""
        mock_get = AsyncMock()
        with patch(f"{_MODULE}.get_variable", mock_get):
            names = await read_traj_names(client, count=0)
        assert names == []
        mock_get.assert_not_called()

    @pytest.mark.asyncio
    async def test_strips_rapid_quotes(self, client: MagicMock) -> None:
        """RAPID string quotes and whitespace are stripped."""
        mock_get = AsyncMock(return_value='  "  Traj_A  "  ')
        with patch(f"{_MODULE}.get_variable", mock_get):
            names = await read_traj_names(client, count=1)
        assert names == ["  Traj_A  "]  # inner spaces preserved, outer stripped

    @pytest.mark.asyncio
    async def test_count_exceeds_max_raises(self, client: MagicMock) -> None:
        """count > MAX_TRAJ raises ValueError without any RWS call."""
        from trajcenter.rws.writer import MAX_TRAJ

        # Pas de mock get_variable — le raise doit se produire avant
        with pytest.raises(ValueError, match="MAX_TRAJ"):
            await read_traj_names(client, count=MAX_TRAJ + 1)

    @pytest.mark.asyncio
    async def test_symbol_url_array_format(self, client: MagicMock) -> None:
        """Array element URL must use RAPID/[i] notation."""
        mock_get = AsyncMock(return_value='"T1"')
        with patch(f"{_MODULE}.get_variable", mock_get):
            await read_traj_names(client, count=1, task="T_ROB1", module="TRAJCENTER")
        _, kwargs = mock_get.call_args
        assert kwargs["symbolurl"] == "RAPID/T_ROB1/TRAJCENTER/NomsTraj/[1]"
