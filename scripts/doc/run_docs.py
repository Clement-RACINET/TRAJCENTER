"""Orchestrateur : génère la doc API et lance mkdocs serve."""
from __future__ import annotations

import subprocess
import sys

from scripts.doc.config import build_config
from scripts.doc.generate_api import generate_api_docs, update_mkdocs_nav


def main() -> None:
    cfg = build_config()
    nav = generate_api_docs(cfg)
    update_mkdocs_nav(cfg, nav)

    print("\n🚀 Lancement de mkdocs serve...")
    subprocess.run([sys.executable, "-m", "mkdocs", "serve"], cwd=cfg.project_root)


if __name__ == "__main__":
    main()
