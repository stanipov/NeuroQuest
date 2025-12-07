"""
Main game logic here
"""
from typing import List, Dict, Any
from random import shuffle
from llm_rpg.templates.tool import BaseTool
from llm_rpg.templates.base_client import BaseClient
from llm_rpg.engine.memory import SQLGameMemory
from llm_rpg.utils.config import ConfigManager
from llm_rpg.engine.npc_ai import NPC
from llm_rpg.engine.tools import InputValidator

from llm_rpg.gui.chat import InputProcessingStatus, HookResponse

from llm_rpg.prompts.response_models import ValidateClassifyAction
from llm_rpg.prompts.response_models import _pick_actions as PossibleGameActions

from copy import copy as _cp
import logging
logger = logging.getLogger(__name__)


"""
There could be several NPCs. For each of them we consequently call respective NPC instance. These will be triggered from 
the _process_user_message() method of RPGChatInterface class. The method will iterate till it receives a signal to stop 
and call to generate the game response. Therefore the GameAI shall have a state that cycles through the NPCs.

This state shall be robust against errors/failed calls. Would a simple iterator from cycles (Python built-in) suffice? 

1. TBD: it's convenient to use the state to pick another NPC for processing. This can add randomness to the game. --> Special class?

2. TBD: how do we process/collect context for the final game action? I mean all clarifications that the player may ask, e.g. 
about the locations, lore, history, etc. What part of it do we feed into an NPC? A rag solution can be useful.

"""

class GameAI(BaseTool):
    def __init__(self,
                 lore: Dict[str, Any],
                 llm_registry: Dict[str, BaseClient],
                 memory: SQLGameMemory,
                 config_mgr: ConfigManager,
                 **kwargs):

        self.config = config_mgr
        self.lore = _cp(lore)
        self.llm_registry = llm_registry

        # internal parameters
        self.__game_response_generated: bool = False
        self.__user_input_validated: bool = False
        self.__npcs = list(self.lore['npc'].keys()) if len(self.lore['npc'].keys())>0 else None
        self.__npc_queue = self.__gen_npc_queue()
        self.__verified_input = ValidateClassifyAction()

        # core agents
        self.npc_ai = {}
        self.input_validator = None
        self.game_ai = None
        self.qa_ai = None

        # SQL memory
        self.memory = memory

        # parameters
        self.enforce_json_output = False
        self.tools_kwargs = {
            "lore_llm": kwargs.get('lore_llm', None),
            "npc_ai_llm": kwargs.get('input_validator', None),
            "game_ai_llm": kwargs.get('game_ai_llm', None),
            "input_validator": kwargs.get('input_validator', None)
        }
        self.game_cfg = self.config.get_game_config()


    def __gen_npc_queue(self) -> List[str]|None:
        return shuffle(self.__npcs) if self.__npcs else None

    def __init_npc_ai(self):
        """Inits all instances for NPC AIs"""
        # list(lore['npc'].keys())
        game_cfg = self.config.get_game_config()
        if self.llm_registry['npc_ai_llm'] is None:
            logger.error(f"No LLM found for NPC AI! Will use LLM for main game response")

        for npc in list(self.lore['npc'].keys()):
            self.npc_ai[npc] = NPC(self.llm_registry['npc_ai_llm'], self.memory, self.lore, npc, game_cfg['npc_chat_history'])


    def __init_game_response(self):
        """Init instance to generate game response"""
        pass


    def __init_input_validator(self):
        """Init user input validator -- InputValidator from llm_rpg.engine.tools"""
        if self.llm_registry['input_validator'] is not None:
            self.input_validator = InputValidator(self.lore, self.llm_registry['input_validator'])
        else:
            self.input_validator = None

    def __init_non_game_response(self):
        """Init an instance to provided non-game response, e.g. lore question, etc"""
        pass


    def verify_user_input(self, message: str) -> ValidateClassifyAction|None:
        """Validates and classifies user (human) input"""
        if self.input_validator is not None:
            user_inventory = self.memory.list_inventory_items('human')
            last_turn = self.memory.get_most_recent_turn()
            context = last_turn['ai_response']
            additional_context = None
            return self.input_validator.run(action = message,
                                                context = context,
                                                inventory = user_inventory,
                                                additional_context = additional_context,
                                                enforce_json_output=self.enforce_json_output,
                                                **self.tools_kwargs['input_validator'])
        else:
            logger.debug(f"Input validator is not available, resorting to default, assuming the input was a game action")
            return ValidateClassifyAction()


    def __generate_npc_response(self) -> HookResponse:
        """Generates actions of the NPCs

        ==========================================================
        FYI
        class InputProcessingStatus(str, Enum):
            DONE = "done"
            CONTINUE = "continue"

        class HookResponse(BaseModel):
            "Model for hook response data"
            message: str = Field(default="")
            role: str = Field(default="GAME")
            message_status: MessageStatus = Field(default=MessageStatus.SUCCESS)
            input_processing_status: InputProcessingStatus = Field(default=InputProcessingStatus.CONTINUE)
        ==========================================================
        """
        return HookResponse()


    def __generate_game_response(self):
        """ Final response of the game, it can be a game action or another clarification response, e.g. lore question
         Use self.__verified_input to route on a response -- game or something else
         """
        self.__game_response_generated = True
        yield


    def process_user_input(self, message: str):
        """Processes user input"""

        # Response expected by the chat._process_user_message():
        #class HookResponse(BaseModel):
        #    """Model for hook response data"""
        #    message: str = Field(default="")
        #    role: str = Field(default="GAME")
        #    message_status: MessageStatus = Field(default=MessageStatus.SUCCESS)
        #    input_processing_status: InputProcessingStatus = Field(default=InputProcessingStatus.CONTINUE)


        # this is response from the validator
        #class ValidateClassifyAction(BaseModel):
        #   """Validator response model"""
        #   is_game_action: bool =  Field(validation_alias='is_game_action', description="True/False")
        #   non_game_action: str = Field(validation_alias="non_game_action", description=_fld_reason_desc)
        #   valid: bool = Field(validation_alias='valid', description="Valid game action? True or False")
        #   valid_reason: List[ValidReason] = Field(description=_fld_val_reason_desc, default_factory=list)
        #   action_type: list[ActionTypes] = Field(description='List of actions', default_factory=list)

        if not self.__user_input_validated:
            # verify the human input
            self.__verified_input = self.verify_user_input(message)
            self.__user_input_validated = True
            self.__game_response_generated = False
            self.__npc_queue = self.__gen_npc_queue()

        if self.__verified_input.is_game_action:
            # trigger game action
            # which is NPC response if any and main AI response
            #game_actions = self.__verified_input.action_type

            if not self.__game_response_generated and self.__npc_queue:
                return self.__generate_npc_response()

        else:
            return HookResponse(input_processing_status=InputProcessingStatus.DONE, message="")
