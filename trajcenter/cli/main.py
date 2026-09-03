# trajcenter/cli/main.py
"""TrajCenter command line interface.

This module intentionally uses only the Python standard library so that the
base ``trajcenter`` command works without optional CLI dependencies.
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from trajcenter.rws.models import TrajectoryStoreEntry
from trajcenter.rws.store import scan_trajectory_store

APP_NAME = "trajcenter"
DEFAULT_STORE = Path("trajectory_store")


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

    if args.command == "store":
        return handle_store_command(args)

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
