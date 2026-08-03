#!/usr/bin/env python3
# tests/rws/test_resolver.py
"""Tests for :mod:`trajcenter.rws.resolver`.

Author: Clement RACINET

The resolver is pure local logic. No ABB controller access is performed.
"""

from __future__ import annotations

import pandas as pd
import pytest

from trajcenter.core.trajectory import Trajectory, TrajectoryMeta, TrajectoryProcess
from trajcenter.rws.models import ProcessTypeEntry, RobotContext, RobotDefaults
from trajcenter.rws.resolver import move_type_code_to_name, resolve_trajectory


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

    Returns:
        Robot defaults.

    Raises:
        None.

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
        move_type=0,
        read_confs=True,
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

    Raises:
        None.

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

    Raises:
        None.

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
        trajectory = Trajectory(
            meta=TrajectoryMeta(
                name="process_demo",
                process=TrajectoryProcess(
                    process_type=1,
                    process_param_names=["force", "feed"],
                ),
            ),
            points=points,
            process_params=process_params,
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
        trajectory = Trajectory(
            meta=TrajectoryMeta(
                name="dedupe",
                process=TrajectoryProcess(
                    process_type=1,
                    process_param_names=["force"],
                ),
            ),
            points=points,
            process_params=process_params,
        )

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
        trajectory = Trajectory(
            meta=TrajectoryMeta(
                name="no_used_sets",
                process=TrajectoryProcess(
                    process_type=1,
                    process_param_names=["force"],
                ),
            ),
            points=points,
            process_params=process_params,
        )

        resolved = resolve_trajectory(trajectory, _context())

        assert resolved.process_param_sets == ()
        assert resolved.points[0].process_param_index == 0


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
