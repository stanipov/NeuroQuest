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

    def display_lore_section(self, title: str, content: str, style_name: str = "rpg_npc") -> None:
        """Display a lore section in a styled panel"""
        panel = Panel(
            Text(content, style=self.get_style("llm_output")),
            title=title,
            border_style=self.get_style(style_name),
            subtitle_align="right"
        )
        self.console.print(panel)

    def display_character_card(self, title: str, character_data: Dict[str, str], style_name: str = "rpg_npc") -> None:
        """Display a character card with fixed-width field labels and bold text in a panel"""
        from rich.table import Table
        
        # Capitalize field names for display
        def format_label(key: str) -> str:
            return key.replace('_', ' ').title()
        
        # Create a table with two columns
        table = Table(show_header=False, show_lines=False, box=None, padding=0)
        table.add_column("Field", style=self.get_style("rpg_npc"), width=20, no_wrap=True)
        table.add_column("Value", style=self.get_style("llm_output"))
        
        # Iterate over available fields in character_data
        for key, value in character_data.items():
            if value is None:
                value = 'N/A'
            
            # Create bold label
            field_text = Text(format_label(key), style=self.get_style("rpg_npc"))
            field_text.stylize("bold")
            
            # Format value - handle multi-line text
            value_str = str(value)
            table.add_row(field_text, value_str)
        
        panel = Panel(
            table,
            title=title,
            border_style=self.get_style(style_name),
            subtitle_align="right"
        )
        self.console.print(panel)

    def display_all_lore(self, game_lore: Dict[str, any]) -> None:
        """Display all game lore information using console_manager"""
        # Display World Description
        self.display_lore_section(
            title=f"Your world: {game_lore['world']['name']}",
            content=game_lore['world']['description']
        )

        # Display World Rules
        self.display_lore_section(
            title="Rules",
            content=game_lore.get('world_outline', 'No rules defined')
        )

        # Display Starting Point
        self.display_lore_section(
            title="Entry Point",
            content=game_lore.get('start', 'No starting point defined')
        )

        # Display Human Player's Character Card (Charter Winning Conditions)
        if 'human_player' in game_lore:
            self.display_character_card(
                title="Your Player",
                character_data=game_lore['human_player']
            )
        else:
            self.display_lore_section(
                title="Your Player",
                content="No character data available"
            )

        # Display NPC Companion(s)
        if 'npc' in game_lore:
            for npc_name, npc_data in game_lore['npc'].items():
                self.display_character_card(
                    title=f"Companion: {npc_name}",
                    character_data=npc_data
                )
        else:
            self.display_lore_section(
                title="Companion",
                content="No NPC companion assigned"
            )

        # Display Antagonist
        if 'antagonist' in game_lore:
            self.display_character_card(
                title="Your Antagonist",
                character_data=game_lore['antagonist']
            )
        else:
            self.display_lore_section(
                title="Antagonist",
                content="No antagonist defined"
            )

    @property
    def styles(self) -> Dict[str, Style]:
        """Dictionary of predefined styles"""
        return self._styles
