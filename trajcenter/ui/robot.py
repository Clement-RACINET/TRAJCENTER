"""Robot menu for the simple TrajCenter terminal UI."""

from __future__ import annotations

from trajcenter.ui.config import UIConfig


def run_robot_menu(config: UIConfig) -> None:
    """Run the robot submenu."""
    while True:
        print()
        print("Robot communication / ABB RWS")
        print("-----------------------------")
        print(f"Host: {config.host or '<from env>'}")
        print(f"Port: {config.port or '<from env>'}")
        print(f"User: {config.username or '<from env>'}")
        print(f"Task: {config.task}")
        print(f"Module: {config.module}")
        print()
        print("1. Show configuration")
        print("b. Back")
        print()

        choice = input("Choice > ").strip().lower()

        if choice == "1":
            _show_robot_config(config)
        elif choice in {"b", "back"}:
            return
        else:
            print("Invalid choice.")


def _show_robot_config(config: UIConfig) -> None:
    """Print robot configuration."""
    print()
    print("Robot configuration")
    print("-------------------")
    print(f"env_file: {config.env_file}")
    print(f"env_override: {config.env_override}")
    print(f"host: {config.host}")
    print(f"port: {config.port}")
    print(f"username: {config.username}")
    print(f"password: {'<provided>' if config.password else None}")
    print(f"password_env: {config.password_env}")
    print(f"timeout: {config.timeout}")
    print(f"task: {config.task}")
    print(f"module: {config.module}")
    print(f"mastership_retries: {config.mastership_retries}")
    print(f"log_level: {config.log_level}")
