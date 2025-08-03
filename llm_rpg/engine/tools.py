"""
Collection of helper tools needed for the game.
- ObjectDescriptor --> describes objects, their type, strength, action, etc.
TODO: InventoryChange --> detects changes into inventory

# - ObjectDetector --> detects all objects/tools used by the human and the AI player
"""
import copy
import logging

import pydantic

logger = logging.getLogger(__name__)

from typing import Dict, List, Any

from llm_rpg.templates.base_client import BaseClient
from llm_rpg.prompts.gameplay import (STORY_TELLER_SYS_PRT,
                                      INVENTORY_CHANGE_SYS_PROMPT,
                                      gen_story_telling_msg)
from llm_rpg.prompts.response_models import Inventory, ValidAction
from llm_rpg.prompts.lore_generation import (gen_obj_est_msgs, OBJECT_DESC)
from llm_rpg.utils.helpers import parse2structure


# ------------------------------------------------- OBJECT DESCRIPTOR --------------------------------------------------
class ObjectDescriptor:
    """
    Generates descriptions and actions for a list of items (e.g. axe, spell, etc)
    """
    def __init__(self, client: BaseClient) -> None:
        global OBJECT_DESC
        self.client = client
        self.obj_expected_flds = list(OBJECT_DESC.keys())
        self.stats = {}


    def __gen_rollback(self, obj: str) -> Dict[str, str]:
        rollback = {}
        rollback['name'] = obj.title()
        for fld in self.obj_expected_flds:
            rollback[fld] = ''
        return rollback


    def describe(self, obj: str, **kwargs) -> Dict[str, str]:
        msgs = gen_obj_est_msgs(obj)
        response = self.client.chat(msgs, **kwargs)
        self.stats[obj] = response['stats']

        # parse the response
        response_dict = {}
        try:
            ans = parse2structure(response['message'], self.obj_expected_flds)
            response_dict = ans[list(ans.keys())[0]]
            response_dict['name'] = response_dict['name'].title()
        except Exception as e:
            logger.warning(f"Could not parse response for \"{obj}\" with \"{e}\" error! Using the rollback!")
            response_dict = self.__gen_rollback(obj)
        return response_dict


# ----------------------------------------------- PLAYER INPUT VALIDATOR -----------------------------------------------
class InputValidator:
    def __init__(self,
                 lore:Dict[str, Any],
                 response_model: pydantic.BaseModel,
                 llm_client: BaseClient):
        """
        Action validator class. It builds system and tass prompts dynamically depending on available input
        :param lore: Dict[str, Any] -- game lore, used to populate known location, world rules, etc.
        :param response_model: pydantic.BaseModel -- response model
        :param llm_client: BaseClient -- LLM client for particular provider
        """
        self.lore_kingdoms_towns = [f"Kingdom \"{x}\" --> Towns: {', '.join(list(lore['towns'][x].keys()))}" for x in
                          lore['towns']]

        # System prompts chunks to be combined later
        self.sys_prompt_world_base= f"""You are AI game engine that verifies player's actions.
Here are rules for the world you are playing in:
{lore['world_outline']}

Known kingdoms and towns:
{self.lore_kingdoms_towns}"""
        self.sys_prompt_task_base = """Your task:
- validate player's action (valid = True / valid = False). The action must be in agreement with the world rules and its description."""
        self.sys_prompt_instructions_base = """Your instructions:
- player is not allowed to act in contradiction to the world rules and world description;
- player can't use items not in their inventory;
- player can't gain items or abilities without a reason;
- player can't act in a wrong location, if the current location is not clear, skip this validation;"""

        self.response_model = response_model
        self.llm = llm_client
        # stats for a recent call
        self.stats = {}
        # the last submitted messages
        self.last_submitted_messages = {}

    def compile_messages(self,
                           action: str,
                           context: str,
                           inventory: List[str] = None,
                           current_location: List[str] = None,
                           other_known_locations: List[Any] = None,
                           phys_ment_state: Dict[str, Any] = None,
                           enforce_json_output:bool=False) -> List[Dict[str, str]]:

        # Build the actual system prompt dynamically based on inputs
        logger.debug("Building system prompt")
        sys_prt = copy.copy(self.sys_prompt_world_base)

        if other_known_locations is not None:
            logger.debug("Other known location added")
            sys_prt += f"\nOther known locations to consider: {other_known_locations}"
        sys_prt += f"\n\n{self.sys_prompt_task_base}"
        sys_prt += f"\n\n{self.sys_prompt_instructions_base}"
        if phys_ment_state is not None:
            logger.debug("Phys/mental instructions state added")
            sys_prt += f"\n- player can't act in contradiction to their physical or mental state. E.g., a player can't lift heavy items while lacking a limb"

        if enforce_json_output:
            logger.debug("Enforcing pydantic schema in the system prompt")
            sys_prt += f"\n\nStructure your output following this Pydantic schema:\n{self.response_model.model_json_schema()}"
        else:
            sys_prt += "\n\nYour response is a valid JSON."

        # build the task message
        logger.debug("Building task prompt")
        val_task = f"""Verify and classify following player's action:
{action}
# ---------- in this context/history ----------
{context}"""

        if inventory is not None or phys_ment_state is not None or current_location is not None:
            logger.debug("Adding additional information to the task")
            val_task += "\n# ---------- Use this additional information about the player ----------"
        if inventory is not None:
            logger.debug("Added inventory")
            val_task += f"\nPlayer's inventory: {inventory}"
        if current_location is not None:
            logger.debug("Added current location")
            val_task += f"\nPlayer's current location: {current_location}"
        if phys_ment_state is not None:
            s = ""
            if "physical" in phys_ment_state:
                logger.debug("Added physical state")
                s += f"\nPlayer's physical state: {phys_ment_state['physical']}"
            if 'mental' in phys_ment_state:
                logger.debug("Added mental state")
                s += f"\nPlayer's mental state: {phys_ment_state['mental']}"
            val_task += s

        return [
            {'role': 'system', 'content': sys_prt},
            {'role': 'user', 'content': val_task}]


    def validate_action(self,
                        action: str,
                        context: str,
                        inventory: List[str] = None,
                        current_location: List[Any] = None,
                        other_known_locations: List[str] = None,
                        phys_ment_state: Dict[str, Any] = None,
                        **llm_kwargs) -> pydantic.BaseModel:
        """
        Validates player's action
        :param action: str -- action to validate
        :param context: str -- any additional context, such as previous responses, etc.
        :param inventory: str -- Optional, list of inventory items
        :param current_location: List[Any] -- current location; could be {"kingdom": ..., "town": ...} or ["Kingdom: ...", ""Town: ...]
        :param other_known_locations: List[str] -- Optional, list of any other known locations
        :param phys_ment_state: Dict[str, Any] -- Optional, physical and mental state of the player
        :param llm_kwargs: Any -- LLM kwargs
        :return: pydantic.BaseModel -- Pydantic response model
        """
        logger.debug("Validating player action")
        __msgs = self.compile_messages(action, context, inventory, current_location, other_known_locations, phys_ment_state)
        self.last_submitted_messages = __msgs
        raw_response = self.llm.struct_output(__msgs, self.response_model, **llm_kwargs)
        try:
            self.stats = raw_response['stats']
        except Exception as e:
            logger.debug(f"Could not get call stats with \"{e}\"")
        return raw_response['message']


# TODO: finalize it:
# ------------------------------------------------- INVENTORY UPDATER --------------------------------------------------
class InventoryChange:
    def __init__(self, llm_client):
        global INVENTORY_CHANGE_SYS_PROMPT
        self.system_prompt = INVENTORY_CHANGE_SYS_PROMPT
        self.client = llm_client
        self.__money_synonyms = ['gold', 'money', 'silver', 'crown']

    def inventory_change_ai(self,
                            human_msg: str,
                            ai_response: str,
                            **client_kw) -> Dict[str, Any]:

        global Inventory

        assessor_task = f"""Recent player action: \"{human_msg}\"
Recent game response: \"{ai_response}\"
Inventory Updates:"""

        inv_msg = [{'role': 'system', 'content': INVENTORY_CHANGE_SYS_PROMPT},
                   {'role': 'user', 'content': assessor_task}]

        inv_ans = self.client.struct_output(inv_msg, Inventory, **client_kw)
        return inv_ans['message'].model_dump()['itemUpdates']


    def validate_ai_updates(self,
                            updates: Dict[str, Any],
                            inventory: List[str]) -> Dict[str, Any]:
        """
        Validates AI response. LLMs may identify 
        :param updates:
        :param inventory:
        :return:
        """
        items2pop = []
        for idx, item in enumerate(updates):
            if item['item'] not in inventory:
                items2pop.append(idx)

        # if no items left in the inventory, then we drop any money possible added
        # as we do not let players gain money for nothing
        for idx, item in enumerate(updates):
            for s in self.__money_synonyms :
                if s == item['item'].lower():
                    # if 'gold' == item['item'].lower():
                    if (len(updates) - len(items2pop)) == 1:
                        items2pop.append(idx)
                continue

        result = []
        for idx, item in enumerate(updates):
            if idx not in items2pop:
                result.append(item)

        return result

    def detect_inventory_change(self, human_msg: str,
                                ai_response: str,
                                inventory: List[str],
                                **client_kw) -> Dict[str, Any]:

        ai_updates = self.inventory_change_ai(human_msg, ai_response, **client_kw)
        return self.validate_ai_updates(ai_updates, inventory)