# trajcenter/cli/main.py
"""TrajCenter command line interface.

This module intentionally uses only the Python standard library so that the
base ``trajcenter`` command works without optional CLI dependencies.
"""

from __future__ import annotations

import argparse
import asyncio
import os
from collections.abc import Sequence
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import TYPE_CHECKING

from trajcenter.convert.registry import infer_converter
from trajcenter.core.trajectory import Trajectory
from trajcenter.export.registry import infer_exporter

if TYPE_CHECKING:
    from trajcenter.store.models import TrajectoryStoreEntry
    from trajcenter.ui.config import UIConfig


APP_NAME = "trajcenter"
DEFAULT_STORE = Path("trajectory_store")
ROBOT_OPTIONAL_DEPENDENCY_MESSAGE = (
    "Robot support requires optional dependencies.\n"
    'Install with: pip install "trajcenter[robot]"'
)
TUI_OPTIONAL_DEPENDENCY_MESSAGE = (
    "TUI support requires optional dependencies.\n"
    'Install with: pip install "trajcenter[textual]"'
)


def get_package_version() -> str:
    """Return the installed TrajCenter package version.

    Returns:
        Installed package version, or ``unknown`` if package metadata cannot be
        found.
    """
    try:
        return version("trajcenter")
    except PackageNotFoundError:
        return "unknown"


def build_parser() -> argparse.ArgumentParser:
    """Build the TrajCenter command-line parser.

    Returns:
        Configured argument parser.
    """
    parser = argparse.ArgumentParser(
        prog=APP_NAME,
        description="TrajCenter command line interface.",
    )

    subparsers = parser.add_subparsers(
        dest="command",
        metavar="COMMAND",
    )

    subparsers.add_parser(
        "version",
        help="Show the installed TrajCenter version.",
        description="Show the installed TrajCenter version.",
    )
    convert_parser = subparsers.add_parser(
        "convert",
        help="Convert a source trajectory file to a .trajcenter archive.",
        description="Convert a source trajectory file to a .trajcenter archive.",
    )
    convert_parser.add_argument(
        "source",
        type=Path,
        help="Source file to convert (.csv, .xlsx, .xlsm, .xls, .apt, .aptsource, .mod).",
    )
    convert_parser.add_argument(
        "dest_dir",
        type=Path,
        help="Destination directory for the produced .trajcenter archive.",
    )
    convert_parser.add_argument(
        "--name",
        help="Optional output archive stem. Defaults to the source file stem.",
    )
    convert_parser.add_argument(
        "--format",
        choices=["csv", "excel", "xlsx", "apt", "rapid", "mod"],
        help="Optional source format override. By default, the format is inferred.",
    )

    export_parser = subparsers.add_parser(
        "export",
        help="Export a .trajcenter archive to CSV or Excel.",
        description="Export a .trajcenter archive to CSV or Excel.",
    )
    export_parser.add_argument(
        "source",
        type=Path,
        help="Source .trajcenter archive.",
    )
    export_parser.add_argument(
        "dest_dir",
        type=Path,
        help="Destination directory for exported files.",
    )
    export_parser.add_argument(
        "--format",
        choices=["csv", "excel", "xlsx"],
        default="csv",
        help="Export format. Default: csv.",
    )
    tui_parser = subparsers.add_parser(
        "tui",
        help="Launch the TrajCenter user interface.",
        description="Launch the TUI.",
    )
    tui_parser.add_argument(
        "--store",
        type=Path,
        default=DEFAULT_STORE,
        help=f"Trajectory store directory. Default: {DEFAULT_STORE}.",
    )
    store_parser = subparsers.add_parser(
        "store",
        help="Inspect local .trajcenter trajectory stores.",
        description="Inspect local .trajcenter trajectory stores.",
    )
    store_subparsers = store_parser.add_subparsers(
        dest="store_command",
        metavar="STORE_COMMAND",
    )
    store_list_parser = store_subparsers.add_parser(
        "list",
        help="List local .trajcenter archives.",
        description="List local .trajcenter archives.",
    )
    store_list_parser.add_argument(
        "--store",
        type=Path,
        default=DEFAULT_STORE,
        help=f"Trajectory store directory. Default: {DEFAULT_STORE}.",
    )
    store_inspect_parser = store_subparsers.add_parser(
        "inspect",
        help="Inspect one local .trajcenter archive by name, filename or index.",
        description="Inspect one local .trajcenter archive by name, filename or index.",
    )
    store_inspect_parser.add_argument(
        "name",
        help=(
            "Trajectory to inspect. Accepts metadata name, archive filename, "
            "archive stem or one-based store index."
        ),
    )
    store_inspect_parser.add_argument(
        "--store",
        type=Path,
        default=DEFAULT_STORE,
        help=f"Trajectory store directory. Default: {DEFAULT_STORE}.",
    )
    robot_parser = subparsers.add_parser(
        "robot",
        help="ABB robot communication commands.",
        description="ABB robot communication commands.",
    )
    robot_subparsers = robot_parser.add_subparsers(
        dest="robot_command",
        metavar="ROBOT_COMMAND",
    )

    robot_subparsers.add_parser(
        "check",
        help="Check that ABB robot support is available.",
        description="Check that ABB robot support is available.",
    )

    robot_supervise_parser = robot_subparsers.add_parser(
        "supervise",
        help="Run the ABB robot supervision loop.",
        description="Run the ABB robot supervision loop.",
    )
    robot_supervise_parser.add_argument(
        "--store",
        type=Path,
        default=DEFAULT_STORE,
        help=f"Trajectory store directory. Default: {DEFAULT_STORE}.",
    )
    robot_supervise_parser.add_argument(
        "--env-file",
        type=Path,
        help="Optional .env file or directory to load before connecting to RWS.",
    )
    robot_supervise_parser.add_argument(
        "--env-override",
        action="store_true",
        help="Allow loaded .env values to override existing environment variables.",
    )
    robot_supervise_parser.add_argument(
        "--host",
        help="ABB RWS controller host. Overrides RWS_HOST.",
    )
    robot_supervise_parser.add_argument(
        "--port",
        type=int,
        help="ABB RWS HTTP port. Overrides RWS_PORT.",
    )
    robot_supervise_parser.add_argument(
        "--username",
        help="ABB RWS username. Overrides RWS_USER.",
    )
    robot_supervise_parser.add_argument(
        "--password",
        help="ABB RWS password. Overrides RWS_PASSWORD.",
    )
    robot_supervise_parser.add_argument(
        "--password-env",
        help="Environment variable containing the ABB RWS password.",
    )
    robot_supervise_parser.add_argument(
        "--timeout",
        type=float,
        help="ABB RWS request timeout in seconds. Overrides RWS_TIMEOUT.",
    )
    robot_supervise_parser.add_argument(
        "--task",
        default="T_ROB1",
        help="RAPID task name. Default: T_ROB1.",
    )
    robot_supervise_parser.add_argument(
        "--module",
        default="TRAJCENTER",
        help="RAPID module name. Default: TRAJCENTER.",
    )
    robot_supervise_parser.add_argument(
        "--mastership-retries",
        type=int,
        default=3,
        help="Number of Mastership retry attempts for writer operations.",
    )
    robot_supervise_parser.add_argument(
        "--log-level",
        default="INFO",
        choices=("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"),
        help="Logging level. Default: INFO.",
    )

    return parser


def format_store_entry(entry: TrajectoryStoreEntry) -> str:
    """Format one trajectory store entry as a compact table row.

    Args:
        entry: Store entry to format.

    Returns:
        Formatted row string.
    """
    return (
        f"{entry.index:>3}  "
        f"{entry.name:<32}  "
        f"{entry.point_count:>6}  "
        f"{entry.process_type:>7}  "
        f"{entry.path.name}"
    )


def print_store_entries(entries: Sequence[TrajectoryStoreEntry]) -> None:
    """Print trajectory store entries as a simple table.

    Args:
        entries: Store entries to print.

    Returns:
        None.
    """
    if not entries:
        print("No .trajcenter archives found.")
        return

    print(f"{'IDX':>3}  {'NAME':<32}  {'POINTS':>6}  {'PROCESS':>7}  FILE")
    print(f"{'-' * 3}  {'-' * 32}  {'-' * 6}  {'-' * 7}  {'-' * 4}")

    for entry in entries:
        print(format_store_entry(entry))


def find_store_entry(
    entries: Sequence[TrajectoryStoreEntry],
    query: str,
) -> TrajectoryStoreEntry:
    """Find one store entry by index, metadata name, filename or stem.

    Args:
        entries: Store entries to search.
        query: User query.

    Returns:
        Matching store entry.

    Raises:
        LookupError: If no entry matches the query or if the query is ambiguous.
    """
    normalized_query = query.casefold()

    if query.isdecimal():
        index = int(query)
        for entry in entries:
            if entry.index == index:
                return entry

    matches = [
        entry
        for entry in entries
        if normalized_query
        in {
            entry.name.casefold(),
            entry.path.name.casefold(),
            entry.path.stem.casefold(),
        }
    ]

    if len(matches) == 1:
        return matches[0]

    if len(matches) > 1:
        names = ", ".join(f"{entry.index}:{entry.name}" for entry in matches)
        raise LookupError(f"Ambiguous trajectory query '{query}': {names}")

    raise LookupError(f"Trajectory not found in store: {query}")


def print_store_entry_details(entry: TrajectoryStoreEntry) -> None:
    """Print detailed information for one store entry.

    Args:
        entry: Store entry to print.

    Returns:
        None.
    """
    print(f"Index:        {entry.index}")
    print(f"Name:         {entry.name}")
    print(f"Point count:  {entry.point_count}")
    print(f"Process type: {entry.process_type}")
    print(f"File:         {entry.path.name}")
    print(f"Path:         {entry.path}")


def handle_convert_command(args: argparse.Namespace) -> int:
    """Run the ``trajcenter convert`` command.

    Args:
        args: Parsed command-line arguments.

    Returns:
        Process exit code.
    """
    try:
        converter = infer_converter(args.source, args.format)
        output = converter.convert_and_save(
            source=args.source,
            dest_dir=args.dest_dir,
            stem=args.name,
        )
    except (FileNotFoundError, OSError, ValueError) as exc:
        print(f"Error: {exc}")
        return 1

    print(f"Created: {output}")
    return 0


def handle_export_command(args: argparse.Namespace) -> int:
    """Run the ``trajcenter export`` command.

    Args:
        args: Parsed command-line arguments.

    Returns:
        Process exit code.
    """
    try:
        trajectory = Trajectory.load(args.source)
        exporter = infer_exporter(args.format)
        output = exporter.export(trajectory, args.dest_dir)
    except (FileNotFoundError, OSError, ValueError) as exc:
        print(f"Error: {exc}")
        return 1

    print(f"Exported: {output}")
    return 0


def handle_store_command(args: argparse.Namespace) -> int:
    """Run a ``trajcenter store`` subcommand.

    Args:
        args: Parsed command-line arguments.

    Returns:
        Process exit code.
    """
    if args.store_command is None:
        print("Missing store command. Use: trajcenter store --help")
        return 2

    try:
        from trajcenter.store.local import scan_trajectory_store
    except ImportError as exc:
        print(ROBOT_OPTIONAL_DEPENDENCY_MESSAGE)
        print(f"Import error: {exc}")
        return 1

    try:
        entries = scan_trajectory_store(args.store)
    except (FileNotFoundError, NotADirectoryError, ValueError) as exc:
        print(f"Error: {exc}")
        return 1

    if args.store_command == "list":
        print_store_entries(entries)
        return 0

    if args.store_command == "inspect":
        try:
            entry = find_store_entry(entries, args.name)
        except LookupError as exc:
            print(f"Error: {exc}")
            return 1

        print_store_entry_details(entry)
        return 0

    print(f"Unknown store command: {args.store_command}")
    return 2


def resolve_robot_password(
    password: str | None,
    password_env: str | None,
) -> str | None:
    """Resolve an ABB RWS password from CLI value or environment variable.

    Args:
        password: Direct password value from CLI.
        password_env: Name of the environment variable containing the password.

    Returns:
        Resolved password, or ``None`` if no explicit override is provided.

    Raises:
        ValueError: If both password sources are provided or if the requested
            environment variable is missing or empty.
    """
    if password is not None and password_env is not None:
        raise ValueError("Use either --password or --password-env, not both.")

    if password_env is None:
        return password

    resolved = os.environ.get(password_env)
    if not resolved:
        raise ValueError(f"Password environment variable is not set: {password_env}")

    return resolved


def handle_robot_command(args: argparse.Namespace) -> int:
    """Run a ``trajcenter robot`` subcommand.

    Args:
        args: Parsed command-line arguments.

    Returns:
        Process exit code.
    """
    if args.robot_command is None:
        print("Missing robot command. Use: trajcenter robot --help")
        return 2

    if args.robot_command == "check":
        try:
            import trajcenter.robot  # noqa: F401
        except ImportError as exc:
            print(ROBOT_OPTIONAL_DEPENDENCY_MESSAGE)
            print(f"Import error: {exc}")
            return 1

        print("Robot ABB API available.")
        return 0

    if args.robot_command == "supervise":
        try:
            from trajcenter.robot.supervisor import (
                run_rws_subscription_supervisor_app,
            )
        except ImportError as exc:
            print(ROBOT_OPTIONAL_DEPENDENCY_MESSAGE)
            print(f"Import error: {exc}")
            return 1

        try:
            password = resolve_robot_password(args.password, args.password_env)
        except ValueError as exc:
            print(f"Error: {exc}")
            return 1

        return asyncio.run(
            run_rws_subscription_supervisor_app(
                store_root=args.store,
                task=args.task,
                module=args.module,
                mastership_retries=args.mastership_retries,
                log_level=args.log_level,
                env_file=args.env_file,
                env_override=args.env_override,
                host=args.host,
                username=args.username,
                password=password,
                port=args.port,
                timeout=args.timeout,
            )
        )

    print(f"Unknown robot command: {args.robot_command}")
    return 2


def run_tui(config: UIConfig) -> int:
    """Run the TrajCenter Textual TUI.

    Args:
        config: UI configuration.

    Returns:
        Process exit code.
    """
    try:
        from trajcenter.ui.app import run_tui as run_textual_tui
    except ImportError as exc:
        print(TUI_OPTIONAL_DEPENDENCY_MESSAGE)
        print(f"Import error: {exc}")
        return 1

    return run_textual_tui(config)


def run_command(args: argparse.Namespace) -> int:
    """Run the parsed TrajCenter command.

    Args:
        args: Parsed command-line arguments.

    Returns:
        Process exit code.
    """
    if args.command == "version":
        print(f"{APP_NAME} {get_package_version()}")
        return 0

    if args.command == "convert":
        return handle_convert_command(args)

    if args.command == "export":
        return handle_export_command(args)

    if args.command == "tui":
        try:
            from trajcenter.ui.config import UIConfig
        except ImportError as exc:
            print(TUI_OPTIONAL_DEPENDENCY_MESSAGE)
            print(f"Import error: {exc}")
            return 1

        return run_tui(UIConfig(store=args.store))

    if args.command == "store":
        return handle_store_command(args)

    if args.command == "robot":
        return handle_robot_command(args)

    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Run the TrajCenter CLI.

    Args:
        argv: Optional command-line arguments. If ``None``, arguments are read
            from ``sys.argv``.

    Returns:
        Process exit code.
    """
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 0

    return run_command(args)


if __name__ == "__main__":
    raise SystemExit(main())
