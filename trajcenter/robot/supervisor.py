#!/usr/bin/env python3
# trajcenter/robot/abb/supervisor.py
"""RWS subscription supervisor for TrajCenter v2.

Author: Clement RACINET

This module runs the event-driven TrajCenter RWS supervisor. It subscribes to
RAPID persistent request flags and dispatches high-level service operations
without polling and without using the obsolete TCP v1 protocol.

ABB Route:
    Subscription setup:
        ``POST /subscription``

    WebSocket event stream:
        ``robapi2_subscription`` subprotocol

    Subscription teardown:
        ``DELETE /subscription/{group-id}``

ABB Constraints:
    - The supervisor watches RAPID PERS variables from
      ``TRAJCENTER``.
    - ``refreshMetaRequest == TRUE`` refreshes robot-side trajectory metadata.
    - ``sendTrajRequest == TRUE`` transfers the selected trajectory.
    - RAPID writes are delegated to service/writer layers only.
    - Mastership acquisition and release are handled by writer-level helpers.
"""

from __future__ import annotations

import asyncio
import contextlib
import signal
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from abb_rws_client_python_rw6 import RWSClient, configure_logging, load_env
from abb_rws_client_python_rw6.core.exceptions import RWSError
from abb_rws_client_python_rw6.highlevel.subscription import (
    SubscribedResource,
    SubscriptionPriority,
    build_rapid_pers_resource_uri,
    watch_resources,
)

from trajcenter.core.logger import get_logger
from trajcenter.robot.constants import DEFAULT_TASK, TRAJCENTER_MODULE
from trajcenter.robot.models import TrajectoryStoreEntry
from trajcenter.robot.service import (
    refresh_store_metadata,
    transfer_selected_trajectory,
)

logger = get_logger(__name__)


@dataclass(slots=True)
class RWSSupervisorConfig:
    """Configuration for the TrajCenter RWS subscription supervisor.

    ABB Route:
        N/A — local supervisor configuration.

    ABB Constraints:
        ``task`` and ``module`` must match the RAPID module declaring
        ``refreshMetaRequest`` and ``sendTrajRequest``.

    Args:
        store_root: Directory containing local ``.trajcenter`` archives.
        task: RAPID task name.
        module: RAPID module name containing TrajCenter web-service variables.
        mastership_retries: Number of retries used by service write operations.
        refresh_priority: ABB subscription priority for metadata refresh flag.
        transfer_priority: ABB subscription priority for transfer request flag.


    Example:
        ::

            config = RWSSupervisorConfig(store_root=Path("trajectory_store"))
    """

    store_root: Path
    task: str = DEFAULT_TASK
    module: str = TRAJCENTER_MODULE
    mastership_retries: int = 3
    refresh_priority: SubscriptionPriority = "1"
    transfer_priority: SubscriptionPriority = "1"


@dataclass(slots=True)
class RWSSupervisorState:
    """Mutable state kept by the RWS subscription supervisor.

    ABB Route:
        N/A — local runtime state.

    ABB Constraints:
        ``entries`` must match the last metadata order written to RAPID because
        ``selectedTrajIndex`` maps directly to this local tuple.

    Args:
        entries: Last known local trajectory store entries.
        refresh_count: Number of metadata refresh operations completed.
        transfer_count: Number of trajectory transfer operations completed.


    Example:
        ::

            state = RWSSupervisorState()
    """

    entries: tuple[TrajectoryStoreEntry, ...] = field(default_factory=tuple)
    refresh_count: int = 0
    transfer_count: int = 0


def build_trajcenter_subscription_resources(
    config: RWSSupervisorConfig,
) -> tuple[SubscribedResource, SubscribedResource]:
    """Build RWS subscription resources for TrajCenter request flags.

    ABB Route:
        Resource URIs are consumed by ``POST /subscription``.

    ABB Constraints:
        The watched RAPID variables are expected to be persistent variables:

        - ``refreshMetaRequest``
        - ``sendTrajRequest``

    Args:
        config: Supervisor configuration.

    Returns:
        Tuple containing refresh and transfer subscription resources.


    Example:
        ::

            resources = build_trajcenter_subscription_resources(config)
    """
    return (
        SubscribedResource(
            name="refreshMetaRequest",
            resource_uri=build_rapid_pers_resource_uri(
                config.task,
                config.module,
                "refreshMetaRequest",
            ),
            priority=config.refresh_priority,
        ),
        SubscribedResource(
            name="sendTrajRequest",
            resource_uri=build_rapid_pers_resource_uri(
                config.task,
                config.module,
                "sendTrajRequest",
            ),
            priority=config.transfer_priority,
        ),
    )


async def handle_supervisor_event(
    client: RWSClient,
    config: RWSSupervisorConfig,
    state: RWSSupervisorState,
    name: str,
    value: str,
) -> None:
    """Handle one TrajCenter subscription event.

    ABB Route:
        Event payload comes from the active RWS WebSocket subscription.

    ABB Constraints:
        Only ``TRUE`` request events trigger actions. ``FALSE`` events are
        ignored because they usually correspond to writer-side acknowledgement
        resets.

    Args:
        client: Open RWS client.
        config: Supervisor configuration.
        state: Mutable supervisor state.
        name: Subscription resource name.
        value: Raw event value.

    Returns:
        None.

    Raises:
        ValueError: If a transfer is requested before metadata has been loaded.
        MastershipDenied: If service-level writes cannot acquire Mastership.
        RWSHTTPError: On unexpected controller HTTP errors.

    Example:
        ::

            await handle_supervisor_event(
                client,
                config,
                state,
                "refreshMetaRequest",
                "TRUE",
            )
    """
    if not _is_true_event(value):
        logger.debug("Ignoring subscription event %s=%s", name, value)
        return

    if name == "refreshMetaRequest":
        logger.info("Received refreshMetaRequest=TRUE")
        state.entries = await refresh_store_metadata(
            client,
            config.store_root,
            task=config.task,
            module=config.module,
            mastership_retries=config.mastership_retries,
        )
        state.refresh_count += 1
        return

    if name == "sendTrajRequest":
        logger.info("Received sendTrajRequest=TRUE")
        if not state.entries:
            raise ValueError(
                "Cannot transfer selected trajectory before store metadata "
                "has been refreshed"
            )

        await transfer_selected_trajectory(
            client,
            state.entries,
            task=config.task,
            module=config.module,
            mastership_retries=config.mastership_retries,
        )
        state.transfer_count += 1
        return

    logger.debug("Ignoring unknown TrajCenter subscription event: %s=%s", name, value)


async def run_rws_subscription_supervisor(
    client: RWSClient,
    config: RWSSupervisorConfig,
    *,
    state: RWSSupervisorState | None = None,
    stop_event: asyncio.Event | None = None,
) -> RWSSupervisorState:
    """Run the event-driven TrajCenter RWS subscription supervisor.

    ABB Route:
        Uses ``watch_resources`` from ``abb_rws_client_python_rw6``:

        - creates one RWS subscription group;
        - consumes WebSocket events;
        - deletes the subscription group when the async generator is closed.

    ABB Constraints:
        ``contextlib.aclosing`` is mandatory here to guarantee subscription
        cleanup on cancellation or stop request. ABB controllers allow only a
        small number of active subscription groups per client.

        The supervisor must stop even when no RWS event is received. Therefore
        the event loop waits concurrently for either:

        - the next WebSocket subscription event;
        - the local ``stop_event``.

    Args:
        client: Open RWS client.
        config: Supervisor configuration.
        state: Optional existing supervisor state.
        stop_event: Optional async event used to stop the supervisor.

    Returns:
        Final supervisor state.

    Raises:
        MastershipDenied: If service-level writes cannot acquire Mastership.
        RWSHTTPError: On unexpected controller HTTP errors.
        ValueError: If a transfer is requested before metadata refresh.

    Example:
        ::

            state = await run_rws_subscription_supervisor(client, config)
    """
    supervisor_state = state if state is not None else RWSSupervisorState()
    resources = build_trajcenter_subscription_resources(config)

    logger.info(
        "Starting TrajCenter RWS subscription supervisor on %s/%s",
        config.task,
        config.module,
    )

    async with contextlib.aclosing(watch_resources(client, resources)) as events:
        if stop_event is None:
            async for name, value in events:
                await handle_supervisor_event(
                    client,
                    config,
                    supervisor_state,
                    name,
                    value,
                )
        else:
            while not stop_event.is_set():
                event_task: asyncio.Task[tuple[str, str]] = asyncio.create_task(
                    anext(events),
                )
                stop_task: asyncio.Task[bool] = asyncio.create_task(
                    stop_event.wait(),
                )

                done, _pending = await asyncio.wait(
                    (event_task, stop_task),
                    return_when=asyncio.FIRST_COMPLETED,
                )

                if stop_task in done:
                    logger.info("Stop event received by RWS supervisor.")
                    await _cancel_task_safely(event_task)
                    break

                await _cancel_task_safely(stop_task)

                try:
                    name, value = event_task.result()
                except StopAsyncIteration:
                    logger.info("RWS subscription event stream closed.")
                    break

                await handle_supervisor_event(
                    client,
                    config,
                    supervisor_state,
                    name,
                    value,
                )

    logger.info(
        "TrajCenter RWS subscription supervisor stopped: %d refresh, %d transfer",
        supervisor_state.refresh_count,
        supervisor_state.transfer_count,
    )
    return supervisor_state


async def run_rws_subscription_supervisor_app(
    *,
    store_root: Path,
    task: str = DEFAULT_TASK,
    module: str = TRAJCENTER_MODULE,
    mastership_retries: int = 3,
    log_level: str = "INFO",
    env_file: Path | None = None,
    env_override: bool = False,
    host: str | None = None,
    username: str | None = None,
    password: str | None = None,
    port: int | None = None,
    timeout: float | None = None,
) -> int:
    """Run the complete TrajCenter RWS supervisor application.

    ABB Route:
        Connects to RWS and delegates subscription handling to
        ``run_rws_subscription_supervisor``.

    ABB Constraints:
        Ctrl+C requests a graceful stop. The underlying supervisor closes the
        RWS subscription generator, which deletes the ABB subscription group.

        Connection parameters are loaded by ``abb_rws_client_python_rw6`` from
        its environment configuration through ``load_env()``.

    Args:
        store_root: Directory containing local ``.trajcenter`` archives.
        task: RAPID task name.
        module: RAPID module name.
        mastership_retries: Number of Mastership retry attempts.
        log_level: Logging level passed to the ABB RWS client logging setup.
        env_file: Optional explicit ``.env`` file or directory to load.
        env_override: Whether loaded ``.env`` values override existing environment variables.
        host: Optional ABB RWS controller host override.
        username: Optional ABB RWS username override.
        password: Optional ABB RWS password override.
        port: Optional ABB RWS HTTP port override.
        timeout: Optional ABB RWS request timeout override.


    Returns:
        Process exit code.

    Example:
        ::

            code = await run_rws_subscription_supervisor_app(
                store_root=Path("trajectory_store"),
            )
    """
    load_env(env_file, override=env_override)
    configure_logging(log_level)

    stop_event = asyncio.Event()

    def request_stop(*_: object) -> None:
        """Request a graceful supervisor stop from OS signal handlers."""
        logger.info("Stop requested.")
        stop_event.set()

    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)

    config = RWSSupervisorConfig(
        store_root=store_root,
        task=task,
        module=module,
        mastership_retries=mastership_retries,
    )

    try:
        async with RWSClient(
            host=host,
            username=username,
            password=password,
            port=port,
            timeout=timeout,
        ) as client:
            logger.info("Connected to ABB controller.")
            logger.info("Store root: %s", config.store_root)
            logger.info("Task/module: %s/%s", config.task, config.module)
            await run_rws_subscription_supervisor(
                client,
                config,
                stop_event=stop_event,
            )
        return 0

    except RWSError as exc:
        logger.error("ABB RWS error: %s", exc)
        return 2

    except (FileNotFoundError, NotADirectoryError, ValueError) as exc:
        logger.error("TrajCenter supervisor error: %s", exc)
        return 1


async def _cancel_task_safely(task: asyncio.Task[Any]) -> None:
    """Cancel an asyncio task and wait for its cancellation.

    ABB Route:
        N/A — local asyncio cleanup helper.

    ABB Constraints:
        This helper is used during supervisor shutdown to avoid leaving a
        pending WebSocket receive task alive after ``stop_event`` has been set.

    Args:
        task: Task to cancel.

    Returns:
        None.

    Example:
        ::

            await _cancel_task_safely(pending_task)
    """
    if task.done():
        return

    task.cancel()

    with contextlib.suppress(asyncio.CancelledError):
        await task


def _is_true_event(value: str) -> bool:
    """Return whether a raw subscription value represents RAPID ``TRUE``.

    ABB Route:
        N/A — local event parser.

    ABB Constraints:
        ABB bool values are expected as ``TRUE`` or ``FALSE`` text, but this
        parser accepts lowercase variants defensively.

    Args:
        value: Raw event value.

    Returns:
        ``True`` if the value is ``TRUE``.


    Example:
        ::

            assert _is_true_event("TRUE")
    """
    return value.strip().upper() == "TRUE"
