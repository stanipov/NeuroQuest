from rich.style import Style
from rich.theme import Theme
from typing import Dict


class ConsoleStyles:
    """Handles all console styling and themes"""

    def __init__(self):
        self._styles = self._setup_styles()
        self._theme = self._setup_theme()
        self._basic_theme = self._setup_basic_theme()

    def _setup_styles(self) -> Dict[str, Style]:
        """Setup color styles for the game"""
        return {
            'title': Style(color="bright_red", bold=True),
            'menu': Style(color="bright_cyan"),
            'option': Style(color="bright_green"),
            'error': Style(color="bright_red", blink=True),
            'success': Style(color="bright_green"),
            'info': Style(color="bright_blue"),
            'prompt': Style(color="bright_yellow"),
            # RPG Chat specific styles
            'user_input': Style(color="bright_cyan", bold=True),
            'llm_output': Style(color="bright_green"),
            'system': Style(color="bright_yellow", italic=True),
            'service_command': Style(color="bright_magenta", underline=True),
            'typing': Style(color="grey58", italic=True),
            'rpg_npc': Style(color="bright_blue", bold=True),
            'rpg_player': Style(color="bright_cyan", bold=True),
            'rpg_system': Style(color="bright_yellow", italic=True),
        }

    def _setup_theme(self) -> Theme:
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

    def _setup_basic_theme(self) -> Theme:
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

    @property
    def styles(self) -> Dict[str, Style]:
        """Dictionary of predefined styles"""
        return self._styles

    @property
    def theme(self) -> Theme:
        """Main theme with colors"""
        return self._theme

    @property
    def basic_theme(self) -> Theme:
        """Fallback theme for limited terminals"""
        return self._basic_theme

    def get_style(self, style_name: str) -> Style:
        """Get a style by name"""
        return self._styles.get(style_name, Style())