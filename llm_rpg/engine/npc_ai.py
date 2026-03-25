"""
NPC behavior

"""

import logging

logger = logging.getLogger(__name__)

import json
from copy import copy as _copy
from typing import List, Dict, Any
from pydantic import BaseModel
from llm_rpg.prompts.response_models import NPCResponseModel
from llm_rpg.prompts.npc import gen_npc_base_system_prompt
from llm_rpg.templates.tool import BaseTool


# ------------------------------ Helpers ------------------------------
def get_other_characters(lore: Dict[str, Any], your_name: str):
    """Extracts names of other NPC characters"""
    npc_names = list(lore["npc"].keys())
    return [x for x in npc_names if x != your_name]


# ------------------------------ NPC AI class ------------------------------
class NPC(BaseTool):
    def __init__(
        self,
        llm_client,
        sql_memory,
        game_lore: Dict[str, Any],
        npc_name: str,
        config: Dict[str, Any] = None,
    ):
        config = config or {}
        num_turns = config["npc_chat_history"]
        super().__init__(llm_client, NPCResponseModel)

        self.sql_memory = sql_memory
        self.name = npc_name
        self.npc_rules = _copy(game_lore["npc_rules"][npc_name])
        self.npc_card = _copy(game_lore["npc"][npc_name])
        self.world_rules = _copy(game_lore["world_outline"])
        self.world_description = _copy(game_lore["world"]["description"])
        self.world_name = _copy(game_lore["world"]["name"])
        self.N_turns_back = num_turns
        self.other_npc_names = get_other_characters(game_lore, npc_name)
        self.human_player_name = game_lore["human_player"]["name"]
        self.inventory_items = self.sql_memory.list_inventory_items(npc_name)
        self.__upd_inv_items_lut()

        # hooks for generation of additional context via, e.g. RAG or knowledge graphs, etc.
        # expected entry point: TODO
        self.extra_context_hooks = None

        # Defaults and statics
        self.base_system_prompt = self.__base_sys_prt()
        self.__fmt_header_lines = f"{'-' * 5}"

        # Recent response
        self.recent_response = None

    def __is_human_player(self, name) -> bool:
        """Is this a human player name?"""
        candidates = [self.human_player_name.lower(), "human", "player"]
        return name.lower() in candidates

    def __list_inventory_items(self):
        """Updates inventory listing"""
        self.inventory_items = self.sql_memory.list_inventory_items(self.name)

    def __upd_inv_items_lut(self):
        """Updates inventory items lookup - just item names, no descriptions"""
        self.inventory_items_desc = {}

    def __base_sys_prt(self):
        """Generates a base and constant system prompt"""
        return gen_npc_base_system_prompt(
            npc_name=self.name,
            npc_card=self.npc_card,
            npc_rules=self.npc_rules,
            world_name=self.world_name,
            world_description=self.world_description,
            world_rules=self.world_rules,
        )

    def compile_messages(self, enforce_struct_output: bool = False):
        """Generates the messages to submit to the LLM"""
        self.__list_inventory_items()
        conversation_hist = self.extract_sql_memory()

        extra_system_prompt = []
        if enforce_struct_output:
            extra_system_prompt = self.add_struct_sys_prompt()

        system_prompt = self.base_system_prompt
        system_prompt += f"\nYour inventory items: {self.inventory_items}"

        conv_context = ""
        if len(conversation_hist) > 1:
            conv_context = self.format_memory_extract(conversation_hist[:-1])

        current_turn = conversation_hist[0]
        npc_goal = self.npc_card.get("goal", "Unknown")

        TASK = f"""Current Situation (Turn {current_turn["turn"]}):

WORLD STATE: {current_turn["ai_response"]}

HUMAN PLAYER'S ACTION: {current_turn["human_response"]}"""

        for npc_char in self.other_npc_names:
            if current_turn[npc_char]:
                TASK += f"\n{npc_char}: {current_turn[npc_char]}"

        TASK += f"""

YOUR CONTEXT:
- Your goal: {npc_goal}
- Your inventory: {self.inventory_items}

CONVERSATION SIGNALS:
- Player's message: {current_turn["human_response"]}
- Check if this is a question: Look for "why", "how", "what", "who", "when", "where" or direct address (name)

DECISION REQUIRED:
Interpret the player's input carefully:
1. If the player asks a question (why/how/what/who/when/where) or addresses you directly, ANSWER first
2. If the player describes an action, execute the action
3. If both questioning and action, answer first then act

Respond in character, using 3-5 sentences for complex responses."""

        if conv_context != "":
            TASK += f"""{self.__fmt_header_lines} Recent History:{self.__fmt_header_lines}
{conv_context}"""

        additional_context = self.get_extra_context()
        if additional_context != "":
            TASK += f"\n{self.__fmt_header_lines} Use this additional: {self.__fmt_header_lines}\n{additional_context}"
        return extra_system_prompt + [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": TASK},
        ]

    def get_extra_context(self, *args, **kwargs) -> str:
        """Placeholder for additional context as specified in the extra_context_hooks"""
        return ""

    def extract_sql_memory(self) -> List[Dict[str, str]]:
        return self.sql_memory.get_last_n_rows(
            self.sql_memory.history_tbl_name, self.N_turns_back
        )

    def format_turn(self, turn: Dict[str, str]) -> str:
        """Formats a turn into a string to be fed to the LLM client"""
        response = f"Situation: {turn['ai_response']}\nHuman: {turn['human_response']}\nYou: {turn[self.name]}"
        for o_character in self.other_npc_names:
            response += f"\n{o_character}: {turn[o_character]}"
        return response

    def format_memory_extract(self, history: List[Dict[str, str]]) -> str:
        """Formats historic turns into a string to feed into the LLM client"""
        context = []
        for turn in history:
            turn_num = turn["turn"]
            response = f"{self.__fmt_header_lines} TURN: {turn_num} {self.__fmt_header_lines}\n"
            context.append(response + self.format_turn(turn))

        return "\n".join(context)

    def run(self, enforce_struct_output: bool = False, **kwargs):
        llm_messages = self.compile_messages(enforce_struct_output)
        response = self.submit_messages(llm_messages, **kwargs)
        self.recent_response = response

        try:
            self.update_turn(response)
        except Exception as e:
            logger.error(f"Update turn: {e}")

        try:
            self.update_state(response)
        except Exception as e:
            logger.error(f"Update state: {e}")

        try:
            self.update_inventory(response)
            self.__list_inventory_items()
            self.__upd_inv_items_lut()
        except Exception as e:
            logger.error(f"Update inventory: {e}")

        try:
            self.update_location(response)
        except Exception as e:
            logger.error(f"Update location: {e}")

        return response

    def update_turn(self, response):
        turn_msgs = [{"role": self.name, "message": response.action}]
        self.sql_memory.update_turn(turn_msgs)

    def update_inventory(self, response):
        """Updates inventory based on LLM response - item names only, no descriptions"""
        logger.debug("Updating inventory")

        # Update all items from the response
        for item in response.inventory_update.itemUpdates:
            logger.debug(f"Processing item: {item.item}")

            # Add new item to inventory if not present
            if item.item not in self.inventory_items:
                payload = {item.item: item.change_amount}
                self.sql_memory.add_inventory_items(item.subject, payload, {})
                self.inventory_items.append(item.item)

            # Update existing item count
            elif item.item not in self.inventory_items:
                payload = {
                    "item": item.item,
                    "character": item.subject,
                    "count_change": item.change_amount,
                }
                logger.debug(f"Updating with payload: {payload}")
                self.sql_memory.update_inventory_item(payload)

            # Remove item from owner's inventory if applicable (transfer)
            character2subtract_item = ""
            if self.__is_human_player(item.source):
                character2subtract_item = "human"
            elif item.source in self.other_npc_names:
                character2subtract_item = item.source

            if character2subtract_item != "":
                payload = {
                    "item": item.item,
                    "character": character2subtract_item,
                    "count_change": -item.change_amount,
                }
                self.sql_memory.update_inventory_item(payload)

    def update_state(self, response):
        payload = {
            "player": self.name,
            "alive": response.state.alive,
            "physical": ", ".join([x.state for x in response.state.physical]),
            "mental": ", ".join([x.state for x in response.state.mental]),
        }
        self.sql_memory.update_row(self.sql_memory.players_state_tbl_name, payload)

    def update_location(self, location):
        pass
