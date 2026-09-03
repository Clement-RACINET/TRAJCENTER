#!/usr/bin/env python3
# scripts/run_trajcenter_supervisor.py
"""Run the TrajCenter v2 RWS subscription supervisor.

Author: Clement RACINET

This script connects to an ABB RobotWare 6 controller through the
``abb-rws-client-python-rw6`` client and starts the event-driven TrajCenter
supervisor.

ABB Route:
    Subscription setup:
        ``POST /subscription``

    WebSocket event stream:
        ``robapi2_subscription`` subprotocol

    Subscription teardown:
        ``DELETE /subscription/{group-id}``

    Service writes:
        Delegated to ``trajcenter.robot.abb.service`` and ``trajcenter.robot.abb.writer``.

ABB Constraints:
    - No TCP v1 server is used.
    - Request handling is event-driven through RWS WebSocket subscriptions.
    - The supervisor watches ``refreshMetaRequest`` and ``sendTrajRequest``.
    - RAPID writes are performed only by the service/writer stack under
      Mastership.
    - Subscription cleanup is guaranteed by the supervisor through
      ``contextlib.aclosing``.

Example:
    From the repository root:

    ::

        python scripts/run_trajcenter_supervisor.py --store trajectory_store
"""

from __future__ import annotations

import argparse
import asyncio
import signal
from pathlib import Path

from abb_rws_client_python_rw6 import configure_logging, load_env
from abb_rws_client_python_rw6.core.client import RWSClient
from abb_rws_client_python_rw6.core.exceptions import RWSError

from trajcenter.core.logger import get_logger
from trajcenter.robot.abb.constants import DEFAULT_TASK, TRAJCENTER_MODULE
from trajcenter.robot.abb.supervisor import (
    RWSSupervisorConfig,
    run_rws_subscription_supervisor,
)

logger = get_logger(__name__)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments.

    ABB Route:
        N/A — local CLI parser.

    ABB Constraints:
        ``task`` and ``module`` must match the RAPID module containing
        ``refreshMetaRequest`` and ``sendTrajRequest``.

    Args:
        None.

    Returns:
        Parsed command-line namespace.

    Raises:
        SystemExit: If arguments are invalid.

    Example:
        ::

            args = parse_args()
    """
    parser = argparse.ArgumentParser(
        description="Run TrajCenter v2 RWS subscription supervisor.",
    )
    parser.add_argument(
        "--store",
        type=Path,
        required=True,
        help="Directory containing local .trajcenter archives.",
    )
    parser.add_argument(
        "--task",
        default=DEFAULT_TASK,
        help=f"RAPID task name. Default: {DEFAULT_TASK}.",
    )
    parser.add_argument(
        "--module",
        default=TRAJCENTER_MODULE,
        help=f"RAPID module name. Default: {TRAJCENTER_MODULE}.",
    )
    parser.add_argument(
        "--mastership-retries",
        type=int,
        default=3,
        help="Number of Mastership retry attempts for writer operations.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"),
        help="Logging level.",
    )
    return parser.parse_args()


async def async_main() -> int:
    """Run the asynchronous supervisor entry point.

    ABB Route:
        Connects to RWS and delegates subscription handling to
        ``run_rws_subscription_supervisor``.

    ABB Constraints:
        Ctrl+C requests a graceful stop. The underlying supervisor closes the
        RWS subscription generator, which deletes the ABB subscription group.

    Args:
        None.

    Returns:
        Process exit code.


    Example:
        ::

            raise SystemExit(asyncio.run(async_main()))
    """
    args = parse_args()

    load_env()
    configure_logging(args.log_level)

    stop_event = asyncio.Event()

    def request_stop(*_: object) -> None:
        """Request a graceful supervisor stop from OS signal handlers.

        ABB Route:
            N/A — local signal handler.

        ABB Constraints:
            The handler only sets an ``asyncio.Event``. Cleanup is performed by
            the supervisor.

        Args:
            *_: Ignored signal arguments.

        Returns:
            None.


        Example:
            ::

                signal.signal(signal.SIGINT, request_stop)
        """
        logger.info("Stop requested.")
        stop_event.set()

    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)

    config = RWSSupervisorConfig(
        store_root=args.store,
        task=args.task,
        module=args.module,
        mastership_retries=args.mastership_retries,
    )

    try:
        async with RWSClient() as client:
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


def main() -> None:
    """Run the synchronous script wrapper.

    ABB Route:
        N/A — local process entry point.

    ABB Constraints:
        The process runs one asyncio event loop.

    Args:
        None.

    Returns:
        None.

    Raises:
        SystemExit: With the exit code returned by ``async_main``.

    Example:
        ::

            main()
    """
    raise SystemExit(asyncio.run(async_main()))


if __name__ == "__main__":
    main()
