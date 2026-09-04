"""Simple terminal UI for TrajCenter."""

from __future__ import annotations

from trajcenter.ui.banner import BANNER
from trajcenter.ui.config import UIConfig
from trajcenter.ui.conversion import run_conversion_menu
from trajcenter.ui.robot import run_robot_menu


def run_ui(config: UIConfig | None = None) -> int:
    """Run the simple TrajCenter terminal UI."""
    if config is None:
        config = UIConfig()

    print(BANNER)

    while True:
        print()
        print("Main menu")
        print("---------")
        print("1. File conversion / trajectory store")
        print("2. Robot communication / ABB RWS")
        print("q. Quit")
        print()

        choice = input("Choice > ").strip().lower()

        if choice == "1":
            run_conversion_menu(config)
        elif choice == "2":
            run_robot_menu(config)
        elif choice in {"q", "quit", "exit"}:
            return 0
        else:
            print("Invalid choice.")
