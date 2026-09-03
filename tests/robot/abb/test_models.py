#!/usr/bin/env python3
# tests/robot/abb/test_models.py
"""Tests for :mod:`trajcenter.robot.abb.models`.

Author: Clement RACINET

These tests validate the local typed models used by the RWS resolver, writer,
reader and service layers. No ABB controller access is performed.
"""

from __future__ import annotations

from pathlib import Path
from typing import TypeAlias

import pytest

from trajcenter.robot.abb.models import (
    ProcessTypeEntry,
    ResolvedPoint,
    ResolvedProcessParam,
    ResolvedProcessParamSet,
    ResolvedRobTarget,
    ResolvedTrajectory,
    RobotContext,
    RobotDefaults,
    TrajectoryStoreEntry,
)

ProcessParamTuple: TypeAlias = tuple[
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
]


def _empty_process_params() -> ProcessParamTuple:
    """Build ten empty process parameter slots.

    ABB Route:
        N/A — local test helper.

    ABB Constraints:
        RAPID ``processParams`` second dimension contains exactly ten slots.

    Args:
        None.

    Returns:
        Tuple of exactly ten empty process parameter slots.


    Example:
        ```python
        params = _empty_process_params()
        ```
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


def _defaults() -> RobotDefaults:
    """Build enabled robot defaults for tests.

    ABB Route:
        N/A — local test helper.

    ABB Constraints:
        No controller access is performed.

    Args:
        None.

    Returns:
        Robot defaults instance.


    Example:
        ```python
        defaults = _defaults()
        ```
    """
    return RobotDefaults(
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
    )


def _robtarget() -> ResolvedRobTarget:
    """Build a resolved robtarget for tests.

    ABB Route:
        N/A — local test helper.

    ABB Constraints:
        External axes are represented by ``None`` before RWS serialization.

    Args:
        None.

    Returns:
        Resolved robtarget.


    Example:
        ```python
        robtarget = _robtarget()
        ```
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
        cf4=0,
        cf6=0,
        cfx=0,
        eax=(None, None, None, None, None, None),
    )


def _point() -> ResolvedPoint:
    """Build a resolved point for tests.

    ABB Route:
        N/A — local test helper.

    ABB Constraints:
        Indexes are already RAPID base-1 indexes.

    Args:
        None.

    Returns:
        Resolved point.


    Example:
        ```python
        point = _point()
        ```
    """
    return ResolvedPoint(
        move_type=0,
        robtarget=_robtarget(),
        tcp_speed=500.0,
        zone_type=10,
        read_confs=True,
        tool_index=1,
        wobj_index=1,
        process_param_index=0,
    )


class TestRobotDefaults:
    """Tests for :class:`trajcenter.robot.abb.models.RobotDefaults`."""

    def test_enabled_defaults(self) -> None:
        """Enabled defaults store values exactly."""
        defaults = _defaults()

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

    def test_disabled_defaults(self) -> None:
        """Disabled optional defaults may store ``None`` values."""
        defaults = RobotDefaults(
            has_tcp_speed=False,
            tcp_speed=None,
            has_zone_type=False,
            zone_type=None,
            has_tool_name=False,
            tool_name=None,
            has_wobj_name=False,
            wobj_name=None,
            move_type=1,
            read_confs=False,
        )

        assert defaults.tcp_speed is None
        assert defaults.zone_type is None
        assert defaults.tool_name is None
        assert defaults.wobj_name is None
        assert defaults.move_type == 1
        assert defaults.read_confs is False


class TestProcessTypeEntry:
    """Tests for :class:`trajcenter.robot.abb.models.ProcessTypeEntry`."""

    def test_process_type_entry(self) -> None:
        """A process catalog entry stores id and name."""
        entry = ProcessTypeEntry(id=1, name="ACF")

        assert entry.id == 1
        assert entry.name == "ACF"


class TestRobotContext:
    """Tests for :class:`trajcenter.robot.abb.models.RobotContext`."""

    def test_tool_index_by_name_is_one_based(self) -> None:
        """Tool lookup returns RAPID base-1 indexes."""
        context = RobotContext(
            defaults=_defaults(),
            tool_names=("tool_a", "tool_b"),
            wobj_names=("wobj_a",),
            process_types=(ProcessTypeEntry(id=0, name="NONE"),),
        )

        assert context.tool_index_by_name == {"tool_a": 1, "tool_b": 2}

    def test_wobj_index_by_name_is_one_based(self) -> None:
        """Workobject lookup returns RAPID base-1 indexes."""
        context = RobotContext(
            defaults=_defaults(),
            tool_names=("tool_a",),
            wobj_names=("wobj_a", "wobj_b"),
            process_types=(ProcessTypeEntry(id=0, name="NONE"),),
        )

        assert context.wobj_index_by_name == {"wobj_a": 1, "wobj_b": 2}

    def test_process_ids(self) -> None:
        """Process ids are collected from robot catalog entries."""
        context = RobotContext(
            defaults=_defaults(),
            tool_names=("tool_a",),
            wobj_names=("wobj_a",),
            process_types=(
                ProcessTypeEntry(id=0, name="NONE"),
                ProcessTypeEntry(id=1, name="ACF"),
                ProcessTypeEntry(id=3, name="PUSHCORP"),
            ),
        )

        assert context.process_ids == frozenset({0, 1, 3})


class TestResolvedRobTarget:
    """Tests for :class:`trajcenter.robot.abb.models.ResolvedRobTarget`."""

    def test_resolved_robtarget(self) -> None:
        """Robtarget components are stored without RWS sentinel injection."""
        robtarget = _robtarget()

        assert robtarget.x == 100.0
        assert robtarget.y == 200.0
        assert robtarget.z == 300.0
        assert robtarget.q1 == 1.0
        assert robtarget.cf1 == 0
        assert robtarget.eax == (None, None, None, None, None, None)

    def test_resolved_robtarget_with_external_axis(self) -> None:
        """Active external axis values are represented as floats."""
        robtarget = ResolvedRobTarget(
            x=0.0,
            y=0.0,
            z=0.0,
            q1=1.0,
            q2=0.0,
            q3=0.0,
            q4=0.0,
            cf1=0,
            cf4=0,
            cf6=0,
            cfx=0,
            eax=(45.0, None, None, None, None, None),
        )

        assert robtarget.eax[0] == 45.0
        assert robtarget.eax[1:] == (None, None, None, None, None)


class TestResolvedProcessParamSet:
    """Tests for :class:`trajcenter.robot.abb.models.ResolvedProcessParamSet`."""

    def test_valid_process_param_set(self) -> None:
        """A parameter set must contain exactly ten slots."""
        param_set = ResolvedProcessParamSet(index=1, params=_empty_process_params())

        assert param_set.index == 1
        assert len(param_set.params) == 10
        assert param_set.params[0].name == ""
        assert param_set.params[0].value == 0.0

    def test_invalid_process_param_set_size_raises(self) -> None:
        """A parameter set with fewer than ten slots is invalid."""
        empty = ResolvedProcessParam(name="", value=0.0)

        with pytest.raises(ValueError, match="exactly 10"):
            ResolvedProcessParamSet(
                index=1,
                params=(empty,),  # pyright: ignore[reportArgumentType]
            )

    def test_named_process_params(self) -> None:
        """Named process params store names and numeric values."""
        empty = ResolvedProcessParam(name="", value=0.0)
        force = ResolvedProcessParam(name="force", value=120.0)
        feed = ResolvedProcessParam(name="feed", value=5.0)

        param_set = ResolvedProcessParamSet(
            index=1,
            params=(
                feed,
                force,
                empty,
                empty,
                empty,
                empty,
                empty,
                empty,
                empty,
                empty,
            ),
        )

        assert param_set.params[0] == feed
        assert param_set.params[1] == force


class TestResolvedPoint:
    """Tests for :class:`trajcenter.robot.abb.models.ResolvedPoint`."""

    def test_resolved_point(self) -> None:
        """A resolved point stores all RAPID record fields."""
        point = _point()

        assert point.move_type == 0
        assert point.robtarget.x == 100.0
        assert point.tcp_speed == 500.0
        assert point.zone_type == 10
        assert point.read_confs is True
        assert point.tool_index == 1
        assert point.wobj_index == 1
        assert point.process_param_index == 0


class TestResolvedTrajectory:
    """Tests for :class:`trajcenter.robot.abb.models.ResolvedTrajectory`."""

    def test_resolved_trajectory_without_process(self) -> None:
        """A trajectory without process has zero parameter sets."""
        point = _point()
        trajectory = ResolvedTrajectory(
            name="demo",
            process_type=0,
            points=(point,),
            process_param_sets=(),
        )

        assert trajectory.name == "demo"
        assert trajectory.process_type == 0
        assert trajectory.point_count == 1
        assert trajectory.process_param_sets == ()

    def test_resolved_trajectory_with_process(self) -> None:
        """A trajectory with process references parameter sets."""
        param_set = ResolvedProcessParamSet(index=1, params=_empty_process_params())
        point = ResolvedPoint(
            move_type=0,
            robtarget=_robtarget(),
            tcp_speed=500.0,
            zone_type=10,
            read_confs=True,
            tool_index=1,
            wobj_index=1,
            process_param_index=1,
        )
        trajectory = ResolvedTrajectory(
            name="with_process",
            process_type=1,
            points=(point,),
            process_param_sets=(param_set,),
        )

        assert trajectory.point_count == 1
        assert trajectory.process_type == 1
        assert trajectory.process_param_sets[0].index == 1


class TestTrajectoryStoreEntry:
    """Tests for :class:`trajcenter.robot.abb.models.TrajectoryStoreEntry`."""

    def test_store_entry(self) -> None:
        """A store entry maps one-based index to a trajectory archive path."""
        entry = TrajectoryStoreEntry(
            index=1,
            path=Path("trajectory_store/demo.trajcenter"),
            name="demo",
            point_count=10,
            process_type=0,
        )

        assert entry.index == 1
        assert entry.path == Path("trajectory_store/demo.trajcenter")
        assert entry.name == "demo"
        assert entry.point_count == 10
        assert entry.process_type == 0
