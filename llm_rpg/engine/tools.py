"""
Collection of helper tools needed for the game.
- ObjectDescriptor --> describes objects, their type, strength, action, etc.
TODO: InventoryChange --> detects changes into inventory

# - ObjectDetector --> detects all objects/tools used by the human and the AI player
"""
import copy
import json
import pydantic
from typing import Dict, List, Any

from llm_rpg.templates.base_client import BaseClient
from llm_rpg.templates.tool import BaseTool

from llm_rpg.prompts.response_models import (InventoryItemDescription,
                                             _pick_actions,
                                             InventoryUpdates,
                                             PlayerState,
                                             ValidateClassifyAction)
from llm_rpg.prompts.lore_generation import (gen_obj_est_msgs)


import logging
logger = logging.getLogger(__name__)

# ------------------------------------------------- OBJECT DESCRIPTOR --------------------------------------------------
class ObjectDescriptor:
    """
    Generates descriptions and actions for a list of items (e.g. axe, spell, etc)
    """
    def __init__(self, client: BaseClient) -> None:
        self.client = client
        self.stats = {}
        self.response_model = InventoryItemDescription


    def describe(self, obj: str, **kwargs) -> Dict[str, str]:
        msgs = gen_obj_est_msgs(obj)
        response = self.client.struct_output(msgs, self.response_model, **kwargs)
        self.stats[obj] = response['stats']
        result = response['message'].model_dump()
        result['name'] = result['name'].title()
        return result


# ----------------------------------------------- PLAYER INPUT VALIDATOR -----------------------------------------------
class InputValidator(BaseTool):
    def __init__(self,
                 lore:Dict[str, Any],
                 llm_client: BaseClient):
        """
        Action validator class. It builds system and tass prompts dynamically depending on available input
        :param lore: Dict[str, Any] -- game lore, used to populate known location, world rules, etc.
        :param response_model: pydantic.BaseModel -- response model
        :param llm_client: BaseClient -- LLM client for particular provider
        """
        super().__init__(llm_client, ValidateClassifyAction)
        self.lore_kingdoms_towns = [f"Kingdom \"{x}\" --> Towns: {', '.join(list(lore['towns'][x].keys()))}" for x in
                          lore['towns']]

        # System prompts chunks to be combined later
        self.system_prompt = f"""You are RPG Game Engine. Task for user's action: 
- is a game action, True/False
- validate, True/False
- classify, pick from {_pick_actions}
Instructions for classification: 
- all actions must be clear from the input and the context, ignore suggestions, discussions, offers, etc. 
- default: []
Rules:
{lore['world_outline']}
Following is forbidden:
- contradiction to the world rules and world description
- use items not in their inventory
- gain items or abilities without a reason"""


    def compile_messages(self,
                         action: str,
                         context: str,
                         inventory: List[str] = None,
                         additional_context:str = None,
                         enforce_json_output:bool = False) -> List[Dict[str, str]]:

        sys_prt = copy.copy(self.system_prompt)

        system_message = []
        if enforce_json_output:
            system_message = self.add_struct_sys_prompt()

        TASK_VAL_INPUT_CLS = f"""User: {action}"""
        if context != "":
            TASK_VAL_INPUT_CLS += f"\nContext: {context}"
        if inventory is not None:
            TASK_VAL_INPUT_CLS += f"\nUser inventory: {inventory}"
        if additional_context is not None and additional_context != '':
            TASK_VAL_INPUT_CLS += f"\nUse this additional context: {inventory}"

        return system_message + [
            {'role': 'system', 'content': sys_prt},
            {'role': 'user', 'content': TASK_VAL_INPUT_CLS}]


    def run(self,
                        action: str,
                        context: str,
                        inventory: List[str] = None,
                        additional_context:str = None,
                        enforce_json_output:bool=False,
                        **llm_kwargs) -> pydantic.BaseModel:
        """
        Validates player's action
        :param action: str -- action to validate
        :param context: str -- any additional context, such as previous responses, etc.
        :param inventory: str -- Optional, list of inventory items
        :param additional_context: str -- any additional context
        :param llm_kwargs: Dict[Any, Any] -- any LLM related kwargs
        :return: pydantic.BaseModel -- Pydantic response model
        """
        logger.info("Validating player action")
        __msgs = self.compile_messages(action, context, inventory, additional_context, enforce_json_output)
        return self.submit_messages(__msgs, **llm_kwargs)


# ------------------------------------------------- INVENTORY UPDATER --------------------------------------------------
class InventoryChange(BaseTool):
    def __init__(self, llm_client):
        super().__init__(llm_client, InventoryUpdates)

        self.sys_prt = """You are RPG Game Engine. Detect changes to a player's inventory.
Your instructions:
- If a player picks up, or gains an item add it to the inventory with a positive change_amount.
- If a player loses an item remove it from their inventory with a negative change_amount.
- Only take items that it's clear the player lost.
- Only give items that it's clear the player gained. 
- Ignore all items offered/gifted unless these were accepted.
- Don't make any other item updates.
Never add any thinking."""


    def compile_messages(self,
                         action: str,
                         context: str,
                         inventory: List[str] = None,
                         additional_context:str = None,
                         enforce_json_output:bool=False) -> List[Dict[str, str]]:
        """
        Build the messages/payload for the LLM
        :param action: str -- human action
        :param context: str -- context (e.g. previous actions/etc)
        :param inventory: List[str] -- list of inventory items
        :param additional_context: str -- any additional information to consider
        :param enforce_json_output: bool -- adds system prompt with the JSON schema, default: False
        :return:
        """
        TASK_PRT = f"""User actions: {action}"""
        if context != '':
            TASK_PRT += f"""Context: {context}"""
        TASK_PRT += f"""User's inventory: {inventory}"""
        if additional_context is not None and additional_context != '':
            TASK_PRT += f"Additional context: {additional_context}"

        system_message = []
        if enforce_json_output:
            system_message = self.add_struct_sys_prompt()

        return system_message + [
            {'role': 'system', 'content': self.sys_prt},
            {'role': 'user', 'content': TASK_PRT}
        ]

    def run(self,
                                action: str,
                                context: str,
                                inventory: List[str] = None,
                                additional_context:str = None,
                                enforce_json_output:bool=False,
                                **llm_kwargs) -> pydantic.BaseModel:
        """
        Detects changes into player's inventory
        :param action: str -- human action
        :param context: str -- context (e.g. previous actions/etc)
        :param inventory: List[str] -- list of inventory items
        :param additional_context: str -- any additional information to consider
        :param enforce_json_output: bool -- adds system prompt with the JSON schema, default: False
        :param llm_kwargs: Dict[Any, Any] -- any LLM related kwargs
        :return: pydantic.BaseModel -- Pydantic response model
        """

        logger.info("Detecting inventory change")
        __msgs = self.compile_messages(action, context, inventory, additional_context, enforce_json_output)
        return self.submit_messages(__msgs, **llm_kwargs)

# ----------------------------------------- PLAYER'S PHYSICAL/MENTAL UPDATER -------------------------------------------
class PlayerState(BaseTool):
    def __init__(self, llm_client):
        super().__init__(llm_client, PlayerState)
        self.sys_prt = "You are RPG Game Engine. Task: detect changes in physical and mental state of the player."

    def compile_messages(self,
                         action: str,
                         context: str,
                         additional_context:str = None,
                         enforce_json_output:bool=False) -> List[Dict[str, str]]:

        task = f"Player: {action}"
        if context is not None and context != "":
            task += f"\nContext: {context}"
        if additional_context is not None and additional_context != "":
            task += f"\nAdditional context: {additional_context}"

        system_message = []
        if enforce_json_output:
            system_message = self.add_struct_sys_prompt()

        return system_message + [
            {'role': 'system', 'content': self.sys_prt},
            {'role': 'user', 'content': task}
        ]

    def run(self,action: str,
            context: str,
            additional_context:str = None,
            enforce_json_output:bool=False,
            **llm_kwargs):
        """
        Identifies changes of physical and mental state of a player
        :param action: str -- human action
        :param context: str -- context (e.g. previous actions/etc)
        :param additional_context: str -- any additional information to consider
        :param enforce_json_output: bool -- adds system prompt with the JSON schema, default: False
        :param llm_kwargs: Dict[Any, Any] -- any LLM related kwargs
        :return: pydantic.BaseModel -- Pydantic response model
        """
        logger.info("Detecting inventory change")
        __msgs = self.compile_messages(action, context, additional_context, enforce_json_output)
        return self.submit_messages(__msgs, **llm_kwargs)