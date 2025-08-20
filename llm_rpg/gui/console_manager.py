from typing import Dict

from rich.console import Console
from rich.panel import Panel
from rich.style import Style
from rich.text import Text
import os

from llm_rpg.gui.styles import ConsoleStyles


class ConsoleManager():
    """Handles console creation and management with rich library"""

    def __init__(self):
        """Initialize console manager with environment setup and console creation"""
        self.setup_terminal_environment()
        self._styles = ConsoleStyles()  # Using the new styles class
        self._console = self.create_console()

    def setup_terminal_environment(self) -> None:
        """Ensure basic terminal environment variables"""
        if 'TERM' not in os.environ:
            os.environ['TERM'] = 'xterm-256color'
        if 'COLORTERM' not in os.environ:
            os.environ['COLORTERM'] = 'truecolor'

    def create_console(self) -> Console:
        """Create console with fallback options"""
        try:
            return Console(theme=self._styles.theme)
        except Exception:
            return Console(theme=self._styles.basic_theme, force_terminal=True)

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
                Text(title, justify="center", style=self._styles.get_style('title')),
                border_style=self.get_style('menu')
            ),
            justify="center"
        )

    def get_style(self, style_name: str) -> Style:
        """Convenience method to get a style by name"""
        return self._styles.get_style(style_name)

    @property
    def console(self) -> Console:
        """The rich Console instance"""
        return self._console

    @property
    def styles(self) -> Dict[str, Style]:
        """Dictionary of predefined styles"""
        return self._styles