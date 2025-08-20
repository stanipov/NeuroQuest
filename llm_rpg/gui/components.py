from typing import Optional, Callable, Any
from rich.live import Live
from rich.panel import Panel
from rich.text import Text
from rich.console import Console, Group
from rich.spinner import Spinner

class ChatComponents:
    """Reusable UI components for the chat interface"""
    def __init__(self, console: Console, styles: 'ConsoleStyles'):
        self.console = console
        self.styles = styles

    def create_message_panel(self, sender: str, message: str, is_user: bool = False) -> Panel:
        """Create a styled message panel"""
        style = self.styles.get_style("rpg_player" if is_user else "rpg_npc")
        return Panel(
            Text(message, style=style),
            title=sender,
            border_style=style,
            subtitle="You" if is_user else None
        )

    def create_typing_indicator(self) -> Group:
        """Create a typing indicator animation"""
        return Group(
            Spinner('dots', style=self.styles.get_style("typing")),
            Text("Thinking...", style=self.styles.get_style("typing"))
        )

    def print_service_command(self, command: str) -> None:
        """Display a service command in the appropriate style"""
        self.console.print(
            Text(f"⚙️ {command}", style=self.styles.get_style("service_command"))
        )

    def print_error(self, message: str) -> None:
        """Display an error message"""
        self.console.print(
            Text(f"Error: {message}", style=self.styles.get_style("error"))
        )