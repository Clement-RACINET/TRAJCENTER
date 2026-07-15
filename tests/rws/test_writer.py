# tests/rws/test_writer.py
"""Unit tests for :mod:`trajcenter.rws.writer`.

All RWS calls are mocked via ``unittest.mock.AsyncMock``.
No HTTP traffic is made.

Covers:
- _symbol helper
- _fmt_num / _fmt_bool / _fmt_string helpers
- _row_to_robtarget — nominal, inactive eax, all eax active
- _eax_presence detection
- write_store_metadata — nominal, padding, validation errors
- write_trajectory — nominal, progress callback, TrajReady last,
  MastershipDenied retry, zero-points guard, tools/wobjs overflow
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest

from abb_rws_client_python_rw6 import MastershipDenied, RobTarget
from trajcenter.core.trajectory import Trajectory, TrajectoryMeta
from trajcenter.rws.writer import (
    MAX_TRAJ,
    MAX_TOOLS,
    MAX_WOBJS,
    _eax_presence,
    _fmt_bool,
    _fmt_num,
    _fmt_string,
    _row_to_robtarget,
    _symbol,
    write_store_metadata,
    write_trajectory,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_MODULE = "trajcenter.rws.writer"


@pytest.fixture
def client() -> MagicMock:
    """Bare MagicMock acting as RWSClient."""
    return MagicMock()


def _make_df(n: int = 2, with_eax_a: bool = False) -> pd.DataFrame:
    """Build a minimal valid points DataFrame with *n* rows."""
    data: dict[str, list] = {
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
        "tool_index": [0] * n,
        "wobj_index": [0] * n,
        "move_type": ["MoveL"] * n,
        "speed": ["v500"] * n,
        "zone": ["z10"] * n,
    }
    if with_eax_a:
        data["eax_a"] = [100.0] * n
    return pd.DataFrame(data)


def _make_traj(
    n: int = 2,
    tools: list[str] | None = None,
    wobjs: list[str] | None = None,
    with_eax_a: bool = False,
) -> Trajectory:
    """Build a minimal valid Trajectory."""
    return Trajectory(
        meta=TrajectoryMeta(name="test_traj"),
        points=_make_df(n, with_eax_a=with_eax_a),
        tools=tools or ["tool0"],
        wobjs=wobjs or ["wobj0"],
    )


# ---------------------------------------------------------------------------
# _symbol
# ---------------------------------------------------------------------------


class TestSymbol:
    """Tests for _symbol()."""

    def test_simple_variable(self) -> None:
        """Simple variable name is correctly assembled."""
        assert _symbol("T_ROB1", "TRAJCENTER", "TrajReady") == (
            "RAPID/T_ROB1/TRAJCENTER/TrajReady"
        )

    def test_array_element(self) -> None:
        """Array element notation is preserved verbatim."""
        assert _symbol("T_ROB1", "TRAJCENTER", "RobtTRAJCENTER/[1]") == (
            "RAPID/T_ROB1/TRAJCENTER/RobtTRAJCENTER/[1]"
        )

    def test_custom_task_and_module(self) -> None:
        """Custom task and module names are used."""
        assert _symbol("T_ROB2", "MY_MOD", "Var") == "RAPID/T_ROB2/MY_MOD/Var"


# ---------------------------------------------------------------------------
# _fmt_num / _fmt_bool / _fmt_string
# ---------------------------------------------------------------------------


class TestFormatHelpers:
    """Tests for format helper functions."""

    def test_fmt_num_integer(self) -> None:
        assert _fmt_num(42) == "42"

    def test_fmt_num_float_integer(self) -> None:
        assert _fmt_num(42.0) == "42"

    def test_fmt_num_float(self) -> None:
        assert _fmt_num(3.14) == "3.14"

    def test_fmt_num_zero(self) -> None:
        assert _fmt_num(0) == "0"

    def test_fmt_bool_true(self) -> None:
        assert _fmt_bool(True) == "TRUE"

    def test_fmt_bool_false(self) -> None:
        assert _fmt_bool(False) == "FALSE"

    def test_fmt_string_simple(self) -> None:
        assert _fmt_string("Tool_formage") == '"Tool_formage"'

    def test_fmt_string_empty(self) -> None:
        assert _fmt_string("") == '""'


# ---------------------------------------------------------------------------
# _eax_presence
# ---------------------------------------------------------------------------


class TestEaxPresence:
    """Tests for _eax_presence()."""

    def test_no_eax_columns(self) -> None:
        df = _make_df()
        assert _eax_presence(df) == (False, False, False, False, False, False)

    def test_eax_a_only(self) -> None:
        df = _make_df(with_eax_a=True)
        assert _eax_presence(df) == (True, False, False, False, False, False)

    def test_all_eax_columns(self) -> None:
        df = _make_df()
        for col in ("eax_a", "eax_b", "eax_c", "eax_d", "eax_e", "eax_f"):
            df[col] = 0.0
        assert _eax_presence(df) == (True, True, True, True, True, True)


# ---------------------------------------------------------------------------
# _row_to_robtarget
# ---------------------------------------------------------------------------


class TestRowToRobtarget:
    """Tests for _row_to_robtarget()."""

    def test_nominal_no_eax(self) -> None:
        """All eax inactive → sentinel 9e9."""
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
        assert rt.qx == 0.0
        assert rt.eax == [9e9] * 6

    def test_quaternion_mapping(self) -> None:
        """q1→qw, q2→qx, q3→qy, q4→qz (ABB scalar-first convention)."""
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
        assert rt.qx == 0.0
        assert rt.qz == 0.0

    def test_eax_a_active(self) -> None:
        """Active eax_a is read from the row; others remain 9e9."""
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
        assert rt.eax[1] == 9e9
        assert rt.eax[5] == 9e9

    def test_all_eax_active(self) -> None:
        """All 6 eax columns active → all values read from row."""
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
                "eax_a": 1.0,
                "eax_b": 2.0,
                "eax_c": 3.0,
                "eax_d": 4.0,
                "eax_e": 5.0,
                "eax_f": 6.0,
            }
        )
        rt = _row_to_robtarget(row, (True,) * 6)
        assert rt.eax == [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]

    def test_confdata_cast(self) -> None:
        """cf1/cf4/cf6/cfx are cast to float."""
        row = pd.Series(
            {
                "x": 0.0,
                "y": 0.0,
                "z": 0.0,
                "q1": 1.0,
                "q2": 0.0,
                "q3": 0.0,
                "q4": 0.0,
                "cf1": -1,
                "cf4": 2,
                "cf6": 0,
                "cfx": 1,
            }
        )
        rt = _row_to_robtarget(row, (False,) * 6)
        assert rt.cf1 == -1.0
        assert rt.cf4 == 2.0


# ---------------------------------------------------------------------------
# write_store_metadata
# ---------------------------------------------------------------------------


class TestWriteStoreMetadata:
    """Tests for write_store_metadata()."""

    @pytest.mark.asyncio
    async def test_nominal(self, client: MagicMock) -> None:
        """Nominal: W1 + W2×MAX_TRAJ + W3×MAX_TRAJ calls are made."""
        mock_set = AsyncMock()
        with patch(f"{_MODULE}.set_variable_with_mastership", mock_set):
            await write_store_metadata(
                client,
                names=["Traj1", "Traj2"],
                point_counts=[320, 150],
            )

        # W1 + W2×MAX_TRAJ + W3×MAX_TRAJ
        expected_calls = 1 + MAX_TRAJ + MAX_TRAJ
        assert mock_set.call_count == expected_calls

    @pytest.mark.asyncio
    async def test_w1_value(self, client: MagicMock) -> None:
        """W1 (NbTrajDispo) receives the correct count."""
        mock_set = AsyncMock()
        with patch(f"{_MODULE}.set_variable_with_mastership", mock_set):
            await write_store_metadata(
                client, names=["A", "B", "C"], point_counts=[10, 20, 30]
            )
        first_call = mock_set.call_args_list[0]
        assert first_call.kwargs["symbolurl"] == "RAPID/T_ROB1/TRAJCENTER/NbTrajDispo"
        assert first_call.kwargs["value"] == "3"

    @pytest.mark.asyncio
    async def test_names_padded_with_empty_strings(self, client: MagicMock) -> None:
        """Names beyond the list are padded with empty RAPID strings."""
        mock_set = AsyncMock()
        with patch(f"{_MODULE}.set_variable_with_mastership", mock_set):
            await write_store_metadata(client, names=["OnlyOne"], point_counts=[100])
        # W2 calls: index 1 = "OnlyOne", index 2..MAX_TRAJ = ""
        w2_calls = mock_set.call_args_list[1 : 1 + MAX_TRAJ]
        assert w2_calls[0].kwargs["value"] == '"OnlyOne"'
        assert w2_calls[1].kwargs["value"] == '""'
        assert w2_calls[-1].kwargs["value"] == '""'

    @pytest.mark.asyncio
    async def test_mismatched_lengths_raises(self, client: MagicMock) -> None:
        """Mismatched names/point_counts raises ValueError."""
        with pytest.raises(ValueError, match="same length"):
            await write_store_metadata(client, names=["A", "B"], point_counts=[10])

    @pytest.mark.asyncio
    async def test_too_many_trajectories_raises(self, client: MagicMock) -> None:
        """More trajectories than MAX_TRAJ raises ValueError."""
        names = [f"T{i}" for i in range(MAX_TRAJ + 1)]
        counts = [100] * (MAX_TRAJ + 1)
        with pytest.raises(ValueError, match="MAX_TRAJ"):
            await write_store_metadata(client, names=names, point_counts=counts)

    @pytest.mark.asyncio
    async def test_mastership_denied_retries(self, client: MagicMock) -> None:
        """MastershipDenied triggers retries up to the limit."""
        mock_set = AsyncMock(side_effect=MastershipDenied("denied"))
        with patch(f"{_MODULE}.set_variable_with_mastership", mock_set):
            with patch(f"{_MODULE}.asyncio.sleep", AsyncMock()):
                with pytest.raises(MastershipDenied):
                    await write_store_metadata(
                        client,
                        names=["A"],
                        point_counts=[10],
                        mastership_retries=3,
                    )
        # 3 attempts × 1 call each (fails on first call of each attempt)
        assert mock_set.call_count == 3

    @pytest.mark.asyncio
    async def test_custom_task_and_module(self, client: MagicMock) -> None:
        """Custom task/module names are forwarded to symbol URLs."""
        mock_set = AsyncMock()
        with patch(f"{_MODULE}.set_variable_with_mastership", mock_set):
            await write_store_metadata(
                client,
                names=["T"],
                point_counts=[5],
                task="T_ROB2",
                module="MY_MOD",
            )
        first_call = mock_set.call_args_list[0]
        assert "T_ROB2" in first_call.kwargs["symbolurl"]
        assert "MY_MOD" in first_call.kwargs["symbolurl"]


# ---------------------------------------------------------------------------
# write_trajectory
# ---------------------------------------------------------------------------


class TestWriteTrajectory:
    """Tests for write_trajectory()."""

    @pytest.mark.asyncio
    async def test_nominal_call_count(self, client: MagicMock) -> None:
        """Nominal: W4 + W6 + W7×MAX_TOOLS + W8 + W9×MAX_WOBJS + W5×N + W10."""
        traj = _make_traj(n=3)
        mock_set = AsyncMock()
        with patch(f"{_MODULE}.set_variable_with_mastership", mock_set):
            await write_trajectory(client, traj)

        n = 3
        # W4(1) + W6(1) + W7(MAX_TOOLS) + W8(1) + W9(MAX_WOBJS) + W5(n) + W10(1)
        expected = 1 + 1 + MAX_TOOLS + 1 + MAX_WOBJS + n + 1
        assert mock_set.call_count == expected

    @pytest.mark.asyncio
    async def test_traj_ready_written_last(self, client: MagicMock) -> None:
        """TrajReady = TRUE must be the very last write."""
        traj = _make_traj(n=2)
        mock_set = AsyncMock()
        with patch(f"{_MODULE}.set_variable_with_mastership", mock_set):
            await write_trajectory(client, traj)

        last_call = mock_set.call_args_list[-1]
        assert "TrajReady" in last_call.kwargs["symbolurl"]
        assert last_call.kwargs["value"] == "TRUE"

    @pytest.mark.asyncio
    async def test_progress_callback(self, client: MagicMock) -> None:
        """on_progress is called once per robtarget with correct indices."""
        traj = _make_traj(n=4)
        progress_calls: list[tuple[int, int]] = []

        mock_set = AsyncMock()
        with patch(f"{_MODULE}.set_variable_with_mastership", mock_set):
            await write_trajectory(
                client,
                traj,
                on_progress=lambda i, n: progress_calls.append((i, n)),
            )

        assert len(progress_calls) == 4
        assert progress_calls[0] == (1, 4)
        assert progress_calls[-1] == (4, 4)

    @pytest.mark.asyncio
    async def test_zero_points_raises(self, client: MagicMock) -> None:
        """Empty trajectory raises ValueError before any RWS call."""
        traj = _make_traj(n=0)  # Trajectory valide, 0 lignes
        mock_set = AsyncMock()
        with patch(f"{_MODULE}.set_variable_with_mastership", mock_set):
            with pytest.raises(ValueError, match="no points"):
                await write_trajectory(client, traj)
        mock_set.assert_not_called()

    @pytest.mark.asyncio
    async def test_too_many_tools_raises(self, client: MagicMock) -> None:
        """More tools than MAX_TOOLS raises ValueError."""
        tools = [f"tool{i}" for i in range(MAX_TOOLS + 1)]
        traj = _make_traj(tools=tools)
        with pytest.raises(ValueError, match="MAX_TOOLS"):
            await write_trajectory(client, traj)

    @pytest.mark.asyncio
    async def test_too_many_wobjs_raises(self, client: MagicMock) -> None:
        """More wobjs than MAX_WOBJS raises ValueError."""
        wobjs = [f"wobj{i}" for i in range(MAX_WOBJS + 1)]
        traj = _make_traj(wobjs=wobjs)
        with pytest.raises(ValueError, match="MAX_WOBJS"):
            await write_trajectory(client, traj)

    @pytest.mark.asyncio
    async def test_mastership_denied_retries_then_raises(
        self, client: MagicMock
    ) -> None:
        """MastershipDenied retries mastership_retries times then re-raises."""
        traj = _make_traj(n=1)
        mock_set = AsyncMock(side_effect=MastershipDenied("denied"))
        with patch(f"{_MODULE}.set_variable_with_mastership", mock_set):
            with patch(f"{_MODULE}.asyncio.sleep", AsyncMock()):
                with pytest.raises(MastershipDenied):
                    await write_trajectory(client, traj, mastership_retries=2)
        assert mock_set.call_count == 2

    @pytest.mark.asyncio
    async def test_mastership_denied_then_success(self, client: MagicMock) -> None:
        """MastershipDenied on first attempt succeeds on second."""
        traj = _make_traj(n=1)
        attempt = 0

        async def _side_effect(*args: object, **kwargs: object) -> None:
            # Accepte positionnels ET kwargs — robuste quelle que soit la signature
            nonlocal attempt
            attempt += 1
            if attempt == 1:
                raise MastershipDenied("denied")
            # Tentatives suivantes : succès silencieux

        mock_set = AsyncMock(side_effect=_side_effect)
        with patch(f"{_MODULE}.set_variable_with_mastership", mock_set):
            with patch(f"{_MODULE}.asyncio.sleep", AsyncMock()):
                # Ne doit pas lever — le retry 2 réussit
                await write_trajectory(client, traj, mastership_retries=3)

        # Au moins 2 appels (1 échec + reprise depuis W4)
        assert mock_set.call_count >= 2

    @pytest.mark.asyncio
    async def test_eax_active_column_written(self, client: MagicMock) -> None:
        """Active eax_a column is included in robtarget value (not 9E+9)."""
        traj = _make_traj(n=1, with_eax_a=True)
        written_values: list[str] = []

        async def _capture(*args: object, **kwargs: object) -> None:
            # Robuste : capture symbolurl et value quelle que soit la convention d'appel
            symbolurl = kwargs.get("symbolurl", args[1] if len(args) > 1 else "")
            value = kwargs.get("value", args[2] if len(args) > 2 else "")
            if "RobtTRAJCENTER" in str(symbolurl):
                written_values.append(str(value))

        mock_set = AsyncMock(side_effect=_capture)
        with patch(f"{_MODULE}.set_variable_with_mastership", mock_set):
            await write_trajectory(client, traj)

        assert len(written_values) == 1
        robt_str = written_values[0]
        # Format attendu : [[x,y,z],[qw,qx,qy,qz],[cf1,cf4,cf6,cfx],[eax_a,9E+9,...]]
        assert robt_str.startswith("[[")
        # eax_a = 100.0 → "100" dans la valeur, pas "9E+9"
        # Les 5 axes suivants (eax_b..f) sont inactifs
        assert "9E+9,9E+9,9E+9,9E+9,9E+9" in robt_str
        # eax_a n'est PAS 9E+9 (il vaut 100)
        # On vérifie que la valeur ne commence pas par 9E+9 dans le bloc eax
        eax_block = robt_str.split("[")[-1].rstrip("]")
        first_eax = eax_block.split(",")[0]
        assert first_eax != "9E+9"

    @pytest.mark.asyncio
    async def test_nb4_value_correct(self, client: MagicMock) -> None:
        """W4 (NbRobtargetsTraj) receives the correct point count."""
        traj = _make_traj(n=7)
        mock_set = AsyncMock()
        with patch(f"{_MODULE}.set_variable_with_mastership", mock_set):
            await write_trajectory(client, traj)

        first_call = mock_set.call_args_list[0]
        assert "NbRobtargetsTraj" in first_call.kwargs["symbolurl"]
        assert first_call.kwargs["value"] == "7"

    @pytest.mark.asyncio
    async def test_tools_padded_with_empty_strings(self, client: MagicMock) -> None:
        """Tool names beyond the list are padded with empty RAPID strings."""
        traj = _make_traj(n=1, tools=["MyTool"])
        mock_set = AsyncMock()
        with patch(f"{_MODULE}.set_variable_with_mastership", mock_set):
            await write_trajectory(client, traj)

        # Find W7 calls (NomsTool)
        tool_calls = [
            c
            for c in mock_set.call_args_list
            if "NomsTool" in str(c.kwargs.get("symbolurl", ""))
        ]
        assert len(tool_calls) == MAX_TOOLS
        assert tool_calls[0].kwargs["value"] == '"MyTool"'
        assert tool_calls[1].kwargs["value"] == '""'
