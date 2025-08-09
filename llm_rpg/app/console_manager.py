from typing import Dict
from rich.console import Console
from rich.style import Style
from rich.theme import Theme
from rich.panel import Panel
from rich.table import Text
import os

from llm_rpg.templates.console_manager import BaseConsoleManager


class ConsoleManager(BaseConsoleManager):
    """Handles console creation and styling with rich library"""

    def __init__(self):
        """Initialize console manager with environment setup and console creation"""
        self.setup_terminal_environment()
        self._console = self.create_console()
        self._styles = self.setup_styles()

    def setup_terminal_environment(self) -> None:
        """Ensure basic terminal environment variables"""
        if 'TERM' not in os.environ:
            os.environ['TERM'] = 'xterm-256color'
        if 'COLORTERM' not in os.environ:
            os.environ['COLORTERM'] = 'truecolor'

    def create_console(self) -> Console:
        """Create console with fallback options"""
        try:
            return Console(theme=self.get_theme())
        except Exception:
            return Console(theme=self.get_basic_theme(), force_terminal=True)

    def get_theme(self) -> Theme:
        """Main theme with colors"""
        return Theme({
            "title": "bold red",
            "menu": "cyan",
            "option": "green",
            "error": "blink red",
            "success": "green",
            "info": "blue",
            "prompt": "yellow"
        })

    def get_basic_theme(self) -> Theme:
        """Fallback theme for limited terminals"""
        return Theme({
            "title": "bold",
            "menu": "",
            "option": "",
            "error": "",
            "success": "",
            "info": "",
            "prompt": ""
        })

    def setup_styles(self) -> Dict[str, Style]:
        """Setup color styles for the game"""
        return {
            'title': Style(color="bright_red", bold=True),
            'menu': Style(color="bright_cyan"),
            'option': Style(color="bright_green"),
            'error': Style(color="bright_red", blink=True),
            'success': Style(color="bright_green"),
            'info': Style(color="bright_blue"),
            'prompt': Style(color="bright_yellow")
        }

    def clear_screen(self) -> None:
        """Clear the terminal screen"""
        try:
            self.console.clear()  # Preferred method using rich
        except Exception:
            # Alternative cross-platform solution:
            os.system('cls' if os.name == 'nt' else 'clear')

    def display_header(self, title: str) -> None:
        """Display a styled header with the given title"""
        self.console.print(
            Panel.fit(
                Text(title, justify="center", style=self.styles['title']),
                border_style=self.styles['menu']
            ),
            justify="center"
        )

    @property
    def console(self) -> Console:
        """The rich Console instance"""
        return self._console

    @property
    def styles(self) -> Dict[str, Style]:
        """Dictionary of predefined styles"""
        return self._styles