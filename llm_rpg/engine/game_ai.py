from typing import List, Dict, Any, Generator
from random import shuffle
from llm_rpg.templates.tool import BaseTool
from llm_rpg.templates.base_client import BaseClient
from llm_rpg.engine.memory import SQLGameMemory
from llm_rpg.utils.config import ConfigManager
from llm_rpg.engine.npc_ai import NPC
from llm_rpg.engine.tools import InputValidator
from llm_rpg.gui.chat import HookResponse, InputProcessingStatus
from llm_rpg.prompts.response_models import ValidateClassifyAction

from copy import copy as _cp
import logging
import random
import string

logger = logging.getLogger(__name__)


class GameAI:
    def __init__(
        self,
        lore: Dict[str, Any],
        llm_registry: Dict[str, BaseClient],
        memory: SQLGameMemory,
        config_mgr: ConfigManager,
        **kwargs,
    ):
        self.config = config_mgr
        self.lore = _cp(lore)
        self.llm_registry = llm_registry

        self.__game_response_generated: bool = False
        self.__user_input_validated: bool = False
        self.__npcs = (
            list(self.lore["npc"].keys()) if len(self.lore["npc"].keys()) > 0 else None
        )
        self.__npc_queue = self.__gen_npc_queue()
        self.__verified_input = ValidateClassifyAction()

        self.npc_ai = {}
        self.input_validator = None
        self.game_ai = None
        self.qa_ai = None

        self.memory = memory

        self.enforce_json_output = False
        self.tools_kwargs = {
            "lore_llm": kwargs.get("lore_llm", None),
            "npc_ai_llm": kwargs.get("input_validator", None),
            "game_ai_llm": kwargs.get("game_ai_llm", None),
            "input_validator": kwargs.get("input_validator", None),
        }
        self.game_cfg = self.config.get_game_config()

        self.__init_npc_ai()
        self.__init_input_validator()

    def __gen_npc_queue(self) -> List[str] | None:
        if not self.__npcs:
            return None
        queue = self.__npcs.copy()
        shuffle(queue)
        return queue

    def __init_npc_ai(self):
        game_cfg = self.config.get_game_config()
        if self.llm_registry["npc_ai_llm"] is None:
            logger.error(
                f"No LLM found for NPC AI! Will use LLM for main game response"
            )

        for npc in list(self.lore["npc"].keys()):
            self.npc_ai[npc] = NPC(
                self.llm_registry["npc_ai_llm"],
                self.memory,
                self.lore,
                npc,
                game_cfg["npc_chat_history"],
            )

    def __init_input_validator(self):
        if self.llm_registry["input_validator"] is not None:
            self.input_validator = InputValidator(
                self.lore, self.llm_registry["input_validator"]
            )
        else:
            self.input_validator = None

    def verify_user_input(self, message: str) -> ValidateClassifyAction | None:
        if self.input_validator is not None:
            user_inventory = self.memory.list_inventory_items("human")
            last_turn_rows = self.memory.get_last_n_rows(
                self.memory.history_tbl_name, 1
            )
            if last_turn_rows:
                context = last_turn_rows[0]["ai_response"]
            else:
                context = ""
            additional_context = None
            return self.input_validator.run(
                action=message,
                context=context,
                inventory=user_inventory,
                additional_context=additional_context,
                enforce_json_output=self.enforce_json_output,
                **self.tools_kwargs["input_validator"],
            )
        else:
            logger.debug(
                f"Input validator is not available, assuming the input was a game action"
            )
            return ValidateClassifyAction()

    def generate_non_game_response(self) -> str:
        return "Non Game Action"

    def process_invalid_input(self) -> str:
        return "Invalid action"

    def generate_game_action(self) -> Generator[str, None, None]:
        """Placeholder generator that yields random symbols for streaming"""
        for _ in range(20):
            yield random.choice(string.ascii_letters + string.digits + " .,;:!?")

    def process_user_input(self, message: str) -> Generator[HookResponse, None, None]:
        """Process user input and yield NPC responses one at a time.

        Yields HookResponse objects for each NPC in the queue. The last response
        will have input_processing_status=InputProcessingStatus.DONE.

        Args:
            message: User input to process

        Yields:
            HookResponse: One response per NPC, or single response for invalid/non-game actions
        """
        self.__verified_input = self.verify_user_input(message)

        # Handle invalid input
        if not self.__verified_input.valid:
            yield HookResponse(
                message=self.process_invalid_input(),
                role="GAME",
                message_status="failed",
                input_processing_status=InputProcessingStatus.DONE,
            )
            return

        # Handle non-game actions
        if not self.__verified_input.is_game_action:
            response = self.generate_non_game_response()
            yield HookResponse(
                message=response,
                role="GAME",
                message_status="success",
                input_processing_status=InputProcessingStatus.DONE,
            )
            return

        # Initialize for game action processing
        self.__user_input_validated = True
        self.__game_response_generated = False
        self.__npc_queue = self.__gen_npc_queue()

        # Yield NPC responses one at a time
        while self.__npc_queue:
            npc = self.__npc_queue.pop(0)
            npc_response = self.npc_ai[npc].run()
            is_last_npc = len(self.__npc_queue) == 0

            yield HookResponse(
                message=npc_response.action,
                role=npc,
                message_status="success",
                input_processing_status=InputProcessingStatus.DONE
                if is_last_npc
                else InputProcessingStatus.CONTINUE,
            )

        self.__game_response_generated = True

    def get_game_action_stream(self) -> Generator[str, None, None]:
        """Get the game action streaming generator"""
        return self.generate_game_action()

    def is_game_response_generated(self) -> bool:
        """Check if game response has been generated"""
        return self.__game_response_generated
