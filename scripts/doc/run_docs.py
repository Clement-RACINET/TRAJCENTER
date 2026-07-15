#!/usr/bin/env python3
# scripts/doc/run_docs.py
"""Orchestrator: generates the API documentation, the coverage report, and starts mkdocs serve.

Author: Clement RACINET
"""

from __future__ import annotations

import subprocess
import sys

from scripts.doc.config import build_config
from scripts.doc.generate_api import generate_api_docs, update_mkdocs_nav


def _generate_coverage(project_root) -> None:
    """Run pytest --cov to produce the HTML coverage report in docs/coverage/.

    Args:
        project_root: Absolute path to the project root directory, used as
            the working directory for the subprocess call.
    """
    print("\n📊 Generating coverage report...")
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "--cov=trajcenter",
            "--cov-branch",
            "--cov-report=html:docs/coverage",
            "--no-header",
            "-q",
        ],
        cwd=project_root,
    )
    if result.returncode != 0:
        print("⚠️  Some tests failed — coverage report may be incomplete.")


def main() -> None:
    """Entry point: generate API docs, update mkdocs.yml, run coverage, then serve.

    Runs the full documentation pipeline in sequence:

    1. Generate per-module Markdown pages via :func:`~scripts.doc.generate_api.generate_api_docs`.
    2. Inject the nav block into ``mkdocs.yml`` via :func:`~scripts.doc.generate_api.update_mkdocs_nav`.
    3. Run the pytest coverage report via :func:`_generate_coverage`.
    4. Start ``mkdocs serve`` (blocking until ``Ctrl+C``).
    """
    cfg = build_config()

    nav = generate_api_docs(cfg)
    update_mkdocs_nav(cfg, nav)

    _generate_coverage(cfg.project_root)

    print("\n🚀 Starting mkdocs serve...  (Ctrl+C to stop)")
    try:
        subprocess.run(
            [sys.executable, "-m", "mkdocs", "serve"],
            cwd=cfg.project_root,
        )
    except KeyboardInterrupt:
        print("\n👋 Server stopped.")
        sys.exit(0)


if __name__ == "__main__":
    main()
