#!/usr/bin/env python3
# contrib/fix_init.py
"""Audit and auto-fix all __init__.py files in abb_rws_client/ and tests/.

For each Python package directory (containing .py files or sub-packages):
  - Creates __init__.py if missing.
  - Rewrites abb_rws_client/rws/*/__init__.py with correct imports + __all__.
  - Rewrites abb_rws_client/rws/__init__.py with explicit sub-package re-exports.
  - Rewrites abb_rws_client/highlevel/__init__.py with public API exports.
  - Rewrites abb_rws_client/__init__.py with public API exports.
  - Rewrites abb_rws_client/_core/__init__.py with core exports.
  - Creates minimal __init__.py in tests/ sub-directories (no imports).

Discovery strategy:
  All public names are discovered automatically via AST scanning — no
  manual declaration required. The only exception is _CORE_PUBLIC_EXPORTS,
  which filters the _core/ API surface to avoid exposing private helpers.

Usage:
    pixi run python contrib/fix_init.py
    pixi run python contrib/fix_init.py --dry-run

Args:
    --dry-run: Print what would be written without touching the filesystem.
    --skip-tests: Skip processing of tests/ sub-directories.
"""

from __future__ import annotations

import argparse
import ast
import io
from pathlib import Path
import sys

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).parent.parent
PKG_ROOT = REPO_ROOT / "abb_rws_client"
TESTS_ROOT = REPO_ROOT / "tests"

# Only _core/ requires an explicit allowlist because its files contain
# private helpers (_build_auth, _raise_for_status, …) that must NOT be
# re-exported. Every other sub-package uses full AST auto-discovery.
_CORE_PUBLIC_EXPORTS: dict[str, list[str]] = {
    "client": ["RWSClient", "RWSClientSync"],
    "env": ["load_env"],
    "exceptions": [
        "CTRL_CODES",
        "MastershipDenied",
        "MastershipError",
        "MastershipNotHeld",
        "RWSAuthenticationError",
        "RWSConnectionError",
        "RWSError",
        "RWSHTTPError",
        "RWSNotFoundError",
        "RWSTimeoutError",
        "RWSValueError",
    ],
    "logging": ["configure_logging", "get_logger"],
    "serializers": [
        "RapidValue",
        "RobTarget",
        "robtarget_to_rws",
        "rws_to_robtarget",
    ],
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _collect_public_names(py_file: Path) -> list[str]:
    """Parse a .py file with AST and return top-level public names only.

    Only inspects the module's top-level body (no recursion).
    Excludes imports — only collects definitions (functions, classes,
    assignments) that are genuinely defined in this module.

    Args:
        py_file: Path to the Python source file.

    Returns:
        Deduplicated, sorted list of public names (no leading underscore).
    """
    try:
        tree = ast.parse(py_file.read_text(encoding="utf-8"))
    except SyntaxError as exc:
        print(f"  [WARN] Cannot parse {py_file}: {exc}", file=sys.stderr)
        return []

    names: list[str] = []

    for node in tree.body:
        match node:
            case ast.FunctionDef(name=n) | ast.AsyncFunctionDef(name=n):
                if not n.startswith("_"):
                    names.append(n)
            case ast.ClassDef(name=n):
                if not n.startswith("_"):
                    names.append(n)
            case ast.Assign(targets=targets):
                for t in targets:
                    if isinstance(t, ast.Name) and not t.id.startswith("_"):
                        names.append(t.id)
            case ast.AnnAssign(target=ast.Name(id=n)):
                if not n.startswith("_"):
                    names.append(n)
            # ast.ImportFrom and ast.Import → intentionally ignored

    seen: set[str] = set()
    result: list[str] = []
    for n in names:
        if n not in seen:
            seen.add(n)
            result.append(n)
    return sorted(result)


def _format_import(module: str, names: list[str]) -> str:
    """Format a single from-import statement, wrapping beyond 88 chars.

    Names are sorted alphabetically to satisfy isort (ruff I001).

    Args:
        module: The module to import from (e.g. '.backup').
        names: List of names to import (order does not matter).

    Returns:
        A formatted import string, single-line or parenthesised multi-line.
        Empty string if names is empty.
    """
    if not names:
        return ""

    sorted_names = sorted(names)
    single = f"from {module} import {', '.join(sorted_names)}"
    if len(single) <= 88:
        return single

    lines = [f"from {module} import ("]
    for name in sorted_names:
        lines.append(f"    {name},")
    lines.append(")")
    return "\n".join(lines)


def _format_all(names: list[str]) -> str:
    """Format a deduplicated, sorted list of names for __all__.

    Args:
        names: Raw list of names (may contain duplicates).

    Returns:
        Indented string of quoted names with trailing commas,
        ready to be embedded inside ``__all__ = [\\n    ...\\n]``.
        Empty string if names is empty.
    """
    unique = sorted(set(names))
    if not unique:
        return ""
    return "\n    ".join(f'"{n}",' for n in unique)


def _write(path: Path, content: str, dry_run: bool) -> None:
    """Write content to path, or print it in dry-run mode.

    Compares existing content before writing to report the actual status:
    - [NEW]       file did not exist
    - [UNCHANGED] content is identical, no write performed
    - [UPDATED]   content changed, file rewritten

    Args:
        path: Destination file path.
        content: File content to write.
        dry_run: If True, only print; do not write.
    """
    rel = path.relative_to(REPO_ROOT)

    if dry_run:
        print(f"\n{'=' * 60}")
        print(f"[DRY-RUN] Would write: {rel}")
        print(f"{'=' * 60}")
        print(content)
        return

    path.parent.mkdir(parents=True, exist_ok=True)

    if path.exists():
        existing = path.read_text(encoding="utf-8")
        if existing == content:
            print(f"  [UNCHANGED] {rel}")
            return
        status = "UPDATED"
    else:
        status = "NEW"

    path.write_text(content, encoding="utf-8")
    print(f"  [{status}] {rel}")


def _is_package_dir(directory: Path) -> bool:
    """Return True if directory contains .py files or sub-packages.

    Args:
        directory: Directory to inspect.

    Returns:
        True if the directory qualifies as a Python package.
    """
    if not directory.is_dir():
        return False
    has_py = any(
        f.suffix == ".py" and f.name != "__init__.py"
        for f in directory.iterdir()
        if f.is_file()
    )
    has_subpkg = any(
        (d / "__init__.py").exists() or _is_package_dir(d)
        for d in directory.iterdir()
        if d.is_dir() and not d.name.startswith(".")
    )
    return has_py or has_subpkg


def _collect_test_dirs(root: Path) -> list[Path]:
    """Recursively collect all sub-directories of tests/ containing .py files.

    Ignores hidden directories and __pycache__.

    Args:
        root: Root of the tests/ directory.

    Returns:
        Sorted list of directories that contain at least one .py file.
    """
    result: list[Path] = []
    for d in sorted(root.rglob("*")):
        if not d.is_dir():
            continue
        if any(part.startswith((".", "__")) for part in d.parts):
            continue
        if any(f.suffix == ".py" for f in d.iterdir() if f.is_file()):
            result.append(d)
    return result


# ---------------------------------------------------------------------------
# Generators
# ---------------------------------------------------------------------------


def _gen_rws_submodule_init(pkg_dir: Path) -> str:
    """Generate __init__.py for any flat sub-package via AST auto-discovery.

    Scans all .py files (excluding __init__.py) in the directory,
    extracts public names via AST, and generates imports + __all__.
    No manual declaration required.

    Args:
        pkg_dir: Path to the sub-package directory.

    Returns:
        Complete __init__.py content as a string.
    """
    py_files = sorted(
        f
        for f in pkg_dir.iterdir()
        if f.is_file() and f.suffix == ".py" and f.name != "__init__.py"
    )

    import_blocks: list[str] = []
    all_names: list[str] = []

    for py_file in py_files:
        names = _collect_public_names(py_file)
        if names:
            block = _format_import(f".{py_file.stem}", names)
            if block:
                import_blocks.append(block)
            all_names.extend(names)

    imports_block = (
        "\n".join(import_blocks) if import_blocks else "# No public symbols"
    )
    rel = pkg_dir.relative_to(PKG_ROOT).as_posix()

    return f"""\
# abb_rws_client/{rel}/__init__.py
\"\"\"Public re-exports for the {rel} sub-package.

Auto-generated by contrib/fix_init.py — do not edit manually.
\"\"\"

from __future__ import annotations

{imports_block}

__all__ = [
    {_format_all(all_names)}
]
"""


def _gen_rws_init(rws_dir: Path) -> str:
    """Generate __init__.py for abb_rws_client/rws/ via AST auto-discovery.

    Collects all public names from every sub-package AND flat .py files
    in rws/, merges them into a single sorted import block, and deduplicates
    names that appear in multiple modules (keeping the first occurrence by
    alphabetical module order to avoid F811 redefinition errors).

    Args:
        rws_dir: Path to abb_rws_client/rws/.

    Returns:
        Complete __init__.py content as a string.
    """
    # ── Step 1: collect all (module_stem, [names]) pairs, sorted alpha ────
    # Mix sub-packages and flat .py files in a single sorted pass so that
    # the import order is strictly alphabetical → satisfies ruff I001.

    entries: list[tuple[str, list[str]]] = []

    # Sub-packages (directories)
    for sub in sorted(rws_dir.iterdir()):
        if not sub.is_dir():
            continue
        if sub.name.startswith("_") or sub.name.startswith("."):
            continue
        sub_names: list[str] = []
        for py_file in sorted(sub.iterdir()):
            if (
                py_file.is_file()
                and py_file.suffix == ".py"
                and py_file.name != "__init__.py"
            ):
                sub_names.extend(_collect_public_names(py_file))
        if sub_names:
            entries.append((sub.name, sorted(set(sub_names))))

    # Flat .py files directly in rws/
    for py_file in sorted(rws_dir.iterdir()):
        if (
            py_file.is_file()
            and py_file.suffix == ".py"
            and py_file.name != "__init__.py"
        ):
            names = _collect_public_names(py_file)
            if names:
                entries.append((py_file.stem, names))

    # Sort all entries alphabetically by module stem → ruff I001 compliant
    entries.sort(key=lambda x: x[0])

    # ── Step 2: deduplicate — first module (alpha order) wins ─────────────
    # When the same function name exists in two modules (e.g. get_robtarget
    # in both rapid/tasks.py and motionsystem.py), only the first occurrence
    # (alphabetically) is kept to avoid F811 redefinition errors.
    seen_names: set[str] = set()
    deduped_entries: list[tuple[str, list[str]]] = []

    for stem, names in entries:
        unique_names = [n for n in names if n not in seen_names]
        seen_names.update(unique_names)
        if unique_names:
            deduped_entries.append((stem, unique_names))

    # ── Step 3: render ────────────────────────────────────────────────────
    import_blocks: list[str] = []
    all_names: list[str] = []

    for stem, names in deduped_entries:
        block = _format_import(f".{stem}", names)
        if block:
            import_blocks.append(block)
        all_names.extend(names)

    imports_block = (
        "\n".join(import_blocks) if import_blocks else "# No sub-packages"
    )

    return f"""\
# abb_rws_client/rws/__init__.py
\"\"\"RWS API mirror — atomic HTTP functions (1 function = 1 endpoint).

Auto-generated by contrib/fix_init.py — do not edit manually.
\"\"\"

from __future__ import annotations

{imports_block}

__all__ = [
    {_format_all(all_names)}
]
"""


def _gen_core_init() -> str:
    """Generate __init__.py for abb_rws_client/_core/.

    Uses the explicit allowlist ``_CORE_PUBLIC_EXPORTS`` (not AST
    auto-discovery) because _core/ contains private helpers that must
    not be re-exported. The allowlist is sorted per-module and globally
    to satisfy ruff I001.

    Returns:
        Complete __init__.py content as a string.
    """
    import_blocks: list[str] = []
    all_names: list[str] = []

    # Iterate in sorted module order so ruff I001 is satisfied
    for module in sorted(_CORE_PUBLIC_EXPORTS):
        names = _CORE_PUBLIC_EXPORTS[module]
        block = _format_import(f".{module}", names)
        if block:
            import_blocks.append(block)
        all_names.extend(names)

    imports_block = "\n".join(import_blocks)

    return f"""\
# abb_rws_client/_core/__init__.py
\"\"\"Internal core — session, exceptions, serializers.

Not part of the public API. Import from ``abb_rws_client`` directly.
\"\"\"

from __future__ import annotations

{imports_block}

__all__ = [
    {_format_all(all_names)}
]
"""


def _gen_package_init() -> str:
    """Generate abb_rws_client/__init__.py with the public API surface.

    Imports are generated in sorted module order (isort-compatible) so
    that ``ruff check`` passes without requiring a subsequent ``--fix``.

    Returns:
        Complete __init__.py content as a string.
    """
    import_blocks: list[str] = []
    all_names: list[str] = []

    # Sorted module order → satisfies ruff I001 out of the box
    for module in sorted(_CORE_PUBLIC_EXPORTS):
        names = _CORE_PUBLIC_EXPORTS[module]
        block = _format_import(f"abb_rws_client._core.{module}", names)
        if block:
            import_blocks.append(block)
        all_names.extend(names)

    imports_block = "\n".join(import_blocks)

    return f"""\
# abb_rws_client/__init__.py
\"\"\"abb-rws6-python-client — Async Python client for ABB RWS (RobotWare 6).

Public API surface:
    - RWSClient / RWSClientSync  : HTTP session management
    - RWSError hierarchy         : typed exceptions
    - RobTarget / RapidValue     : RAPID type helpers
    - robtarget_to_rws / rws_to_robtarget : serializers
    - load_env                   : .env file loader
    - configure_logging          : library log level
    - get_logger                 : namespaced child logger

Example:
    >>> from abb_rws_client import RWSClient
    >>> async with RWSClient(host="192.168.125.1") as client:
    ...     resp = await client.get("/rw/rapid/execution")
\"\"\"

from __future__ import annotations

{imports_block}

__all__ = [
    {_format_all(all_names)}
]

__version__ = "0.8.0"
"""


def _gen_test_init(directory: Path) -> str:
    """Generate a minimal __init__.py for a tests/ sub-directory.

    Tests __init__.py files must stay empty of imports to avoid
    circular dependencies and pytest collection conflicts.
    They only serve as package markers for relative imports in conftest.

    Args:
        directory: The test sub-directory.

    Returns:
        Minimal __init__.py content as a string.
    """
    rel = directory.relative_to(REPO_ROOT).as_posix()
    return f"""\
# {rel}/__init__.py
# Package marker — do not add imports here.
# Auto-generated by contrib/fix_init.py — do not edit manually.
"""


# ---------------------------------------------------------------------------
# Fix functions
# ---------------------------------------------------------------------------


def fix_package(dry_run: bool) -> None:
    """Rewrite abb_rws_client/__init__.py.

    Args:
        dry_run: If True, only print without writing.
    """
    print("\n── abb_rws_client/__init__.py ──────────────────────────────")
    _write(PKG_ROOT / "__init__.py", _gen_package_init(), dry_run)


def fix_core(dry_run: bool) -> None:
    """Rewrite _core/__init__.py.

    Args:
        dry_run: If True, only print without writing.
    """
    print("\n── _core/__init__.py ───────────────────────────────────────")
    _write(PKG_ROOT / "_core" / "__init__.py", _gen_core_init(), dry_run)


def fix_rws(dry_run: bool) -> None:
    """Process all rws/ sub-packages via AST auto-discovery, then rws/__init__.py.

    Args:
        dry_run: If True, only print without writing.
    """
    rws_dir = PKG_ROOT / "rws"
    if not rws_dir.exists():
        print("[SKIP] abb_rws_client/rws/ not found — skipping.")
        return

    print("\n── rws/ sub-packages ──────────────────────────────────────")
    for sub in sorted(rws_dir.iterdir()):
        if not sub.is_dir() or sub.name.startswith("_") or sub.name.startswith("."):
            continue
        _write(sub / "__init__.py", _gen_rws_submodule_init(sub), dry_run)

    print("\n── rws/__init__.py ─────────────────────────────────────────")
    _write(rws_dir / "__init__.py", _gen_rws_init(rws_dir), dry_run)


def fix_highlevel(dry_run: bool) -> None:
    """Rewrite highlevel/__init__.py via AST auto-discovery.

    Automatically picks up any new module added to highlevel/ without
    requiring manual edits to this script.

    Args:
        dry_run: If True, only print without writing.
    """
    hl_dir = PKG_ROOT / "highlevel"
    if not hl_dir.exists():
        print("\n[SKIP] highlevel/ does not exist yet — skipping.")
        return

    print("\n── highlevel/__init__.py ───────────────────────────────────")
    _write(hl_dir / "__init__.py", _gen_rws_submodule_init(hl_dir), dry_run)


def fix_tests(dry_run: bool) -> None:
    """Create minimal __init__.py markers in all tests/ sub-directories.

    Args:
        dry_run: If True, only print without writing.
    """
    if not TESTS_ROOT.exists():
        print("\n[SKIP] tests/ not found — skipping.")
        return

    print("\n── tests/ sub-directories ──────────────────────────────────")
    sub_dirs = _collect_test_dirs(TESTS_ROOT)

    if not sub_dirs:
        print("  [SKIP] No sub-directories with .py files found in tests/.")
        return

    for directory in sub_dirs:
        _write(directory / "__init__.py", _gen_test_init(directory), dry_run)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """CLI entry point.

    Raises:
        SystemExit: On argument parsing error.
    """
    stdout = sys.stdout
    if isinstance(stdout, io.TextIOWrapper):
        stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(
        description=(
            "Audit and fix all __init__.py files in "
            "abb_rws_client/ and tests/."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be written without touching the filesystem.",
    )
    parser.add_argument(
        "--skip-tests",
        action="store_true",
        help="Skip processing of tests/ sub-directories.",
    )
    args = parser.parse_args()

    dry = args.dry_run
    print(
        "🔍 DRY-RUN mode — no files will be written.\n"
        if dry
        else "Fixing __init__.py files...\n"
    )

    fix_package(dry)
    fix_core(dry)
    fix_rws(dry)
    fix_highlevel(dry)

    if not args.skip_tests:
        fix_tests(dry)

    print("\n Dry-run complete." if dry else "\n Done.")


if __name__ == "__main__":
    main()
