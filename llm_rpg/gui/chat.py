import threading
from typing import Optional, Callable, Any, List, Tuple
from queue import Queue, Empty
from rich.live import Live
from rich.panel import Panel
from rich.text import Text
from rich.spinner import Spinner
from rich.console import Group
from llm_rpg.clients.dummy_llm import DummyLLM
from llm_rpg.gui.console_manager import ConsoleManager

import logging
logger = logging.getLogger(__name__)

class RPGChatInterface:
    """Main RPG chat interface with proper threading for streaming"""
    # WIP
    # hooks for user input processing are intended to call a "game driving" class methods
    # user_input_processing_commands -->    1) ai_response --> final step for streaming the final response
    #                                       2) process_input --> user input processing
    # post_processing_commands --> 1) exit -- all necessary actions to make upon existing the game
    def __init__(self, console_manager: ConsoleManager):
        self.console = console_manager.console
        self.styles = console_manager.styles
        self.running = False

        # Service commands configuration
        self.service_commands = ["/help", "/inventory", "/stats"]
        self.service_command_hooks = {}

        # Processing user input
        self.user_input_processing_commands = []
        self.user_input_processing_hooks = {}

        # Post-processing streaming response
        self.post_processing_commands = []
        self.post_processing_hooks = {}

        self.__hook_stacks = set(['service', 'user_input', 'post_processing'])
        self.__exit_kws = set(["--exit", "--quit", "!q:"])

        # Streaming state
        self.streaming_active = False
        self.response_queue = Queue()

    def _is_service_command(self, text: str) -> bool:
        """Check if the input is a service command"""
        return any(text.startswith(cmd) for cmd in self.service_commands)

    def _process_service_command(self, command: str) -> None:
        """Handle service commands using registered hooks"""
        cmd_parts = command.split()
        base_cmd = cmd_parts[0]

        if base_cmd in self.service_command_hooks:
            self.console.print(
                Text(f"⚙️ Processing: {base_cmd}", style=self.styles.get_style("service_command"))
            )
            self.service_command_hooks[base_cmd](cmd_parts[1:] if len(cmd_parts) > 1 else None)
        else:
            self.console.print(
                Text(f"⚠️ Unknown command: {base_cmd}", style=self.styles.get_style("error"))
            )

    def __register_service_command(self, command: str, handler: Callable) -> None:
        """Register a handler for a service command"""
        self.service_commands.append(command)
        self.service_command_hooks[command] = handler
        logger.info(f"Registered \"{command}\" as service command")

    def __register_input_processing_command(self, command: str, handler: Callable) -> None:
        """Register a handler for user input processing"""
        self.user_input_processing_commands.append(command)
        self.user_input_processing_hooks[command] = handler
        logger.info(f"Registered \"{command}\" as user input processing command")

    def __register_post_processing_command(self, command: str, handler: Callable) -> None:
        """Register a handler for a post-streaming/response processing"""
        self.post_processing_commands.append(command)
        self.post_processing_hooks[command] = handler
        logger.info(f"Registered \"{command}\" as user post-response processing command")

    def register_command_hooks(self, stack: str, command: str, handler: Callable) -> None:
        """
        Base method to register command hooks

        :param stack: 
        :param command:
        :param handler:
        :return:
        """
        #  set('service', 'user_input', 'post_processing')
        if stack not in self.__hook_stacks:
            logger.error(f"Hook stack not recognised. Got {stack}, expected: {self.__hook_stacks}")
            raise ValueError(f"Hook stack not recognised. Got {stack}, expected: {self.__hook_stacks}")

        if stack.lower() == 'service':
            self.__register_service_command(command, handler)
        if stack.lower() == "user_input" or stack.lower() == "user":
            self.__register_input_processing_command(command, handler)
        if stack.lower() == "post_processing" or stack.lower() == 'post':
            self.__register_post_processing_command(command, handler)

    def _show_typing_indicator(self) -> Live:
        """Show animated typing indicator"""
        return Live(
            Group(
                Spinner('dots', style=self.styles.get_style("typing")),
                Text("Thinking...", style=self.styles.get_style("typing"))
            ),
            refresh_per_second=12,
            console=self.console
        )

    def _generate_response_in_thread(self, processed_input: str):
        """Run response generation in background thread"""
        try:
            # TODO: replace with a proper response generator from the processing hook
            for chunk in self.user_input_processing_hooks['ai_response'](processed_input):
                self.response_queue.put(chunk)
            self.response_queue.put(None)  # Signal completion
        except Exception as e:
            self.response_queue.put(("error", str(e)))

    def _display_streaming_response(self, processed_input: str, title: str = "GAME") -> str:
        """Display response stream with proper threading and customizable title"""
        # Start response generation in background
        thread = threading.Thread(
            target=self._generate_response_in_thread,
            args=(processed_input,),
            daemon=True
        )
        thread.start()

        full_response = []
        with self._show_typing_indicator() as live:
            while True:
                try:
                    item = self.response_queue.get(timeout=0.01)

                    if item is None:  # Generation complete
                        break
                    elif isinstance(item, tuple) and item[0] == "error":
                        self.console.print(
                            Text(f"Error: {item[1]}", style=self.styles.get_style("error"))
                        )
                        # TODO: add necessary operations on exit
                        break

                    full_response.append(item)
                    panel = Panel(
                        Text("".join(full_response), style=self.styles.get_style("llm_output")),
                        title=title,
                        border_style=self.styles.get_style("rpg_npc"),
                        subtitle_align="right"
                    )
                    live.update(panel)

                except Empty:
                    continue

        thread.join()
        return "".join(full_response)


    def _display_static_response(self, response_data: dict) -> str:
        """Display a pre-generated static response with custom title"""
        response_text = response_data["response"]
        title = response_data.get("title", "GAME")

        panel = Panel(
            Text(response_text, style=self.styles.get_style("llm_output")),
            title=title,
            border_style=self.styles.get_style("rpg_npc"),
            subtitle_align="right"
        )
        self.console.print(panel)
        return response_text


    def _process_user_message(self, user_input: str) -> Tuple[Any, str]:
        """Process user message and return result with display type"""
        if self.user_input_processing_hooks != {}:
            processed_result = self.user_input_processing_hooks['process_input'](user_input)
        else:
            processed_result = ""

        # Determine display type and return both result and type
        if isinstance(processed_result, dict) and "response" in processed_result:
            return processed_result, "static"
        else:
            return processed_result, "streaming"


    def _handle_user_message(self, user_input: str) -> str:
        """Orchestrate the complete flow for handling user messages"""
        # Process the message
        processed_result, display_type = self._process_user_message(user_input)

        # Display based on type
        if display_type == "static":
            return self._display_static_response(processed_result)
        else:  # streaming
            return self._display_streaming_response(processed_result)


    def _is_game_quit(self, message) -> bool:
        if message.lower() in self.__exit_kws:
            return True
        return False

    def start(self):
        """Main chat loop"""
        self.running = True
        self.console.print(
            Panel("Welcome to the RPG Chat!", style=self.styles.get_style("rpg_system"))
        )

        try:
            while self.running:
                user_input = self.console.input(
                    Text("You: ", style=self.styles.get_style("rpg_player"))
                ).strip()

                if self._is_game_quit(user_input):
                    self.running = False
                    self.post_processing_hooks['exit']()
                    break

                if self._is_service_command(user_input):
                    self._process_service_command(user_input)
                else:
                    # Process and display the game response
                    game_response = self._handle_user_message(user_input)

        except KeyboardInterrupt:
            self.running = False
        finally:
            self.console.print("Chat session ended.", style=self.styles.get_style("system"))


# External processing functions
# ------ Mock-up simulations ------
import time, random
def process_input_placeholder(user_input: str) -> str:
    """Enhanced input processing with thinking emulation"""
    # Emulate parsing and understanding
    time.sleep(0.4)  # Processing delay

    # Add RPG-style processing effects
    processing_phrases = [
        f"\n*The mage studies your words carefully*",
        f"\n*Ancient runes glow as your message is analyzed*",
        f"\n*The spirit guide nods slowly*"
    ]

    # Return enriched input with processing flavor
    return f"{user_input}{random.choice(processing_phrases)}"


def placeholder_generate_response(processed_input: str):
    """Enhanced RPG response generator with dramatic pacing"""
    # Initial delay before responding
    time.sleep(1.2)

    # Stage 1: Acknowledgment
    yield f"\n*adjusts robes* Your words about '{processed_input.split()[0]}'..."
    time.sleep(0.01)

    # Stage 2: Dramatic build-up
    dramatic_pauses = [
        "\n*casts divination spell*",
        "\n*consults ancient tome*",
        "\n*gazes into crystal ball*"
    ]
    yield random.choice(dramatic_pauses)
    time.sleep(0.15)

    # Stage 3: Revelation
    revelations = [
        "\nThe spirits reveal...",
        "\nThe stars align to show...",
        "\nMy magical senses perceive..."
    ]
    yield random.choice(revelations)
    time.sleep(0.8)

    # Stage 4: Actual response
    response_body = [
        "\nYou must seek the lost artifact in the Caves of Despair!",
        "\nBeware! The dark lord's minions are watching you...",
        "\nI foresee a great battle in your near future!",
        "\nThe answer lies eastward, beyond the Mountains of Madness."
    ]
    yield random.choice(response_body)
    time.sleep(0.5)

    # Final prompt
    yield "\n\n*leans forward* What will you do next, adventurer?"