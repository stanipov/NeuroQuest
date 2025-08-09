from abc import ABC, abstractmethod
from typing import Dict
from rich.console import Console
from rich.style import Style
from rich.theme import Theme


class BaseConsoleManager(ABC):
    """Abstract base class for console management functionality"""

    @abstractmethod
    def setup_terminal_environment(self) -> None:
        """Ensure basic terminal environment variables are set"""
        pass

    @abstractmethod
    def create_console(self) -> Console:
        """Create and return a configured Console instance"""
        pass

    @abstractmethod
    def get_theme(self) -> Theme:
        """Return the main theme with colors for the console"""
        pass

    @abstractmethod
    def get_basic_theme(self) -> Theme:
        """Return a fallback theme for limited terminals"""
        pass

    @abstractmethod
    def setup_styles(self) -> Dict[str, Style]:
        """Setup and return color styles dictionary for the application"""
        pass

    @abstractmethod
    def clear_screen(self) -> None:
        """Clear the terminal screen"""
        pass

    @abstractmethod
    def display_header(self, title: str) -> None:
        """Display a styled header with the given title"""
        pass

    @property
    @abstractmethod
    def console(self) -> Console:
        """The rich Console instance"""
        pass

    @property
    @abstractmethod
    def styles(self) -> Dict[str, Style]:
        """Dictionary of predefined styles"""
        pass