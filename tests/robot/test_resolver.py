#!/usr/bin/env python3
# tests/robot/abb/test_resolver.py
"""Tests for :mod:`trajcenter.robot.resolver`.

Author: Clement RACINET

The resolver is pure local logic. No ABB controller access is performed.
"""

from __future__ import annotations

import pandas as pd
import pytest
from pydantic import ValidationError

from trajcenter.core.trajectory import (
    MoveType,
    Trajectory,
    TrajectoryMeta,
    TrajectoryProcess,
)
from trajcenter.robot.models import (
    ProcessTypeEntry,
    ResolvedProcessParamSet,
    RobotContext,
    RobotDefaults,
)
from trajcenter.robot.resolver import (
    _build_process_param_slots,
    _is_missing,
    _process_param_rows_by_index,
    _resolve_confdata_value,
    _resolve_optional_float,
    _resolve_point_process_index,
    _resolve_read_confs,
    _to_float,
    _to_int,
    _used_process_source_indexes,
    move_type_code_to_name,
    resolve_trajectory,
)

_MODULE = "trajcenter.robot.resolver"


def _defaults(
    *,
    has_tcp_speed: bool = True,
    tcp_speed: float | None = 500.0,
    has_zone_type: bool = True,
    zone_type: int | None = 10,
    has_tool_name: bool = True,
    tool_name: str | None = "Tool_A",
    has_wobj_name: bool = True,
    wobj_name: str | None = "Wobj_A",
    move_type: int = 0,
    read_confs: bool = True,
) -> RobotDefaults:
    """Build robot defaults for resolver tests.

    ABB Route:
        N/A — local test helper.

    ABB Constraints:
        No controller access is performed.

    Args:
        has_tcp_speed: Whether default TCP speed is enabled.
        tcp_speed: Default TCP speed.
        has_zone_type: Whether default zone is enabled.
        zone_type: Default zone.
        has_tool_name: Whether default tool is enabled.
        tool_name: Default tool name.
        has_wobj_name: Whether default workobject is enabled.
        wobj_name: Default workobject name.
        move_type: Default movement type code.
        read_confs: Default readConfs flag.

    Returns:
        Robot defaults.


    Example:
        ```python
        defaults = _defaults()
        ```
    """
    return RobotDefaults(
        has_tcp_speed=has_tcp_speed,
        tcp_speed=tcp_speed,
        has_zone_type=has_zone_type,
        zone_type=zone_type,
        has_tool_name=has_tool_name,
        tool_name=tool_name,
        has_wobj_name=has_wobj_name,
        wobj_name=wobj_name,
        move_type=move_type,
        read_confs=read_confs,
    )


def _context(defaults: RobotDefaults | None = None) -> RobotContext:
    """Build robot context for resolver tests.

    ABB Route:
        N/A — local test helper.

    ABB Constraints:
        Tool and workobject lists are ordered like RAPID arrays.

    Args:
        defaults: Optional robot defaults.

    Returns:
        Robot context.


    Example:
        ```python
        context = _context()
        ```
    """
    return RobotContext(
        defaults=defaults or _defaults(),
        tool_names=("Tool_A", "Tool_B"),
        wobj_names=("Wobj_A", "Wobj_B"),
        process_types=(
            ProcessTypeEntry(id=0, name="NONE"),
            ProcessTypeEntry(id=1, name="ACF"),
            ProcessTypeEntry(id=2, name="AAK"),
            ProcessTypeEntry(id=3, name="PUSHCORP"),
        ),
    )


def _base_points(**extra: object) -> pd.DataFrame:
    """Build a minimal point table.

    ABB Route:
        N/A — local test helper.

    ABB Constraints:
        The mandatory robtarget geometry columns are always present.

    Args:
        **extra: Extra columns overriding or extending the base point.

    Returns:
        Point DataFrame.


    Example:
        ```python
        points = _base_points(tool_name="Tool_A")
        ```
    """
    row: dict[str, object] = {
        "x": 100.0,
        "y": 200.0,
        "z": 300.0,
        "q1": 1.0,
        "q2": 0.0,
        "q3": 0.0,
        "q4": 0.0,
    }
    row.update(extra)
    return pd.DataFrame([row])


def _resolved_process_set(index: int) -> ResolvedProcessParamSet:
    """Build one resolved process parameter set.

    ABB Route:
        N/A — local test helper.

    ABB Constraints:
        The returned index mimics the RAPID base-1 process parameter index.

    Args:
        index: Resolved RAPID index.

    Returns:
        Resolved process parameter set.


    Example:
        ```python
        param_set = _resolved_process_set(1)
        ```
    """
    return ResolvedProcessParamSet(
        index=index,
        params=_build_process_param_slots(("force",), (120.0,)),
    )


def _trajectory(points: pd.DataFrame) -> Trajectory:
    """Build a no-process trajectory.

    ABB Route:
        N/A — local test helper.

    ABB Constraints:
        No process parameter table is attached.

    Args:
        points: Point table.

    Returns:
        Trajectory.

    Raises:
        ValueError: If points are invalid.

    Example:
        ```python
        trajectory = _trajectory(points)
        ```
    """
    return Trajectory(meta=TrajectoryMeta(name="demo"), points=points)


def _process_trajectory(
    *,
    points: pd.DataFrame,
    process_params: pd.DataFrame | None,
    param_names: list[str] | None = None,
    process_type: int = 1,
) -> Trajectory:
    """Build a process trajectory.

    ABB Route:
        N/A — local test helper.

    ABB Constraints:
        ``process_type`` must exist in the test robot process catalog unless
        the test explicitly validates catalog rejection.

    Args:
        points: Point table.
        process_params: Optional process parameter table.
        param_names: Ordered process parameter names.
        process_type: Numeric process type.

    Returns:
        Trajectory with process metadata.

    Raises:
        ValueError: If trajectory construction rejects the provided data.

    Example:
        ```python
        trajectory = _process_trajectory(points=points, process_params=params)
        ```
    """
    return Trajectory(
        meta=TrajectoryMeta(
            name="process_demo",
            process=TrajectoryProcess(
                process_type=process_type,
                process_param_names=param_names or ["force"],
            ),
        ),
        points=points,
        process_params=process_params,
    )


class TestResolveTrajectoryWithoutProcess:
    """Tests for no-process trajectory resolution."""

    def test_resolves_point_with_explicit_values(self) -> None:
        """Explicit point values override robot defaults."""
        points = _base_points(
            move_type="MoveJ",
            tcp_speed=250.0,
            zone_type=5,
            tool_name="Tool_B",
            wobj_name="Wobj_B",
            readconfs=False,
            cf1=1,
            cf4=2,
            cf6=3,
            cfx=4,
            eax_a=45.0,
        )

        resolved = resolve_trajectory(_trajectory(points), _context())

        assert resolved.name == "demo"
        assert resolved.process_type == 0
        assert resolved.point_count == 1
        assert resolved.process_param_sets == ()

        point = resolved.points[0]
        assert point.move_type == 1
        assert point.tcp_speed == 250.0
        assert point.zone_type == 5
        assert point.read_confs is False
        assert point.tool_index == 2
        assert point.wobj_index == 2
        assert point.process_param_index == 0

        assert point.robtarget.x == 100.0
        assert point.robtarget.y == 200.0
        assert point.robtarget.z == 300.0
        assert point.robtarget.q1 == 1.0
        assert point.robtarget.cf1 == 1
        assert point.robtarget.cf4 == 2
        assert point.robtarget.cf6 == 3
        assert point.robtarget.cfx == 4
        assert point.robtarget.eax == (45.0, None, None, None, None, None)

    def test_resolves_missing_optional_values_from_defaults(self) -> None:
        """Missing speed, zone, tool, wobj, move type and readconfs use defaults."""
        resolved = resolve_trajectory(_trajectory(_base_points()), _context())

        point = resolved.points[0]
        assert point.move_type == 0
        assert point.tcp_speed == 500.0
        assert point.zone_type == 10
        assert point.read_confs is True
        assert point.tool_index == 1
        assert point.wobj_index == 1
        assert point.robtarget.cf1 == 0
        assert point.robtarget.eax == (None, None, None, None, None, None)

    def test_missing_robtarget_value_raises(self) -> None:
        """Mandatory robtarget columns must be present and non-missing."""
        points = _base_points(x=None)

        with pytest.raises(ValueError, match="Cannot resolve robtarget"):
            resolve_trajectory(_trajectory(points), _context())

    def test_invalid_numeric_robtarget_value_raises(self) -> None:
        """Invalid numeric robtarget values are rejected during trajectory casting."""
        points = _base_points(x="not-a-number")

        with pytest.raises(ValueError, match="Cannot cast column 'x'"):
            _trajectory(points)

    def test_move_type_enum_is_supported(self) -> None:
        """MoveType enum values are normalized before alias lookup."""
        points = _base_points(
            move_type=MoveType.MOVE_C,
            tcp_speed=500.0,
            zone_type=10,
            tool_name="Tool_A",
            wobj_name="Wobj_A",
        )

        resolved = resolve_trajectory(_trajectory(points), _context())

        assert resolved.points[0].move_type == 2

    @pytest.mark.parametrize(
        ("raw_value", "expected"),
        [
            (True, True),
            (False, False),
            (1, True),
            (0, False),
        ],
    )
    def test_read_confs_supported_trajectory_values_are_resolved(
        self,
        raw_value: object,
        expected: bool,
    ) -> None:
        """Trajectory-compatible readconfs values are converted to booleans."""
        points = _base_points(
            tcp_speed=500.0,
            zone_type=10,
            tool_name="Tool_A",
            wobj_name="Wobj_A",
            readconfs=raw_value,
        )

        resolved = resolve_trajectory(_trajectory(points), _context())

        assert resolved.points[0].read_confs is expected

    @pytest.mark.parametrize(
        "raw_value",
        ["true", "1", "yes", "false", "0", "no"],
    )
    def test_read_confs_string_values_are_rejected_by_trajectory_cast(
        self,
        raw_value: object,
    ) -> None:
        """String readconfs values are rejected by the trajectory model casting."""
        points = _base_points(
            tcp_speed=500.0,
            zone_type=10,
            tool_name="Tool_A",
            wobj_name="Wobj_A",
            readconfs=raw_value,
        )

        with pytest.raises(ValueError, match="Cannot cast column 'readconfs'"):
            _trajectory(points)

    def test_missing_read_confs_uses_false_default(self) -> None:
        """Missing readconfs uses the robot default even when it is false."""
        context = _context(_defaults(read_confs=False))

        resolved = resolve_trajectory(_trajectory(_base_points()), context)

        assert resolved.points[0].read_confs is False

    def test_missing_tcp_speed_without_default_raises(self) -> None:
        """Missing TCP speed is invalid when robot default is disabled."""
        defaults = _defaults(has_tcp_speed=False, tcp_speed=None)

        with pytest.raises(ValueError, match="tcp_speed"):
            resolve_trajectory(_trajectory(_base_points()), _context(defaults))

    def test_missing_zone_without_default_raises(self) -> None:
        """Missing zone is invalid when robot default is disabled."""
        defaults = _defaults(has_zone_type=False, zone_type=None)

        with pytest.raises(ValueError, match="zone_type"):
            resolve_trajectory(_trajectory(_base_points()), _context(defaults))

    def test_missing_tool_without_default_raises(self) -> None:
        """Missing tool is invalid when robot default is disabled."""
        defaults = _defaults(has_tool_name=False, tool_name=None)

        with pytest.raises(ValueError, match="tool_name"):
            resolve_trajectory(_trajectory(_base_points()), _context(defaults))

    def test_missing_wobj_without_default_raises(self) -> None:
        """Missing workobject is invalid when robot default is disabled."""
        defaults = _defaults(has_wobj_name=False, wobj_name=None)

        with pytest.raises(ValueError, match="wobj_name"):
            resolve_trajectory(_trajectory(_base_points()), _context(defaults))

    def test_unknown_tool_raises(self) -> None:
        """A tool absent from robot context is rejected."""
        points = _base_points(
            tcp_speed=500.0,
            zone_type=10,
            tool_name="Unknown",
            wobj_name="Wobj_A",
        )

        with pytest.raises(ValueError, match="Tool"):
            resolve_trajectory(_trajectory(points), _context())

    def test_unknown_wobj_raises(self) -> None:
        """A workobject absent from robot context is rejected."""
        points = _base_points(
            tcp_speed=500.0,
            zone_type=10,
            tool_name="Tool_A",
            wobj_name="Unknown",
        )

        with pytest.raises(ValueError, match="Workobject"):
            resolve_trajectory(_trajectory(points), _context())

    def test_invalid_zone_raises(self) -> None:
        """Unsupported ABB zone codes are rejected."""
        points = _base_points(
            tcp_speed=500.0,
            zone_type=999,
            tool_name="Tool_A",
            wobj_name="Wobj_A",
        )

        with pytest.raises(ValueError, match="zone_type"):
            resolve_trajectory(_trajectory(points), _context())

    def test_invalid_move_type_raises(self) -> None:
        """Unsupported movement type strings are rejected."""
        points = _base_points(
            move_type="MoveX",
            tcp_speed=500.0,
            zone_type=10,
            tool_name="Tool_A",
            wobj_name="Wobj_A",
        )

        with pytest.raises(ValueError, match="move_type"):
            resolve_trajectory(_trajectory(points), _context())

    def test_process_type_not_in_robot_catalog_raises(self) -> None:
        """The robot process catalog is authoritative."""
        context = RobotContext(
            defaults=_defaults(),
            tool_names=("Tool_A",),
            wobj_names=("Wobj_A",),
            process_types=(),
        )

        with pytest.raises(ValueError, match="Process type"):
            resolve_trajectory(_trajectory(_base_points()), context)


class TestResolveTrajectoryWithProcess:
    """Tests for process parameter resolution."""

    def test_resolves_process_sets_and_point_indexes(self) -> None:
        """Used source process indexes are mapped to resolved RAPID indexes."""
        points = pd.DataFrame(
            [
                {
                    "x": 100.0,
                    "y": 200.0,
                    "z": 300.0,
                    "q1": 1.0,
                    "q2": 0.0,
                    "q3": 0.0,
                    "q4": 0.0,
                    "tcp_speed": 500.0,
                    "zone_type": 10,
                    "tool_name": "Tool_A",
                    "wobj_name": "Wobj_A",
                    "process_param_index": 2,
                },
                {
                    "x": 110.0,
                    "y": 210.0,
                    "z": 310.0,
                    "q1": 1.0,
                    "q2": 0.0,
                    "q3": 0.0,
                    "q4": 0.0,
                    "tcp_speed": 500.0,
                    "zone_type": 10,
                    "tool_name": "Tool_A",
                    "wobj_name": "Wobj_A",
                    "process_param_index": 5,
                },
                {
                    "x": 120.0,
                    "y": 220.0,
                    "z": 320.0,
                    "q1": 1.0,
                    "q2": 0.0,
                    "q3": 0.0,
                    "q4": 0.0,
                    "tcp_speed": 500.0,
                    "zone_type": 10,
                    "tool_name": "Tool_A",
                    "wobj_name": "Wobj_A",
                    "process_param_index": 0,
                },
            ]
        )
        process_params = pd.DataFrame(
            [
                {"process_param_index": 2, "force": 120.0, "feed": 5.0},
                {"process_param_index": 5, "force": 150.0, "feed": 7.0},
            ]
        )
        trajectory = _process_trajectory(
            points=points,
            process_params=process_params,
            param_names=["force", "feed"],
        )

        resolved = resolve_trajectory(trajectory, _context())

        assert resolved.name == "process_demo"
        assert resolved.process_type == 1
        assert resolved.point_count == 3
        assert len(resolved.process_param_sets) == 2

        assert resolved.points[0].process_param_index == 1
        assert resolved.points[1].process_param_index == 2
        assert resolved.points[2].process_param_index == 0

        first_set = resolved.process_param_sets[0]
        assert first_set.index == 1
        assert first_set.params[0].name == "force"
        assert first_set.params[0].value == 120.0
        assert first_set.params[1].name == "feed"
        assert first_set.params[1].value == 5.0
        assert first_set.params[2].name == ""
        assert first_set.params[2].value == 0.0

    def test_deduplicates_identical_process_sets(self) -> None:
        """Two source indexes with same values share one resolved set."""
        points = pd.DataFrame(
            [
                {
                    "x": 100.0,
                    "y": 200.0,
                    "z": 300.0,
                    "q1": 1.0,
                    "q2": 0.0,
                    "q3": 0.0,
                    "q4": 0.0,
                    "tcp_speed": 500.0,
                    "zone_type": 10,
                    "tool_name": "Tool_A",
                    "wobj_name": "Wobj_A",
                    "process_param_index": 1,
                },
                {
                    "x": 110.0,
                    "y": 210.0,
                    "z": 310.0,
                    "q1": 1.0,
                    "q2": 0.0,
                    "q3": 0.0,
                    "q4": 0.0,
                    "tcp_speed": 500.0,
                    "zone_type": 10,
                    "tool_name": "Tool_A",
                    "wobj_name": "Wobj_A",
                    "process_param_index": 2,
                },
            ]
        )
        process_params = pd.DataFrame(
            [
                {"process_param_index": 1, "force": 120.0},
                {"process_param_index": 2, "force": 120.0},
            ]
        )
        trajectory = _process_trajectory(points=points, process_params=process_params)

        resolved = resolve_trajectory(trajectory, _context())

        assert len(resolved.process_param_sets) == 1
        assert resolved.points[0].process_param_index == 1
        assert resolved.points[1].process_param_index == 1

    def test_active_process_with_only_zero_point_indexes_has_no_sets(self) -> None:
        """Active process may still have points with no parameter set."""
        points = _base_points(
            tcp_speed=500.0,
            zone_type=10,
            tool_name="Tool_A",
            wobj_name="Wobj_A",
            process_param_index=0,
        )
        process_params = pd.DataFrame([{"process_param_index": 1, "force": 120.0}])
        trajectory = _process_trajectory(points=points, process_params=process_params)

        resolved = resolve_trajectory(trajectory, _context())

        assert resolved.process_param_sets == ()
        assert resolved.points[0].process_param_index == 0

    def test_active_process_without_process_params_raises(self) -> None:
        """Active process requires a process parameter table."""
        points = _base_points(
            tcp_speed=500.0,
            zone_type=10,
            tool_name="Tool_A",
            wobj_name="Wobj_A",
            process_param_index=1,
        )

        with pytest.raises(ValueError, match="process_params is required"):
            _process_trajectory(points=points, process_params=None)

    def test_too_many_process_parameter_names_raises(self) -> None:
        """More than ten process parameters are rejected by trajectory metadata."""
        points = _base_points(
            tcp_speed=500.0,
            zone_type=10,
            tool_name="Tool_A",
            wobj_name="Wobj_A",
            process_param_index=1,
        )
        names = [f"p{i}" for i in range(11)]
        process_row: dict[str, object] = {"process_param_index": 1}
        process_row.update({name: float(index) for index, name in enumerate(names)})

        with pytest.raises(
            ValidationError, match="process_param_names has more than 10"
        ):
            _process_trajectory(
                points=points,
                process_params=pd.DataFrame([process_row]),
                param_names=names,
            )

    def test_missing_process_param_index_column_in_points_raises(self) -> None:
        """Active process points must contain process_param_index."""
        points = _base_points(
            tcp_speed=500.0,
            zone_type=10,
            tool_name="Tool_A",
            wobj_name="Wobj_A",
        )
        process_params = pd.DataFrame([{"process_param_index": 1, "force": 120.0}])

        with pytest.raises(ValueError, match="points must contain process_param_index"):
            _process_trajectory(points=points, process_params=process_params)

    def test_missing_process_param_index_column_in_params_raises(self) -> None:
        """Process parameter tables must contain process_param_index."""
        points = _base_points(
            tcp_speed=500.0,
            zone_type=10,
            tool_name="Tool_A",
            wobj_name="Wobj_A",
            process_param_index=1,
        )
        process_params = pd.DataFrame([{"force": 120.0}])

        with pytest.raises(ValueError, match="process_params must contain"):
            _process_trajectory(points=points, process_params=process_params)

    def test_missing_referenced_process_parameter_row_raises(self) -> None:
        """A point cannot reference a missing process parameter row."""
        points = _base_points(
            tcp_speed=500.0,
            zone_type=10,
            tool_name="Tool_A",
            wobj_name="Wobj_A",
            process_param_index=2,
        )
        process_params = pd.DataFrame([{"process_param_index": 1, "force": 120.0}])

        with pytest.raises(
            ValueError,
            match="points reference missing process_param_index values",
        ):
            _process_trajectory(points=points, process_params=process_params)

    def test_unresolved_point_process_index_raises(self) -> None:
        """Point process index resolution rejects unknown source indexes."""
        row = pd.Series({"process_param_index": 9})

        with pytest.raises(ValueError, match="unresolved process_param_index 9"):
            _resolve_point_process_index(
                row=row,
                process_type=1,
                process_index_by_source={1: _resolved_process_set(1)},
            )

    def test_missing_point_process_index_resolves_to_zero(self) -> None:
        """Missing point process index means no process parameter set."""
        row = pd.Series({})

        index = _resolve_point_process_index(
            row=row,
            process_type=1,
            process_index_by_source={},
        )

        assert index == 0


class TestResolverPrivateHelpers:
    """Targeted tests for resolver helper edge cases."""

    def test_unsupported_confdata_column_raises(self) -> None:
        """Only ABB confdata columns are accepted."""
        with pytest.raises(ValueError, match="Unsupported confdata column"):
            _resolve_confdata_value(pd.Series({}), "bad_cf")

    def test_unsupported_external_axis_column_raises(self) -> None:
        """Only ABB external axis columns are accepted."""
        with pytest.raises(ValueError, match="Unsupported external axis column"):
            _resolve_optional_float(pd.Series({}), "bad_eax")

    def test_used_process_source_indexes_missing_column_raises(self) -> None:
        """The process index column is mandatory for active processes."""
        with pytest.raises(ValueError, match="points must contain"):
            _used_process_source_indexes(pd.DataFrame([{"x": 1.0}]))

    def test_used_process_source_indexes_sorts_and_filters_zero(self) -> None:
        """Used process indexes are sorted and zero indexes are ignored."""
        points = pd.DataFrame(
            [
                {"process_param_index": 3},
                {"process_param_index": 0},
                {"process_param_index": 1},
            ]
        )

        assert _used_process_source_indexes(points) == [1, 3]

    def test_process_param_rows_by_index_missing_column_raises(self) -> None:
        """The process parameter table index column is mandatory."""
        with pytest.raises(ValueError, match="process_params must contain"):
            _process_param_rows_by_index(pd.DataFrame([{"force": 120.0}]))

    def test_process_param_rows_by_index_builds_mapping(self) -> None:
        """Process parameter rows are mapped by source index."""
        rows = _process_param_rows_by_index(
            pd.DataFrame(
                [
                    {"process_param_index": 2, "force": 120.0},
                    {"process_param_index": 5, "force": 150.0},
                ]
            )
        )

        assert sorted(rows) == [2, 5]
        assert rows[2]["force"] == 120.0
        assert rows[5]["force"] == 150.0

    def test_build_process_param_slots_length_mismatch_raises(self) -> None:
        """Process parameter names and values must have identical lengths."""
        with pytest.raises(ValueError, match="length mismatch"):
            _build_process_param_slots(("force", "feed"), (120.0,))

    def test_build_process_param_slots_too_many_names_raises(self) -> None:
        """More than ten process parameters cannot be represented."""
        names = tuple(f"p{i}" for i in range(11))
        values = tuple(float(i) for i in range(11))

        with pytest.raises(ValueError, match="Process parameter count exceeds"):
            _build_process_param_slots(names, values)

    def test_to_float_missing_raises(self) -> None:
        """Missing numeric values are rejected."""
        with pytest.raises(ValueError, match="Missing numeric value"):
            _to_float(None, name="tcp_speed")

    def test_to_float_invalid_raises(self) -> None:
        """Non-convertible floats are rejected."""
        with pytest.raises(ValueError, match="Cannot convert tcp_speed"):
            _to_float("invalid", name="tcp_speed")

    def test_to_int_missing_raises(self) -> None:
        """Missing integer values are rejected."""
        with pytest.raises(ValueError, match="Missing integer value"):
            _to_int(None, name="zone_type")

    def test_to_int_invalid_raises(self) -> None:
        """Non-convertible integers are rejected."""
        with pytest.raises(ValueError, match="Cannot convert zone_type"):
            _to_int("invalid", name="zone_type")

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            (None, True),
            ("", True),
            ("   ", True),
            (float("nan"), True),
            ("abc", False),
            (0, False),
        ],
    )
    def test_is_missing_standard_values(self, value: object, expected: bool) -> None:
        """Standard pandas and blank-string missing values are detected."""
        assert _is_missing(value) is expected

    def test_is_missing_returns_false_when_pandas_isna_raises(self) -> None:
        """Values unsupported by pandas.isna are treated as present."""

        class BadArray:
            """Object making pandas.isna return a non-scalar result."""

            def __bool__(self) -> bool:
                """Raise to exercise the defensive resolver branch.

                ABB Route:
                    N/A — local test helper.

                ABB Constraints:
                    No controller access is performed.

                Args:
                    None.

                Returns:
                    Never returns.

                Raises:
                    ValueError: Always raised to mimic ambiguous pandas truth value.

                Example:
                    ```python
                    bool(BadArray())
                    ```
                """
                raise ValueError("ambiguous truth value")

        assert _is_missing(BadArray()) is False

    @pytest.mark.parametrize(
        ("raw_value", "expected"),
        [
            ("TRUE", True),
            ("FALSE", False),
            ("unexpected", True),
            ("", True),
            ("true", True),
            ("1", True),
            ("yes", True),
            ("false", False),
            ("0", False),
            ("no", False),
            (1, True),
            (0, False),
        ],
    )
    def test_resolve_read_confs_direct_helper(
        self,
        raw_value: object,
        expected: bool,
    ) -> None:
        """The direct readconfs helper keeps fallback bool conversion behavior."""
        row = pd.Series({"readconfs": raw_value})

        assert _resolve_read_confs(row, _context()) is expected


class TestMoveTypeCodeToName:
    """Tests for movement type helper."""

    def test_known_codes(self) -> None:
        """Known movement codes are converted to names."""
        assert move_type_code_to_name(0) == "MoveL"
        assert move_type_code_to_name(1) == "MoveJ"
        assert move_type_code_to_name(2) == "MoveC"

    def test_unknown_code_raises(self) -> None:
        """Unknown movement codes are rejected."""
        with pytest.raises(ValueError, match="Unsupported"):
            move_type_code_to_name(99)
