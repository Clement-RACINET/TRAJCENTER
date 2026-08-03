#!/usr/bin/env python3
# tests/rws/test_writer.py
"""Unit tests for :mod:`trajcenter.rws.writer`.

Author: Clement RACINET

All RWS calls are mocked via ``unittest.mock.AsyncMock``.
No HTTP traffic is made.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest
from abb_rws_client_python_rw6 import MastershipDenied, RobTarget

from trajcenter.rws.models import (
    ResolvedPoint,
    ResolvedProcessParam,
    ResolvedProcessParamSet,
    ResolvedRobTarget,
    ResolvedTrajectory,
)
from trajcenter.rws.writer import (
    MAX_PROCESS_PARAM_PER_SET,
    MAX_PROCESS_PARAM_SET_COUNT,
    MAX_TRAJ,
    MAX_TRAJ_POINTS,
    STATUS_METADATA_REFRESHED,
    STATUS_TRAJECTORY_TRANSFERRED,
    _eax_presence,
    _fmt_bool,
    _fmt_num,
    _fmt_point_record,
    _fmt_process_param_record,
    _fmt_robtarget,
    _fmt_string,
    _fmt_traj_meta_record,
    _retry_mastership,
    _row_to_robtarget,
    _symbol_2d_array_element,
    write_resolved_trajectory,
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

    Args:
        None.

    Returns:
        Mock client.

    Raises:
        None.

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

    Raises:
        None.

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


def _make_resolved_robtarget() -> ResolvedRobTarget:
    """Build one resolved robtarget for writer tests.

    ABB Route:
        N/A — local test helper.

    ABB Constraints:
        ``None`` external axes are serialized as ``9E+9`` by the writer.

    Args:
        None.

    Returns:
        Resolved robtarget.

    Raises:
        None.

    Example:
        ::

            robtarget = _make_resolved_robtarget()
    """
    return ResolvedRobTarget(
        x=100.0,
        y=200.0,
        z=300.0,
        q1=1.0,
        q2=0.0,
        q3=0.0,
        q4=0.0,
        cf1=0,
        cf4=1,
        cf6=2,
        cfx=0,
        eax=(None, 12.5, None, None, None, None),
    )


def _make_resolved_point(process_param_index: int = 0) -> ResolvedPoint:
    """Build one resolved point for writer tests.

    ABB Route:
        N/A — local test helper.

    ABB Constraints:
        ``process_param_index`` follows RAPID base-1 convention or ``0``.

    Args:
        process_param_index: Process parameter set index.

    Returns:
        Resolved point.

    Raises:
        None.

    Example:
        ::

            point = _make_resolved_point(process_param_index=1)
    """
    return ResolvedPoint(
        move_type=0,
        robtarget=_make_resolved_robtarget(),
        tcp_speed=500.0,
        zone_type=10,
        read_confs=True,
        tool_index=1,
        wobj_index=2,
        process_param_index=process_param_index,
    )


def _make_empty_process_params() -> tuple[
    ResolvedProcessParam,
    ResolvedProcessParam,
    ResolvedProcessParam,
    ResolvedProcessParam,
    ResolvedProcessParam,
    ResolvedProcessParam,
    ResolvedProcessParam,
    ResolvedProcessParam,
    ResolvedProcessParam,
    ResolvedProcessParam,
]:
    """Build exactly ten empty process parameter slots.

    ABB Route:
        N/A — local test helper.

    ABB Constraints:
        ``trajCenterProcessParameter`` second RAPID dimension is fixed to 10.

    Args:
        None.

    Returns:
        Fixed-length tuple containing ten empty process parameter slots.

    Raises:
        None.

    Example:
        ::

            params = _make_empty_process_params()
    """
    empty = ResolvedProcessParam(name="", value=0.0)
    return (
        empty,
        empty,
        empty,
        empty,
        empty,
        empty,
        empty,
        empty,
        empty,
        empty,
    )


def _make_resolved_trajectory() -> ResolvedTrajectory:
    """Build one minimal resolved trajectory for writer tests.

    ABB Route:
        N/A — local test helper.

    ABB Constraints:
        Process parameter sets contain exactly 10 slots.

    Args:
        None.

    Returns:
        Resolved trajectory.

    Raises:
        None.

    Example:
        ::

            resolved = _make_resolved_trajectory()
    """
    empty_params = _make_empty_process_params()
    params = (
        ResolvedProcessParam(name="force", value=120.0),
        ResolvedProcessParam(name="speed", value=42.5),
        *empty_params[2:],
    )

    return ResolvedTrajectory(
        name="demo",
        process_type=1,
        points=(
            _make_resolved_point(process_param_index=1),
            _make_resolved_point(process_param_index=0),
        ),
        process_param_sets=(ResolvedProcessParamSet(index=1, params=params),),
    )


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

    def test_fmt_robtarget_injects_inactive_eax(self) -> None:
        """Inactive external axes are serialized as ``9E+9`` sentinel values."""
        assert _fmt_robtarget(_make_resolved_robtarget()) == (
            "[[100,200,300],[1,0,0,0],[0,1,2,0],"
            "[9000000000,12.5,9000000000,9000000000,9000000000,9000000000]]"
        )

    def test_fmt_process_param_record(self) -> None:
        """A process parameter is serialized as ``[name,value]``."""
        param = ResolvedProcessParam(name="force", value=120.0)
        assert _fmt_process_param_record(param) == '["force",120]'

    def test_fmt_point_record(self) -> None:
        """A resolved point is serialized in ``trajCenterPointData`` order."""
        point = _make_resolved_point(process_param_index=1)
        assert _fmt_point_record(point).startswith(
            "[0,[[100,200,300],[1,0,0,0],[0,1,2,0],"
        )
        assert _fmt_point_record(point).endswith(",500,10,TRUE,1,2,1]")

    def test_symbol_2d_array_element(self) -> None:
        """Two-dimensional RAPID array indexes are percent-encoded."""
        assert (
            _symbol_2d_array_element(
                task="T_ROB1",
                module="TRAJCENTER_WebServices",
                variable="processParams",
                first_index=1,
                second_index=2,
            )
            == "RAPID/T_ROB1/TRAJCENTER_WebServices/processParams%7B1%2C2%7D"
        )

    def test_symbol_2d_array_element_rejects_invalid_indexes(self) -> None:
        """Two-dimensional RAPID array indexes are one-based."""
        with pytest.raises(ValueError, match="first array index"):
            _symbol_2d_array_element("T_ROB1", "M", "a", 0, 1)

        with pytest.raises(ValueError, match="second array index"):
            _symbol_2d_array_element("T_ROB1", "M", "a", 1, 0)


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


class TestWriteResolvedTrajectory:
    """Tests for :func:`trajcenter.rws.writer.write_resolved_trajectory`."""

    @pytest.mark.asyncio
    async def test_nominal_single_mastership_call(self, client: MagicMock) -> None:
        """A resolved trajectory is written through one batched Mastership call."""
        mock_set = AsyncMock()
        resolved = _make_resolved_trajectory()

        with patch(f"{_MODULE}.set_variables_with_mastership", mock_set):
            await write_resolved_trajectory(client, resolved)

        mock_set.assert_awaited_once()
        assert mock_set.call_args.kwargs["domain"] == "rapid"

    @pytest.mark.asyncio
    async def test_status_and_flags_written(self, client: MagicMock) -> None:
        """The writer finalizes transfer status and request flags."""
        mock_set = AsyncMock()
        resolved = _make_resolved_trajectory()

        with patch(f"{_MODULE}.set_variables_with_mastership", mock_set):
            await write_resolved_trajectory(client, resolved)

        values = mock_set.call_args.kwargs["values"]
        assert values["RAPID/T_ROB1/TRAJCENTER_WebServices/trajReady"] == "TRUE"
        assert values["RAPID/T_ROB1/TRAJCENTER_WebServices/transferError"] == "FALSE"
        assert values["RAPID/T_ROB1/TRAJCENTER_WebServices/sendTrajRequest"] == "FALSE"
        assert values["RAPID/T_ROB1/TRAJCENTER_WebServices/transferProgress"] == "100"
        assert values["RAPID/T_ROB1/TRAJCENTER_WebServices/lastErrorCode"] == str(
            STATUS_TRAJECTORY_TRANSFERRED
        )
        assert values["RAPID/T_ROB1/TRAJCENTER_WebServices/lastError"] == '""'

    @pytest.mark.asyncio
    async def test_nb_loaded_points_written(self, client: MagicMock) -> None:
        """``nbLoadedTrajPoints`` receives the resolved point count."""
        mock_set = AsyncMock()
        resolved = _make_resolved_trajectory()

        with patch(f"{_MODULE}.set_variables_with_mastership", mock_set):
            await write_resolved_trajectory(client, resolved)

        values = mock_set.call_args.kwargs["values"]
        assert values["RAPID/T_ROB1/TRAJCENTER_WebServices/nbLoadedTrajPoints"] == "2"

    @pytest.mark.asyncio
    async def test_traj_data_records_written(self, client: MagicMock) -> None:
        """Resolved points are written into one-based ``trajData`` entries."""
        mock_set = AsyncMock()
        resolved = _make_resolved_trajectory()

        with patch(f"{_MODULE}.set_variables_with_mastership", mock_set):
            await write_resolved_trajectory(client, resolved)

        values = mock_set.call_args.kwargs["values"]
        first = values["RAPID/T_ROB1/TRAJCENTER_WebServices/trajData%7B1%7D"]
        second = values["RAPID/T_ROB1/TRAJCENTER_WebServices/trajData%7B2%7D"]

        assert first.endswith(",500,10,TRUE,1,2,1]")
        assert second.endswith(",500,10,TRUE,1,2,0]")

    @pytest.mark.asyncio
    async def test_process_params_are_written_and_cleared(
        self,
        client: MagicMock,
    ) -> None:
        """Used process sets are written and unused sets are cleared."""
        mock_set = AsyncMock()
        resolved = _make_resolved_trajectory()

        with patch(f"{_MODULE}.set_variables_with_mastership", mock_set):
            await write_resolved_trajectory(client, resolved)

        values = mock_set.call_args.kwargs["values"]

        assert (
            values["RAPID/T_ROB1/TRAJCENTER_WebServices/processParams%7B1%2C1%7D"]
            == '["force",120]'
        )
        assert (
            values["RAPID/T_ROB1/TRAJCENTER_WebServices/processParams%7B1%2C2%7D"]
            == '["speed",42.5]'
        )
        assert (
            values["RAPID/T_ROB1/TRAJCENTER_WebServices/processParams%7B2%2C1%7D"]
            == '["",0]'
        )

    @pytest.mark.asyncio
    async def test_process_param_table_size(self, client: MagicMock) -> None:
        """The process parameter table is fully normalized to ``256 x 10``."""
        mock_set = AsyncMock()
        resolved = _make_resolved_trajectory()

        with patch(f"{_MODULE}.set_variables_with_mastership", mock_set):
            await write_resolved_trajectory(client, resolved)

        values = mock_set.call_args.kwargs["values"]
        process_keys = [key for key in values if "processParams%7B" in key]
        assert len(process_keys) == (
            MAX_PROCESS_PARAM_SET_COUNT * MAX_PROCESS_PARAM_PER_SET
        )

    @pytest.mark.asyncio
    async def test_too_many_points_raises(self, client: MagicMock) -> None:
        """More points than RAPID capacity raises ``ValueError``."""
        point = _make_resolved_point()
        resolved = ResolvedTrajectory(
            name="too_many",
            process_type=0,
            points=(point,) * (MAX_TRAJ_POINTS + 1),
            process_param_sets=(),
        )

        with pytest.raises(ValueError, match="MAX_TRAJ_POINTS"):
            await write_resolved_trajectory(client, resolved)

    @pytest.mark.asyncio
    async def test_unknown_process_param_index_raises(
        self,
        client: MagicMock,
    ) -> None:
        """A point cannot reference a missing process parameter set."""
        resolved = ResolvedTrajectory(
            name="bad",
            process_type=0,
            points=(_make_resolved_point(process_param_index=2),),
            process_param_sets=(),
        )

        with pytest.raises(ValueError, match="unknown process parameter set"):
            await write_resolved_trajectory(client, resolved)

    @pytest.mark.asyncio
    async def test_invalid_process_param_set_index_raises(
        self,
        client: MagicMock,
    ) -> None:
        """Process parameter set indexes must fit RAPID bounds."""
        resolved = ResolvedTrajectory(
            name="bad",
            process_type=0,
            points=(_make_resolved_point(process_param_index=0),),
            process_param_sets=(
                ResolvedProcessParamSet(
                    index=257,
                    params=_make_empty_process_params(),
                ),
            ),
        )

        with pytest.raises(ValueError, match="Process parameter set index"):
            await write_resolved_trajectory(client, resolved)

    @pytest.mark.asyncio
    async def test_duplicate_process_param_set_index_raises(
        self,
        client: MagicMock,
    ) -> None:
        """Duplicate process parameter set indexes are rejected."""
        resolved = ResolvedTrajectory(
            name="bad",
            process_type=0,
            points=(_make_resolved_point(process_param_index=1),),
            process_param_sets=(
                ResolvedProcessParamSet(
                    index=1,
                    params=_make_empty_process_params(),
                ),
                ResolvedProcessParamSet(
                    index=1,
                    params=_make_empty_process_params(),
                ),
            ),
        )

        with pytest.raises(ValueError, match="Duplicate process parameter"):
            await write_resolved_trajectory(client, resolved)

    @pytest.mark.asyncio
    async def test_mastership_denied_retries(self, client: MagicMock) -> None:
        """``MastershipDenied`` triggers retries for trajectory writes."""
        mock_set = AsyncMock(side_effect=MastershipDenied("denied"))
        resolved = _make_resolved_trajectory()

        with patch(f"{_MODULE}.set_variables_with_mastership", mock_set):
            with patch(f"{_MODULE}.asyncio.sleep", AsyncMock()):
                with pytest.raises(MastershipDenied):
                    await write_resolved_trajectory(
                        client,
                        resolved,
                        mastership_retries=3,
                    )

        assert mock_set.call_count == 3

    @pytest.mark.asyncio
    async def test_progress_callback_is_called(self, client: MagicMock) -> None:
        """The optional local progress callback receives build progress."""
        mock_set = AsyncMock()
        progress = MagicMock()
        resolved = _make_resolved_trajectory()

        with patch(f"{_MODULE}.set_variables_with_mastership", mock_set):
            await write_resolved_trajectory(
                client,
                resolved,
                on_progress=progress,
            )

        assert progress.call_count > 0


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
    """Temporary tests for trajectory writer orchestration."""

    @pytest.mark.asyncio
    async def test_write_trajectory_not_implemented_yet(
        self,
        client: MagicMock,
    ) -> None:
        """The obsolete v1 writer must not silently run."""
        with pytest.raises(NotImplementedError, match="write_resolved_trajectory"):
            await write_trajectory(client, MagicMock())
