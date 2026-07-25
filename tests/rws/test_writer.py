#!/usr/bin/env python3
# tests/rws/test_writer.py
"""Unit tests for :mod:`trajcenter.rws.writer`.

> **Author**: Clément RACINET

All RWS calls are mocked via ``unittest.mock.AsyncMock``.
No HTTP traffic is made.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest

from abb_rws_client_python_rw6 import MastershipDenied, RobTarget
from trajcenter.rws.writer import (
    MAX_TRAJ,
    STATUS_METADATA_REFRESHED,
    _eax_presence,
    _fmt_bool,
    _fmt_num,
    _fmt_string,
    _fmt_traj_meta_record,
    _retry_mastership,
    _row_to_robtarget,
    write_store_metadata,
    write_trajectory,
)

_MODULE = "trajcenter.rws.writer"


@pytest.fixture
def client() -> MagicMock:
    """Return a bare ``MagicMock`` acting as ``RWSClient``.

    ABB Route:
        N/A — test fixture.

    ABB Constraints:
        No controller access is performed.

    Returns:
        Mock client.

    Example:
        ::

            client = MagicMock()
    """
    return MagicMock()


def _make_df(n: int = 2, with_eax_a: bool = False) -> pd.DataFrame:
    """Build a minimal valid v2 points DataFrame.

    ABB Route:
        N/A — test helper.

    ABB Constraints:
        No controller access is performed.

    Args:
        n: Number of rows to generate.
        with_eax_a: Whether to add an active ``eax_a`` column.

    Returns:
        Points DataFrame.

    Example:
        ::

            df = _make_df(n=2)
    """
    data: dict[str, list[object]] = {
        "x": [float(i * 100) for i in range(n)],
        "y": [0.0] * n,
        "z": [500.0] * n,
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
    if with_eax_a:
        data["eax_a"] = [100.0] * n
    return pd.DataFrame(data)


class TestFormatHelpers:
    """Tests for RAPID value format helper functions."""

    def test_fmt_num_integer(self) -> None:
        """An integer value is formatted as a plain string."""
        assert _fmt_num(42) == "42"

    def test_fmt_num_float_integer(self) -> None:
        """A float with no fractional part is formatted without decimal."""
        assert _fmt_num(42.0) == "42"

    def test_fmt_num_float(self) -> None:
        """A float with a fractional part is formatted with decimals."""
        assert _fmt_num(3.14) == "3.14"

    def test_fmt_bool_true(self) -> None:
        """``True`` is formatted as ``TRUE``."""
        assert _fmt_bool(True) == "TRUE"

    def test_fmt_bool_false(self) -> None:
        """``False`` is formatted as ``FALSE``."""
        assert _fmt_bool(False) == "FALSE"

    def test_fmt_string_simple(self) -> None:
        """A non-empty string is wrapped in RAPID double quotes."""
        assert _fmt_string("Tool_formage") == '"Tool_formage"'

    def test_fmt_string_empty(self) -> None:
        """An empty string is formatted as an empty RAPID string."""
        assert _fmt_string("") == '""'

    def test_fmt_string_escapes_quotes(self) -> None:
        """Embedded quotes are escaped."""
        assert _fmt_string('A"B') == '"A\\"B"'

    def test_fmt_traj_meta_record_default_process(self) -> None:
        """A metadata record defaults to process type ``0``."""
        assert _fmt_traj_meta_record("TrajA", 100) == '["TrajA",100,0]'

    def test_fmt_traj_meta_record_custom_process(self) -> None:
        """A metadata record accepts a custom process type."""
        assert _fmt_traj_meta_record("TrajA", 100, 2) == '["TrajA",100,2]'


class TestEaxPresence:
    """Tests for :func:`trajcenter.rws.writer._eax_presence`."""

    def test_no_eax_columns(self) -> None:
        """A DataFrame with no ``eax_*`` columns returns all ``False``."""
        df = _make_df()
        assert _eax_presence(df) == (False, False, False, False, False, False)

    def test_eax_a_only(self) -> None:
        """Only ``eax_a`` present returns ``(True, False, …)``."""
        df = _make_df(with_eax_a=True)
        assert _eax_presence(df) == (True, False, False, False, False, False)

    def test_all_eax_columns(self) -> None:
        """All six ``eax_*`` columns present returns all ``True``."""
        df = _make_df()
        for col in ("eax_a", "eax_b", "eax_c", "eax_d", "eax_e", "eax_f"):
            df[col] = 0.0
        assert _eax_presence(df) == (True, True, True, True, True, True)


class TestRowToRobtarget:
    """Tests for :func:`trajcenter.rws.writer._row_to_robtarget`."""

    def test_nominal_no_eax(self) -> None:
        """All external axes inactive produce ``9e9`` sentinel values."""
        row = pd.Series(
            {
                "x": 100.0,
                "y": 200.0,
                "z": 300.0,
                "q1": 1.0,
                "q2": 0.0,
                "q3": 0.0,
                "q4": 0.0,
                "cf1": 0,
                "cf4": 0,
                "cf6": 0,
                "cfx": 0,
            }
        )
        rt = _row_to_robtarget(row, (False,) * 6)
        assert isinstance(rt, RobTarget)
        assert rt.x == 100.0
        assert rt.y == 200.0
        assert rt.z == 300.0
        assert rt.qw == 1.0
        assert rt.eax == [9e9] * 6

    def test_quaternion_mapping(self) -> None:
        """``q1`` maps to ``qw`` and ``q3`` maps to ``qy``."""
        row = pd.Series(
            {
                "x": 0.0,
                "y": 0.0,
                "z": 0.0,
                "q1": 0.707,
                "q2": 0.0,
                "q3": 0.707,
                "q4": 0.0,
                "cf1": 0,
                "cf4": 0,
                "cf6": 0,
                "cfx": 0,
            }
        )
        rt = _row_to_robtarget(row, (False,) * 6)
        assert rt.qw == pytest.approx(0.707)
        assert rt.qy == pytest.approx(0.707)

    def test_eax_a_active(self) -> None:
        """Active ``eax_a`` is read from the row."""
        row = pd.Series(
            {
                "x": 0.0,
                "y": 0.0,
                "z": 0.0,
                "q1": 1.0,
                "q2": 0.0,
                "q3": 0.0,
                "q4": 0.0,
                "cf1": 0,
                "cf4": 0,
                "cf6": 0,
                "cfx": 0,
                "eax_a": 250.0,
            }
        )
        rt = _row_to_robtarget(row, (True, False, False, False, False, False))
        assert rt.eax[0] == 250.0
        assert rt.eax[1:] == [9e9] * 5

    def test_nan_eax_is_inactive(self) -> None:
        """NaN external axis values are serialized as inactive ``9e9``."""
        row = pd.Series(
            {
                "x": 0.0,
                "y": 0.0,
                "z": 0.0,
                "q1": 1.0,
                "q2": 0.0,
                "q3": 0.0,
                "q4": 0.0,
                "cf1": 0,
                "cf4": 0,
                "cf6": 0,
                "cfx": 0,
                "eax_a": float("nan"),
            }
        )
        rt = _row_to_robtarget(row, (True, False, False, False, False, False))
        assert rt.eax == [9e9] * 6


class TestWriteStoreMetadata:
    """Tests for :func:`trajcenter.rws.writer.write_store_metadata`."""

    @pytest.mark.asyncio
    async def test_nominal_single_mastership_call(self, client: MagicMock) -> None:
        """Metadata is written through a single batched mastership call."""
        mock_set = AsyncMock()
        with patch(f"{_MODULE}.set_variables_with_mastership", mock_set):
            await write_store_metadata(
                client,
                names=["Traj1", "Traj2"],
                point_counts=[320, 150],
            )

        mock_set.assert_awaited_once()
        values = mock_set.call_args.kwargs["values"]
        assert len(values) == 1 + MAX_TRAJ + 5

    @pytest.mark.asyncio
    async def test_nb_traj_available_value(self, client: MagicMock) -> None:
        """``nbTrajAvailable`` receives the number of trajectories."""
        mock_set = AsyncMock()
        with patch(f"{_MODULE}.set_variables_with_mastership", mock_set):
            await write_store_metadata(
                client,
                names=["A", "B", "C"],
                point_counts=[10, 20, 30],
            )

        values = mock_set.call_args.kwargs["values"]
        assert values["RAPID/T_ROB1/TRAJCENTER_WebServices/nbTrajAvailable"] == "3"

    @pytest.mark.asyncio
    async def test_trajectories_records_padded(self, client: MagicMock) -> None:
        """Trajectory records are padded to ``MAX_TRAJ`` entries."""
        mock_set = AsyncMock()
        with patch(f"{_MODULE}.set_variables_with_mastership", mock_set):
            await write_store_metadata(client, names=["OnlyOne"], point_counts=[100])

        values = mock_set.call_args.kwargs["values"]
        assert (
            values["RAPID/T_ROB1/TRAJCENTER_WebServices/trajectories%7B1%7D"]
            == '["OnlyOne",100,0]'
        )
        assert (
            values["RAPID/T_ROB1/TRAJCENTER_WebServices/trajectories%7B2%7D"]
            == '["",0,0]'
        )
        assert (
            values[f"RAPID/T_ROB1/TRAJCENTER_WebServices/trajectories%7B{MAX_TRAJ}%7D"]
            == '["",0,0]'
        )

    @pytest.mark.asyncio
    async def test_process_types_written(self, client: MagicMock) -> None:
        """Optional process types are written into metadata records."""
        mock_set = AsyncMock()
        with patch(f"{_MODULE}.set_variables_with_mastership", mock_set):
            await write_store_metadata(
                client,
                names=["A", "B"],
                point_counts=[10, 20],
                process_types=[1, 2],
            )

        values = mock_set.call_args.kwargs["values"]
        assert (
            values["RAPID/T_ROB1/TRAJCENTER_WebServices/trajectories%7B1%7D"]
            == '["A",10,1]'
        )
        assert (
            values["RAPID/T_ROB1/TRAJCENTER_WebServices/trajectories%7B2%7D"]
            == '["B",20,2]'
        )

    @pytest.mark.asyncio
    async def test_status_values_written(self, client: MagicMock) -> None:
        """Metadata refresh status variables are written."""
        mock_set = AsyncMock()
        with patch(f"{_MODULE}.set_variables_with_mastership", mock_set):
            await write_store_metadata(client, names=["A"], point_counts=[10])

        values = mock_set.call_args.kwargs["values"]
        assert (
            values["RAPID/T_ROB1/TRAJCENTER_WebServices/refreshMetaRequest"] == "FALSE"
        )
        assert values["RAPID/T_ROB1/TRAJCENTER_WebServices/transferError"] == "FALSE"
        assert values["RAPID/T_ROB1/TRAJCENTER_WebServices/lastErrorCode"] == str(
            STATUS_METADATA_REFRESHED
        )
        assert values["RAPID/T_ROB1/TRAJCENTER_WebServices/lastError"] == '""'
        assert values["RAPID/T_ROB1/TRAJCENTER_WebServices/transferProgress"] == "100"

    @pytest.mark.asyncio
    async def test_mismatched_lengths_raises(self, client: MagicMock) -> None:
        """Mismatched ``names``/``point_counts`` lengths raise ``ValueError``."""
        with pytest.raises(ValueError, match="same length"):
            await write_store_metadata(client, names=["A", "B"], point_counts=[10])

    @pytest.mark.asyncio
    async def test_mismatched_process_types_raises(self, client: MagicMock) -> None:
        """Mismatched ``process_types`` length raises ``ValueError``."""
        with pytest.raises(ValueError, match="process_types"):
            await write_store_metadata(
                client,
                names=["A", "B"],
                point_counts=[10, 20],
                process_types=[0],
            )

    @pytest.mark.asyncio
    async def test_too_many_trajectories_raises(self, client: MagicMock) -> None:
        """More trajectories than ``MAX_TRAJ`` raises ``ValueError``."""
        names = [f"T{i}" for i in range(MAX_TRAJ + 1)]
        counts = [100] * (MAX_TRAJ + 1)
        with pytest.raises(ValueError, match="MAX_TRAJ"):
            await write_store_metadata(client, names=names, point_counts=counts)

    @pytest.mark.asyncio
    async def test_mastership_denied_retries(self, client: MagicMock) -> None:
        """``MastershipDenied`` triggers retries up to ``mastership_retries``."""
        mock_set = AsyncMock(side_effect=MastershipDenied("denied"))
        with patch(f"{_MODULE}.set_variables_with_mastership", mock_set):
            with patch(f"{_MODULE}.asyncio.sleep", AsyncMock()):
                with pytest.raises(MastershipDenied):
                    await write_store_metadata(
                        client,
                        names=["A"],
                        point_counts=[10],
                        mastership_retries=3,
                    )

        assert mock_set.call_count == 3

    @pytest.mark.asyncio
    async def test_custom_task_and_module(self, client: MagicMock) -> None:
        """Custom ``task`` and ``module`` are forwarded into symbol URLs."""
        mock_set = AsyncMock()
        with patch(f"{_MODULE}.set_variables_with_mastership", mock_set):
            await write_store_metadata(
                client,
                names=["T"],
                point_counts=[5],
                task="T_ROB2",
                module="MY_MOD",
            )

        values = mock_set.call_args.kwargs["values"]
        first_key = next(iter(values))
        assert first_key == "RAPID/T_ROB2/MY_MOD/nbTrajAvailable"


class TestRetryMastership:
    """Tests for :func:`trajcenter.rws.writer._retry_mastership`."""

    @pytest.mark.asyncio
    async def test_success_first_attempt(self) -> None:
        """A successful callable is executed once."""
        mock = AsyncMock()
        await _retry_mastership(mock, retries=3)
        mock.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_invalid_retries_raises(self) -> None:
        """``retries < 1`` raises ``ValueError``."""
        with pytest.raises(ValueError, match=">= 1"):
            await _retry_mastership(AsyncMock(), retries=0)

    @pytest.mark.asyncio
    async def test_denied_then_success(self) -> None:
        """A first ``MastershipDenied`` can succeed on retry."""
        mock = AsyncMock(side_effect=[MastershipDenied("denied"), None])
        with patch(f"{_MODULE}.asyncio.sleep", AsyncMock()):
            await _retry_mastership(mock, retries=2)
        assert mock.call_count == 2

    @pytest.mark.asyncio
    async def test_denied_then_raises(self) -> None:
        """All denied attempts re-raise ``MastershipDenied``."""
        mock = AsyncMock(side_effect=MastershipDenied("denied"))
        with patch(f"{_MODULE}.asyncio.sleep", AsyncMock()):
            with pytest.raises(MastershipDenied):
                await _retry_mastership(mock, retries=2)
        assert mock.call_count == 2


class TestWriteTrajectoryPlaceholder:
    """Temporary tests for trajectory writer during RWS-3."""

    @pytest.mark.asyncio
    async def test_write_trajectory_not_implemented_yet(
        self,
        client: MagicMock,
    ) -> None:
        """The obsolete v1 writer must not silently run."""
        with pytest.raises(NotImplementedError, match="RWS-4"):
            await write_trajectory(client, MagicMock())
