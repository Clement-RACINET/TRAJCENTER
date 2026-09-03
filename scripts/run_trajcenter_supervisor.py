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

import argparse
import asyncio
from pathlib import Path

from trajcenter.robot.abb.constants import DEFAULT_TASK, TRAJCENTER_MODULE
from trajcenter.robot.abb.supervisor import run_rws_subscription_supervisor_app


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
        "--env-file",
        type=Path,
        help="Optional .env file or directory to load before connecting to RWS.",
    )
    parser.add_argument(
        "--env-override",
        action="store_true",
        help="Allow loaded .env values to override existing environment variables.",
    )
    parser.add_argument(
        "--host",
        help="ABB RWS controller host. Overrides RWS_HOST.",
    )
    parser.add_argument(
        "--port",
        type=int,
        help="ABB RWS HTTP port. Overrides RWS_PORT.",
    )
    parser.add_argument(
        "--username",
        help="ABB RWS username. Overrides RWS_USER.",
    )
    parser.add_argument(
        "--password",
        help="ABB RWS password. Overrides RWS_PASSWORD.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        help="ABB RWS request timeout in seconds. Overrides RWS_TIMEOUT.",
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
        Connects to RWS and delegates subscription handling to the package-level
        supervisor application runner.

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

    return await run_rws_subscription_supervisor_app(
        store_root=args.store,
        task=args.task,
        module=args.module,
        mastership_retries=args.mastership_retries,
        log_level=args.log_level,
        env_file=args.env_file,
        env_override=args.env_override,
        host=args.host,
        username=args.username,
        password=args.password,
        port=args.port,
        timeout=args.timeout,
    )


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
