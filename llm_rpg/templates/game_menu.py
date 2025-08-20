from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Union
import time
import os
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.style import Style


# -------------------------- Constants --------------------------
G_INV_INPUT_SLEEP_S = 1

# -------------------------- Abstract Base Classes --------------------------
class Menu(ABC):
    """Abstract base class for all menu types"""
    def __init__(self, console_manager):
        self.console_manager = console_manager

    @property
    def console(self) -> Console:
        """Get console instance from manager"""
        return self.console_manager.console

    @property
    def styles(self) -> Dict[str, Style]:
        """Get styles from manager"""
        return self.console_manager.styles

    @abstractmethod
    def display(self) -> Any:
        """Display the menu and handle user interaction"""
        pass

    def clear_screen(self) -> None:
        """Clear screen using console manager"""
        self.console_manager.clear_screen()

    def display_header(self, title: str) -> None:
        """Display header using console manager"""
        self.console_manager.display_header(title)

    def get_numeric_input(self, prompt: str, min_val: int, max_val: int) -> Optional[int]:
        """Get validated numeric input from user"""
        while True:
            choice = self.console.input(
                Text(prompt, style=self.console_manager.get_style('prompt'))
            ).strip().lower()

            if choice == 'back':
                return None

            try:
                value = int(choice)
                if min_val <= value <= max_val:
                    return value
                raise ValueError
            except ValueError:
                self.console.print(
                    Text(f"Please enter a number between {min_val} and {max_val}",
                         style=self.styles['error']),
                    justify="center"
                )
                time.sleep(G_INV_INPUT_SLEEP_S)
