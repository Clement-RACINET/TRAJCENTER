#!/usr/bin/env python3
# contrib/clean.py
"""Remove all cache and build artefacts from the repository.

Targets:
    - __pycache__/   Python bytecode cache
    - *.pyc          Compiled bytecode files
    - .pytest_cache/ pytest cache
    - .mypy_cache/   mypy cache
    - .ruff_cache/   ruff cache
    - dist/          build output
    - *.egg-info/    setuptools metadata
    - docs/coverage/ coverage HTML report
    - tests/coverage.xml coverage XML report

Usage:
    pixi run python contrib/clean.py
    pixi run python contrib/clean.py --dry-run
"""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil

REPO_ROOT = Path(__file__).parent.parent

# Dossiers supprimés récursivement
_DIR_PATTERNS: list[str] = [
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "dist",
    "*.egg-info",
]

# Fichiers supprimés récursivement
_FILE_PATTERNS: list[str] = [
    "*.pyc",
    "*.pyo",
    "*.pyd",
]


def _remove(path: Path, dry_run: bool) -> None:
    """Remove a file or directory, or print it in dry-run mode.

    Args:
        path: Path to remove.
        dry_run: If True, only print; do not delete.
    """
    rel = path.relative_to(REPO_ROOT)
    if dry_run:
        print(f"  [DRY-RUN] Would remove: {rel}")
        return
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()
    print(f"  [REMOVED] {rel}")


def clean(dry_run: bool = False) -> None:
    """Scan and remove all cache/build artefacts.

    Args:
        dry_run: If True, only print what would be removed.
    """
    removed = 0

    # Dossiers nommés exactement (récursif dans tout le repo)
    exact_dir_names = {p for p in _DIR_PATTERNS if "*" not in p and "/" not in p}
    for dirpath in sorted(REPO_ROOT.rglob("*")):
        if dirpath.is_dir() and dirpath.name in exact_dir_names:
            # Ne pas descendre dans .pixi/
            if ".pixi" in dirpath.parts:
                continue
            _remove(dirpath, dry_run)
            removed += 1

    # Dossiers avec glob (ex: *.egg-info) à la racine
    for pattern in _DIR_PATTERNS:
        if "*" in pattern and "/" not in pattern:
            for match in REPO_ROOT.glob(pattern):
                if match.is_dir():
                    _remove(match, dry_run)
                    removed += 1

    # Chemins fixes relatifs à REPO_ROOT (ex: docs/coverage)
    for pattern in _DIR_PATTERNS:
        if "/" in pattern:
            target = REPO_ROOT / pattern
            if target.exists():
                _remove(target, dry_run)
                removed += 1

    # Fichiers (*.pyc, coverage.xml, etc.)
    for pattern in _FILE_PATTERNS:
        if pattern.startswith("*"):
            for match in REPO_ROOT.rglob(pattern):
                if ".pixi" in match.parts:
                    continue
                _remove(match, dry_run)
                removed += 1
        else:
            target = REPO_ROOT / pattern
            if target.exists():
                _remove(target, dry_run)
                removed += 1

    if removed == 0:
        print("  Nothing to clean.")
    else:
        noun = "item" if removed == 1 else "items"
        print(f"\n{removed} {noun} {'would be ' if dry_run else ''}removed.")


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Remove cache and build artefacts from the repository.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be removed without deleting anything.",
    )
    args = parser.parse_args()

    print(
        "DRY-RUN — nothing will be deleted.\n"
        if args.dry_run
        else "Cleaning repository...\n"
    )
    clean(args.dry_run)


if __name__ == "__main__":
    main()
