from rich.panel import Panel
from rich.table import Table
from rich.text import Text

import time

from typing import Dict, Any, Optional
from llm_rpg.templates.game_menu import Menu
from llm_rpg.gui.console_manager import ConsoleManager

# -------------------------- Set of global parameters --------------------------
G_INV_INPUT_SLEEP_S = 1
G_HEADER = "⚔️ NeuroQuest ⚔️"

# -------------------------- Components for the Main Game Menu --------------------------
class MainMenu(Menu):
    """Main menu of the game"""
    def __init__(self, console_manager: ConsoleManager, io_instance: Any):
        super().__init__(console_manager)
        self.io = io_instance
        self.return_data = {
            "new_game": False,
            "new_game_params": None,
            "load_game": -1
        }

    def display(self) -> Dict[str, Any]:
        """Display the main menu and handle user interaction"""
        while True:
            self.clear_screen()
            self.display_header(G_HEADER)

            menu = Table.grid(padding=(1, 4))
            menu.add_row("1. New Game")
            menu.add_row("2. Load Game")
            menu.add_row("3. Exit")

            self.console.print(
                Panel.fit(
                    menu,
                    title="Main Menu",
                    border_style=self.console_manager.get_style('menu')
                ),
                justify="center"
            )

            choice = self.get_numeric_input("Choose your destiny (1-3): ", 1, 3)
            if choice is None:
                continue

            if choice == 1:
                self.return_data["new_game"] = True
                self.return_data["new_game_params"] = NewGameMenu(self.console_manager).display()
                return self.return_data
            elif choice == 2:
                load_menu = LoadGameMenu(self.console_manager, self.io)
                loaded_game = load_menu.display()
                if loaded_game is None:  # User chose to go back
                    continue
                self.return_data["new_game"] = False
                self.return_data["load_game"] = loaded_game
                return self.return_data
            elif choice == 3:
                self.console.print(
                    Text("Farewell, adventurer!", style=self.console_manager.get_style('info')),
                    justify="center"
                )
                exit()

class NewGameMenu(Menu):
    """Menu for configuring new game settings"""
    def __init__(self, console_manager: ConsoleManager):
        super().__init__(console_manager)
        self.game_settings = {
            'world_setting': 'fantasy',
            'world_type': 'dark',
            'kingdoms': 3,
            'towns_per_kingdom': 3,
            'companions': 1
        }

    def display(self) -> Dict[str, Any]:
        """Display and handle new game configuration"""
        while True:
            self.clear_screen()
            self.display_header("⚙️ New Game Configuration ⚙️")

            menu = Table.grid(padding=(1, 4))
            menu.add_row(f"1. World Setting (Current: {self.game_settings['world_setting']})")
            menu.add_row(f"2. World Type (Current: {self.game_settings['world_type']})")
            menu.add_row(f"3. Number of Kingdoms (Current: {self.game_settings['kingdoms']})")
            menu.add_row(f"4. Towns per Kingdom (Current: {self.game_settings['towns_per_kingdom']})")
            menu.add_row(f"5. Number of Companions (Current: {self.game_settings['companions']})")
            menu.add_row("6. Done/Back")

            self.console.print(
                Panel.fit(
                    menu,
                    title="Configuration Options",
                    border_style=self.console_manager.get_style('menu')
                ),
                justify="center"
            )

            choice = self.get_numeric_input("Select an option (1-6): ", 1, 6)
            if choice is None:
                continue

            if choice == 1:
                self.game_settings['world_setting'] = self.configure_world_setting() or self.game_settings['world_setting']
            elif choice == 2:
                self.game_settings['world_type'] = self.configure_world_type() or self.game_settings['world_type']
            elif choice == 3:
                self.game_settings['kingdoms'] = self.configure_numeric_setting(
                    "Number of Kingdoms", self.game_settings['kingdoms'], 1, 10)
            elif choice == 4:
                self.game_settings['towns_per_kingdom'] = self.configure_numeric_setting(
                    "Towns per Kingdom", self.game_settings['towns_per_kingdom'], 1, 10)
            elif choice == 5:
                self.game_settings['companions'] = self.configure_numeric_setting(
                    "Number of Companions", self.game_settings['companions'], 1, 5)
            elif choice == 6:
                return self.game_settings

    def configure_world_setting(self) -> Optional[str]:
        """Configure world setting option"""
        return self._configure_choice_menu(
            "🌍 World Setting 🌍",
            ["Fantasy", "Sci-Fi"],
            ["fantasy", "sci-fi"]
        )

    def configure_world_type(self) -> Optional[str]:
        """Configure world type option"""
        return self._configure_choice_menu(
            "🌑 World Type 🌑",
            ["Dark", "Neutral", "Funny"],
            ["dark", "neutral", "funny"]
        )

    def _configure_choice_menu(self, title: str, options: list[str], values: list[str]) -> Optional[str]:
        """Generic method for choice-based configuration"""
        while True:
            self.clear_screen()
            self.display_header(title)

            menu = Table.grid(padding=(1, 4))
            for i, option in enumerate(options, 1):
                menu.add_row(f"{i}. {option}")
            menu.add_row(f"{len(options)+1}. Back")

            self.console.print(
                Panel.fit(
                    menu,
                    title="Available Options",
                    border_style=self.console_manager.get_style('menu')
                ),
                justify="center"
            )

            choice = self.get_numeric_input(f"Choose an option (1-{len(options)+1}): ", 1, len(options)+1)
            if choice is None or choice == len(options)+1:
                return None
            return values[choice-1]

    def configure_numeric_setting(self, name: str, current: int, min_val: int, max_val: int) -> int:
        """Configure numeric settings"""
        while True:
            self.clear_screen()
            self.display_header(f"🔢 Configure {name} 🔢")

            self.console.print(
                Text(f"Current value: {current}", style=self.console_manager.get_style('info')),
                justify="center"
            )

            choice = self.get_numeric_input(
                f"Enter new value ({min_val}-{max_val}) or 'back': ",
                min_val,
                max_val
            )
            if choice is not None:
                return choice
            return current

class LoadGameMenu(Menu):
    """Menu for loading saved games"""
    def __init__(self, console_manager: ConsoleManager, io_instance: Any):
        super().__init__(console_manager)
        self.io = io_instance

    def display(self) -> Optional[int]:
        """Display and handle saved game loading"""
        while True:
            self.clear_screen()
            self.display_header("💾 Load Saved Game 💾")

            games = self.io.get_all_games()

            if games.empty:
                self.console.print(
                    Text("No saved games found!", style=self.console_manager.get_style('error')),
                    justify="center"
                )
                time.sleep(2)
                return None

            table = Table(title="Saved Games", border_style=self.console_manager.get_style('menu'))
            table.add_column("#", style=self.console_manager.get_style('info'))
            table.add_column("Description", style=self.console_manager.get_style('option'))
            table.add_column("Date", style=self.console_manager.get_style('info'))

            for idx, row in games[["description", "datetime_utc"]].iterrows():
                date_str = row["datetime_utc"].strftime("%Y-%m-%d %H:%M")
                table.add_row(str(idx + 1), row["description"], date_str)

            self.console.print(table, justify="center")

            choice = self.get_numeric_input(
                "Select a game to load (or 'back' to return): ",
                1,
                len(games)
            )
            if choice is None:  # User chose 'back'
                return None
            return choice - 1

# -------------------------- Game Menu Facade --------------------------
class GameMenu:
    """Facade class for managing game menus"""
    def __init__(self, console_manager: ConsoleManager, io_instance: Any):
        self.console_manager = console_manager
        self.io = io_instance

    def main_menu(self) -> Dict[str, Any]:
        """Entry point to the menu system"""
        return MainMenu(self.console_manager, self.io).display()