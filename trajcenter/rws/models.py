#!/usr/bin/env python3
# trajcenter/rws/models.py
"""Typed models for TrajCenter ABB RWS transfer operations.

Author: Clement RACINET

This module defines the internal data structures exchanged between the RWS
reader, resolver, writer, store scanner and service orchestrator.

The goal is to keep pandas DataFrames and local .trajcenter archive details out
of the writer. The writer only receives already validated and resolved payloads.

ABB Route:
    N/A — local data models only.

ABB Constraints:
    - RAPID arrays are one-based.
    - toolIndex, wobjIndex and processParamIndex use base-1 indexing.
    - processParamIndex = 0 means no process parameters.
    - External axis inactive sentinel 9E+9 is injected only during RWS
      serialization, never stored in .trajcenter archives.

Example:
    ```python
    point = ResolvedPoint(
        move_type=0,
        robtarget=ResolvedRobTarget(
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
        ),
        tcp_speed=500.0,
        zone_type=10,
        read_confs=True,
        tool_index=1,
        wobj_index=1,
        process_param_index=0,
    )
    ```
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from trajcenter.rws.constants import MAX_PROCESS_PARAM_PER_SET


@dataclass(frozen=True, slots=True)
class RobotDefaults:
    """Robot-side default values read from ``TRAJCENTER``.

    ABB Route:
        ``GET /rw/rapid/symbol/data/RAPID/{task}/TRAJCENTER/{var}``.

    ABB Constraints:
        Defaults may only be applied when the corresponding ``hasDefault*``
        flag is ``TRUE``. The PC must not invent speed, zone, tool or wobj.

    Args:
        has_tcp_speed: Whether ``defaultTcpSpeed`` is valid.
        tcp_speed: Default TCP speed in mm/s, or ``None``.
        has_zone_type: Whether ``defaultZoneType`` is valid.
        zone_type: Default zone type, or ``None``.
        has_tool_name: Whether ``defaultToolName`` is valid.
        tool_name: Default tool name, or ``None``.
        has_wobj_name: Whether ``defaultWobjName`` is valid.
        wobj_name: Default workobject name, or ``None``.
        move_type: Default movement type code.
        read_confs: Default ``readConfs`` value.


    Example:
        ```python
        defaults = RobotDefaults(
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
        ```
    """

    has_tcp_speed: bool
    tcp_speed: float | None
    has_zone_type: bool
    zone_type: int | None
    has_tool_name: bool
    tool_name: str | None
    has_wobj_name: bool
    wobj_name: str | None
    move_type: int
    read_confs: bool


@dataclass(frozen=True, slots=True)
class ProcessTypeEntry:
    """One robot-side process catalog entry.

    ABB Route:
        Parsed from ``TRAJCENTER/processTypes{i}``.

    ABB Constraints:
        RAPID record layout is ``[num id, string name]``.

    Args:
        id: Numeric process type identifier.
        name: Human-readable process name.



    Example:
        ```python
        entry = ProcessTypeEntry(id=1, name="ACF")
        ```
    """

    id: int
    name: str


@dataclass(frozen=True, slots=True)
class RobotContext:
    """Robot-side context required to resolve a trajectory before transfer.

    ABB Route:
        Built from multiple RWS reads:
        - defaults in ``TRAJCENTER``;
        - tools in ``TRAJCENTER/trajTools``;
        - wobjs in ``TRAJCENTER/trajWobjs``;
        - process catalog in ``TRAJCENTER/processTypes``.

    ABB Constraints:
        ``tool_names`` and ``wobj_names`` are ordered lists. Python index
        ``0`` corresponds to RAPID index ``1``.

    Args:
        defaults: Robot defaults.
        tool_names: Ordered tool names from ``trajTools``.
        wobj_names: Ordered workobject names from ``trajWobjs``.
        process_types: Robot process catalog.


    Example:
        ```python
        context = RobotContext(
            defaults=defaults,
            tool_names=("tool0",),
            wobj_names=("wobj0",),
            process_types=(ProcessTypeEntry(id=0, name="NONE"),),
        )
        ```
    """

    defaults: RobotDefaults
    tool_names: tuple[str, ...]
    wobj_names: tuple[str, ...]
    process_types: tuple[ProcessTypeEntry, ...]

    @property
    def tool_index_by_name(self) -> dict[str, int]:
        """Return ``tool_name -> RAPID base-1 index`` mapping.

        ABB Route:
            N/A — local lookup.

        ABB Constraints:
            RAPID array indexes are one-based.


        Returns:
            Mapping of tool name to RAPID index.


        Example:
            ```python
            assert context.tool_index_by_name["tool0"] == 1
            ```
        """
        return {name: index for index, name in enumerate(self.tool_names, start=1)}

    @property
    def wobj_index_by_name(self) -> dict[str, int]:
        """Return ``wobj_name -> RAPID base-1 index`` mapping.

        ABB Route:
            N/A — local lookup.

        ABB Constraints:
            RAPID array indexes are one-based.


        Returns:
            Mapping of workobject name to RAPID index.


        Example:
            ```python
            assert context.wobj_index_by_name["wobj0"] == 1
            ```
        """
        return {name: index for index, name in enumerate(self.wobj_names, start=1)}

    @property
    def process_ids(self) -> frozenset[int]:
        """Return process ids declared by the robot catalog.

        ABB Route:
            N/A — local lookup.

        ABB Constraints:
            The robot catalog is authoritative.


        Returns:
            Set of process ids.


        Example:
            ```python
            assert 0 in context.process_ids
            ```
        """
        return frozenset(entry.id for entry in self.process_types)


@dataclass(frozen=True, slots=True)
class ResolvedRobTarget:
    """Resolved robtarget components ready for RWS serialization.

    ABB Route:
        Serialized by writer for ``trajData{i}``.

    ABB Constraints:
        ``eax`` stores ``None`` for inactive external axes. The writer injects
        ``9E+9`` only during RWS serialization.

    Args:
        x: X coordinate in mm.
        y: Y coordinate in mm.
        z: Z coordinate in mm.
        q1: ABB quaternion component ``w``.
        q2: ABB quaternion component ``x``.
        q3: ABB quaternion component ``y``.
        q4: ABB quaternion component ``z``.
        cf1: ABB confdata cf1.
        cf4: ABB confdata cf4.
        cf6: ABB confdata cf6.
        cfx: ABB confdata cfx.
        eax: Six optional external axis values. ``None`` means inactive.



    Example:
        ```python
        robtarget = ResolvedRobTarget(
            x=100.0,
            y=0.0,
            z=500.0,
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
        ```
    """

    x: float
    y: float
    z: float
    q1: float
    q2: float
    q3: float
    q4: float
    cf1: int
    cf4: int
    cf6: int
    cfx: int
    eax: tuple[
        float | None,
        float | None,
        float | None,
        float | None,
        float | None,
        float | None,
    ]


@dataclass(frozen=True, slots=True)
class ResolvedProcessParam:
    """One resolved process parameter slot.

    ABB Route:
        Written to ``TRAJCENTER/processParams{i,j}``.

    ABB Constraints:
        RAPID record layout is ``[string name, num value]``.
        Empty name means unused slot.

    Args:
        name: Parameter name, or ``""`` for unused slot.
        value: Numeric parameter value.



    Example:
        ```python
        param = ResolvedProcessParam(name="force", value=120.0)
        ```
    """

    name: str
    value: float


@dataclass(frozen=True, slots=True)
class ResolvedProcessParamSet:
    """One resolved process parameter set.

    ABB Route:
        Written to ``processParams{index,1..10}``.

    ABB Constraints:
        ``index`` is base-1 in RAPID and must be in ``1..256``.
        ``params`` must contain exactly 10 slots. Unused slots are
        represented by ``ResolvedProcessParam(name="", value=0.0)``.

    Args:
        index: RAPID base-1 process parameter set index.
        params: Ten ordered parameter slots.


    Raises:
        ValueError: If ``params`` does not contain exactly 10 entries.

    Example:
        ```python
        empty = ResolvedProcessParam(name="", value=0.0)
        param_set = ResolvedProcessParamSet(index=1, params=(empty,) * 10)
        ```
    """

    index: int
    params: tuple[
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

    def __post_init__(self) -> None:
        """Validate process parameter set shape.

        ABB Route:
            N/A — local validation.

        ABB Constraints:
            RAPID second dimension is fixed to 10.


        Returns:
            None.

        Raises:
            ValueError: If the parameter count is not exactly 10.

        Example:
            ```python
            ResolvedProcessParamSet(index=1, params=(empty,) * 10)
            ```
        """
        if len(self.params) != MAX_PROCESS_PARAM_PER_SET:
            raise ValueError(
                "ResolvedProcessParamSet.params must contain exactly "
                f"{MAX_PROCESS_PARAM_PER_SET} entries"
            )


@dataclass(frozen=True, slots=True)
class ResolvedPoint:
    """One trajectory point resolved for RAPID transfer.

    ABB Route:
        Written to ``TRAJCENTER/trajData{i}``.

    ABB Constraints:
        RAPID record layout:
        ``[moveType, robtarget, tcpSpeed, zoneType, readConfs, toolIndex,
        wobjIndex, processParamIndex]``.

    Args:
        move_type: RAPID movement type code.
        robtarget: Resolved robtarget.
        tcp_speed: TCP speed in mm/s.
        zone_type: ABB zone code.
        read_confs: Whether RAPID must use confdata.
        tool_index: Base-1 index in ``trajTools``.
        wobj_index: Base-1 index in ``trajWobjs``.
        process_param_index: Base-1 index in ``processParams`` or ``0``.



    Example:
        ```python
        point = ResolvedPoint(
            move_type=0,
            robtarget=robtarget,
            tcp_speed=500.0,
            zone_type=10,
            read_confs=True,
            tool_index=1,
            wobj_index=1,
            process_param_index=0,
        )
        ```
    """

    move_type: int
    robtarget: ResolvedRobTarget
    tcp_speed: float
    zone_type: int
    read_confs: bool
    tool_index: int
    wobj_index: int
    process_param_index: int


@dataclass(frozen=True, slots=True)
class ResolvedTrajectory:
    """Full trajectory payload resolved for RWS transfer.

    ABB Route:
        Written to:
        - ``nbLoadedTrajPoints``;
        - ``processParams{1..256,1..10}``;
        - ``trajData{1..nbLoadedTrajPoints}``.

    ABB Constraints:
        ``points`` must not exceed ``maxTrajPointCount``.
        ``process_param_sets`` contains only used sets; the writer may clear
        unused RAPID slots depending on transfer policy.

    Args:
        name: Display name.
        process_type: Numeric process type.
        points: Resolved point sequence.
        process_param_sets: Resolved process parameter sets.



    Example:
        ```python
        resolved = ResolvedTrajectory(
            name="demo",
            process_type=0,
            points=(point,),
            process_param_sets=(),
        )
        ```
    """

    name: str
    process_type: int
    points: tuple[ResolvedPoint, ...]
    process_param_sets: tuple[ResolvedProcessParamSet, ...]

    @property
    def point_count(self) -> int:
        """Return number of resolved points.

        ABB Route:
            N/A — local property.

        ABB Constraints:
            This value is written to ``nbLoadedTrajPoints``.


        Returns:
            Number of points.


        Example:
            ```python
            assert resolved.point_count == len(resolved.points)
            ```
        """
        return len(self.points)


@dataclass(frozen=True, slots=True)
class TrajectoryStoreEntry:
    """One trajectory file discovered in the local PC store.

    ABB Route:
        N/A — local filesystem metadata.

    ABB Constraints:
        ``index`` is one-based and maps directly to ``selectedTrajIndex``.

    Args:
        index: One-based store index.
        path: Path to the ``.trajcenter`` archive.
        name: Display name written into ``trajectories{i}.name``.
        point_count: Number of points written into ``trajectories{i}.pointCount``.
        process_type: Process type written into ``trajectories{i}.processType``.


    Example:
        ```python
        entry = TrajectoryStoreEntry(
            index=1,
            path=Path("trajectory_store/demo.trajcenter"),
            name="demo",
            point_count=10,
            process_type=0,
        )
        ```
    """

    index: int
    path: Path
    name: str
    point_count: int
    process_type: int
