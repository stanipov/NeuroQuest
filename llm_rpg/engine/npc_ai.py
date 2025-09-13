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
from llm_rpg.templates.tool import BaseTool
from llm_rpg.engine.tools import ObjectDescriptor

# ------------------------------ Helpers ------------------------------
def get_other_characters(lore:Dict[str, Any], your_name: str):
    """Extracts names of other NPC characters"""
    npc_names = list(lore['npc'].keys())
    return [x for x in npc_names if x!=your_name]

# ------------------------------ NPC AI class ------------------------------
class NPC(BaseTool):
    def __init__(self,
                 llm_client,
                 sql_memory,
                 game_lore: Dict[str, Any],
                 npc_name: str,
                 num_turns: int = 10):

        super().__init__(llm_client, NPCResponseModel)

        self.sql_memory = sql_memory
        self.inv_items_descriptor = ObjectDescriptor(llm_client)
        self.name = npc_name
        self.npc_rules = _copy(game_lore['npc_rules'][npc_name])
        self.npc_card = _copy(game_lore['npc'][npc_name])
        self.world_rules = _copy(game_lore['world_outline'])
        self.world_description = _copy(game_lore['world']['description'])
        self.world_name = _copy(game_lore['world']['name'])
        self.N_turns_back = num_turns
        self.other_npc_names = get_other_characters(game_lore, npc_name)
        self.human_player_name = game_lore['human_player']['name']
        self.inventory_items = self.sql_memory.list_inventory_items(npc_name)
        self.__upd_inv_items_lut()

        # hooks for generation of additional context via, e.g. RAG or knowledge graphs, etc.
        # expected entry point: TODO
        self.extra_context_hooks = {}

        # Defaults and statics
        self.base_system_prompt = self.__base_sys_prt()
        self.__fmt_header_lines = f"{'-' * 5}"
        self.__inv_desc_T = 0.25

        # Recent response
        self.recent_response = None


    def __is_human_player(self, name) -> bool:
        """Is this a human player name?"""
        candidates = [self.human_player_name.lower(), 'human', 'player']
        return name.lower() in candidates


    def __list_inventory_items(self):
        """Updates inventory listing"""
        self.inventory_items = self.sql_memory.list_inventory_items(self.name)


    def __upd_inv_items_lut(self):
        self.inventory_items_desc = {}
        for x in self.sql_memory.list_all_rows(self.sql_memory.items_tbl_name):
            self.inventory_items_desc[x['name']] = x


    def __base_sys_prt(self):
        """Generates a base and constant system prompt"""
        return f"""You are {self.name}. These are your brief biography details:
{self.npc_card}

You act following her rules:
{self.npc_rules}

You live in a world that follows these behavioral rules:
{self.world_rules}

Here's your world:
- name: {self.world_name}
- description: {self.world_description}

You will be provided with actions of other characters.

Your task: respond to these as {self.name}
Instructions:
- actions MUST agree with the world rules
- you help the human player
- you behave strictly in accordance to your behavioral rules
- can use only items in her inventory
- if you decide to change your inventory, provide inventory changes with items and counts"""


    def compile_messages(self, enforce_struct_output:bool=False):
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
        TASK = f"""What will you do?

    Situation: {current_turn['ai_response']}

    Human actions: {current_turn['human_response']}"""
        for npc_char in self.other_npc_names:
            if current_turn[npc_char]:
                TASK += f"\n{npc_char}: {current_turn[npc_char]}"
        if  conv_context != "":
            TASK += f"""{self.__fmt_header_lines} Your previous conversation: {self.__fmt_header_lines}
    {conv_context}"""

        additional_context = self.get_extra_context()
        if additional_context != "":
            TASK += f"\n{self.__fmt_header_lines} Use this additional: {self.__fmt_header_lines}\n{additional_context}"
        return extra_system_prompt + [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': TASK}
        ]


    def get_extra_context(self, *args, **kwargs) -> str:
        """Placeholder for additional context as specified in the extra_context_hooks"""
        return ""


    def extract_sql_memory(self) -> List[Dict[str,str]] :
        return self.sql_memory.get_last_n_rows(self.sql_memory.history_tbl_name, self.N_turns_back)


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
            turn_num = turn['turn']
            response = f"{self.__fmt_header_lines} TURN: {turn_num} {self.__fmt_header_lines}\n"
            context.append(response + self.format_turn(turn))

        return '\n'.join(context)


    def run(self, enforce_struct_output:bool=False, **kwargs):
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
        turn_msgs = [
            {"role": self.name, "message": response.action}
        ]
        self.sql_memory.update_turn(turn_msgs)


    def update_inventory(self, response):
        logger.debug("Updating inventory of any")
        # List all items in the items table to see if we need to describe any new item
        all_inv_items = set()
        for row in self.sql_memory.list_all_rows(self.sql_memory.items_tbl_name):
            all_inv_items.add(row['name'])

        new_inventory_items = {}
        for item in response.inventory_update.itemUpdates:
            if item.item not in all_inv_items:
                logger.debug(f"New item not in LUT: {item.item}")
                new_inventory_items[item.item] = {
                    "description": {},
                    "owner": item.subject,
                    "count": item.change_amount
                }

        if len(new_inventory_items) != 0:
            logger.info(f"Found new items to describe: {new_inventory_items.keys()}")
            for item in new_inventory_items:
                logger.info(f"Describing new item: \"{item}\"")
                new_inventory_items[item]['description'] = self.inv_items_descriptor(item, temperature=self.__inv_desc_T)
                self.inventory_items_desc.update( {item.item: new_inventory_items[item]['description']} )

        # add the new items
        for item in new_inventory_items:
            owner = new_inventory_items[item]['owner']
            payload = {
                item: new_inventory_items[item]['count']
            }
            payload_lut = {
                item: new_inventory_items[item]['description']
            }
            self.sql_memory.add_inventory_items(owner, payload, payload_lut)

        # update all items now
        for item in response.inventory_update.itemUpdates:
            logger.debug(f"Processing item: {item.item}")
            # if the item is not in the current inventory of the NPC:
            if item not in self.inventory_items:
                payload = {
                    item.item: item.change_amount,
                }
                payload_lut = {
                    item.item: self.inventory_items_desc[item.item]
                }
                logger.debug(f"Adding {item.item}")
                logger.debug(f"Payload: {payload}")
                logger.debug(f"Character: {item.subject}")
                self.sql_memory.add_inventory_items(item.subject, payload, payload_lut)
                self.inventory_items.append(item.item)

            # If item.item is in new_inventory_items, then it was a brand-new item, and we have updated it above
            # Also, we do not want double update
            if item.item not in new_inventory_items and item.item not in self.inventory_items:
                payload = {
                    "item": item.item,
                    "character": item.subject,
                    "count_change": item.change_amount
                }
                logger.debug(f"Updating with payload: {payload}")
                self.sql_memory.update_inventory_item(payload)

            # remove item from inventory of the player if applicable
            logger.debug(f"Checking if {item.item} count needs to be decreased for someone else")
            character2subtract_item = ""
            if self.__is_human_player(item.source):
                logger.debug(f"Item belonged to the human player")
                character2subtract_item = "human"
            elif item.source in self.other_npc_names:
                logger.debug(f"Item belonged to {item.source}")
                character2subtract_item = item.source
            logger.debug(f"Shall decrease for: \"{character2subtract_item}\"")
            if character2subtract_item != "":
                logger.debug(f"Decreasing count of {item.item} by {item.change_amount}")
                payload = {
                    "item": item.item,
                    "character": character2subtract_item,
                    "count_change": -item.change_amount
                }
                logger.debug(f"Payload: {payload}")
                self.sql_memory.update_inventory_item(payload)

    def update_state(self, response):
        payload = {
            "player": self.name,
            "alive": response.state.alive,
            "physical": ', '.join([x.state for x in response.state.physical]),
            "mental": ', '.join([x.state for x in response.state.mental])
        }
        self.sql_memory.update_row(self.sql_memory.players_state_tbl_name, payload)


    def update_location(self, location):
        pass