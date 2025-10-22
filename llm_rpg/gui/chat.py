import threading
from typing import Optional, Callable, Any, List, Tuple, Dict
from queue import Queue, Empty
from enum import Enum
from pydantic import BaseModel, Field
from rich.live import Live
from rich.panel import Panel
from rich.text import Text
from rich.spinner import Spinner
from rich.console import Group
from llm_rpg.clients.dummy_llm import DummyLLM
from llm_rpg.gui.console_manager import ConsoleManager

import logging

logger = logging.getLogger(__name__)


class MessageStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"


class InputProcessingStatus(str, Enum):
    DONE = "done"
    CONTINUE = "continue"


class HookResponse(BaseModel):
    """Model for hook response data"""
    message: str = Field(default="")
    role: str = Field(default="GAME")
    message_status: MessageStatus = Field(default=MessageStatus.SUCCESS)
    input_processing_status: InputProcessingStatus = Field(default=InputProcessingStatus.CONTINUE)


class DisplayType(str, Enum):
    STATIC = "static"
    STREAMING = "streaming"


class StaticResponseData(BaseModel):
    """Model for static response data"""
    response: str
    title: str = "GAME"


class RPGChatInterface:
    """Main RPG chat interface with proper threading for streaming"""

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

        self.__hook_stacks = {'service', 'user_input', 'post_processing'}
        self.__exit_kws = {"--exit", "--quit", "!q:"}

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

        :param stack: hook stack type ('service', 'user_input', 'post_processing')
        :param command: command string
        :param handler: handler function
        """
        if stack not in self.__hook_stacks:
            logger.error(f"Hook stack not recognised. Got {stack}, expected: {self.__hook_stacks}")
            raise ValueError(f"Hook stack not recognised. Got {stack}, expected: {self.__hook_stacks}")

        if stack.lower() == 'service':
            self.__register_service_command(command, handler)
        elif stack.lower() in {"user_input", "user"}:
            self.__register_input_processing_command(command, handler)
        elif stack.lower() in {"post_processing", "post"}:
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

    def _generate_response_in_thread(self, responses: List[HookResponse]):
        """Run response generation in background thread"""
        try:
            for chunk in self.user_input_processing_hooks['ai_response'](responses):
                self.response_queue.put(chunk)
            self.response_queue.put(None)  # Signal completion
        except Exception as e:
            self.response_queue.put(("error", str(e)))

    def _display_streaming_response(self, responses: List[HookResponse], title: str = "GAME") -> str:
        """Display response stream with proper threading and customizable title"""
        # Start response generation in background
        thread = threading.Thread(
            target=self._generate_response_in_thread,
            args=(responses,),
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

    def _display_static_response(self, response_data: StaticResponseData) -> str:
        """Display a pre-generated static response with custom title"""
        panel = Panel(
            Text(response_data.response, style=self.styles.get_style("llm_output")),
            title=response_data.title,
            border_style=self.styles.get_style("rpg_npc"),
            subtitle_align="right"
        )
        self.console.print(panel)
        return response_data.response

    def _display_hook_response(self, hook_response: HookResponse) -> None:
        """Display a single hook response message"""
        if hook_response.message:
            style = (self.styles.get_style("success")
                     if hook_response.message_status == MessageStatus.SUCCESS
                     else self.styles.get_style("error"))

            panel = Panel(
                Text(hook_response.message, style=style),
                title=hook_response.role,
                border_style=self.styles.get_style("rpg_npc"),
                subtitle_align="right"
            )
            self.console.print(panel)

    def _process_user_input_until_done(self, user_input: str) -> List[HookResponse]:
        """Process user input until input_processing_status is 'done'"""
        responses = []

        while True:
            if not self.user_input_processing_hooks:
                # Fallback if no hooks registered
                responses.append(HookResponse(
                    message="No input processing hooks registered",
                    role="SYSTEM",
                    message_status=MessageStatus.FAILED,
                    input_processing_status=InputProcessingStatus.DONE
                ))
                break

            hook_response_dict = self.user_input_processing_hooks['process_input'](user_input)
            hook_response = HookResponse(**hook_response_dict)
            responses.append(hook_response)

            # Display the message if not empty
            if hook_response.message:
                self._display_hook_response(hook_response)

            # Check if processing is complete
            if hook_response.input_processing_status == InputProcessingStatus.DONE:
                break

        return responses

    def _process_user_message(self, user_input: str) -> Tuple[Any, DisplayType]:
        """Process user message and return result with display type"""
        responses = self._process_user_input_until_done(user_input)

        # After input processing is done, get the final AI response
        if self.user_input_processing_hooks and 'ai_response' in self.user_input_processing_hooks:
            return responses, DisplayType.STREAMING
        else:
            # Fallback static response if no ai_response hook
            final_message = responses[-1].message if responses else "No response generated"
            static_response = StaticResponseData(response=final_message)
            return static_response, DisplayType.STATIC

    def _handle_user_message(self, user_input: str) -> str:
        """Orchestrate the complete flow for handling user messages"""
        # Process the message
        processed_result, display_type = self._process_user_message(user_input)

        # Display based on type
        if display_type == DisplayType.STATIC:
            return self._display_static_response(processed_result)
        else:  # streaming
            return self._display_streaming_response(processed_result)

    def _is_game_quit(self, message: str) -> bool:
        """Check if the message is a quit command"""
        return message.lower() in self.__exit_kws

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
                    if 'exit' in self.post_processing_hooks:
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