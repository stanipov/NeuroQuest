"""
NPC behavior

"""

import logging

logger = logging.getLogger(__name__)

import json
from copy import copy as _copy
from typing import List, Dict, Any
from pydantic import BaseModel
from llm_rpg.prompts.response_models import NPCResponseModel, NPCGatewayResponse
from llm_rpg.prompts.npc import gen_npc_base_system_prompt, gen_npc_gateway_prompt, gen_npc_system_prompt
from llm_rpg.templates.tool import BaseTool
from llm_rpg.templates.base_client import BaseClient
from llm_rpg.engine.memory import GameMemory
from llm_rpg.utils.prompt_utils import generate_with_retry


# ------------------------------ Helpers ------------------------------
def get_other_characters(lore: Dict[str, Any], your_name: str):
    """Extracts names of other NPC characters"""
    npc_names = list(lore["npc"].keys())
    return [x for x in npc_names if x != your_name]


# ------------------------------ NPC AI class ------------------------------
class NPCAgent(BaseTool):
    def __init__(self,
                 name: str,
                 llm_client: BaseClient,
                 lore: Dict[str, Any],
                 config: Dict[str, Any],
                 game_memory: GameMemory):

        super().__init__(llm_client, NPCResponseModel)

        self.my_name = name
        self.my_card = _copy(lore["npc"][self.my_name])
        for x in ("money", "inventory"):
            _ = self.my_card.pop(x)

        self.llm_client = llm_client
        self.lore = _copy(lore)
        self.config = config
        self.memory = game_memory

        self.human_player_name = self.lore["human_player"]["name"]
        self.other_npc_names = get_other_characters(self.lore, self.my_name)

        # Build kingdom/town reference string
        self.known_locations = [f'Kingdom "{x}" --> Towns: {", ".join(list(lore["towns"][x].keys()))}'\
                                    for x in lore.get("towns", {})]


    def _format_history(self, history: list[dict]) -> str:
        """
        Format recent history for dynamic context.
        
        Args:
            history: List of recent game turns from memory
            
        Returns:
            Formatted history string for prompt context
        """
        if not history:
            return "No recent history available."
        
        formatted = []
        for turn in history:
            turn_num = turn.get("turn", "?")
            user_action = turn.get("user_input", "N/A")
            game_state = turn.get("game_action", turn.get("displayed_action", "N/A"))
            
            # Include other NPC actions if present
            npc_actions = []
            for npc_name in self.other_npc_names:
                sanitized = self.memory._inverse_npc_mapping.get(npc_name, npc_name)
                if sanitized in turn and turn[sanitized]:
                    npc_actions.append(f"{npc_name}: {turn[sanitized]}")
            
            entry = f"Turn {turn_num}:\n  Player: {user_action}\n  State: {game_state}"
            if npc_actions:
                entry += f"\n  {' | '.join(npc_actions)}"
            formatted.append(entry)
        
        return "\n".join(formatted)


    def _input_gateway(self, user_input: str) -> Dict[str, Any]:
        """
        Decide if the NPC should respond to user input.

        Args:
            user_input: Current user input

        Returns:
            Dict with 'should_act' (bool) and 'reason' (str)
        """
        # Fetch recent global history from memory
        recent_history = self.memory.get_last_n_turns(n=self.config.get("gateway_history_depth"))
        
        # Format history for context
        history_context = self._format_history(recent_history)
        
     # Build system prompt (static, character-specific)
        system_prompt = gen_npc_gateway_prompt(npc_name=self.my_name,
                                                npc_card=self.my_card,
                                                other_npc_names=self.other_npc_names)
        
        # Build user prompt (dynamic, per-call)
        user_prompt = f"""CURRENT INPUT: "{user_input}"

RECENT CONTEXT:
{history_context}

Apply the checklist above. Is this input directed at you, or not?"""

        fallback = NPCGatewayResponse(should_act=False, reason="Gateway failed")
        result = generate_with_retry(client=self.llm_client,
                                     messages=[{"role": "system", "content": system_prompt},
                                               {"role": "user", "content": user_prompt}],
                                     response_model=NPCGatewayResponse,
                                     max_retries=self.config["max_generation_retries"],
                                     fallback_value=fallback,
                                     component_name=f"NPC Gateway: {self.my_name}",
                                     temperature_cooldown_step=self.config["temperature_cooldown_step"],
                                     temperature_min=self.config["temperature_min"],
                                     temperature=self.config["gateway_temperature"])
        return result["message"]


    def _build_system_prompt(self, *args) -> str:
        state = self.memory.get_latest_state(self.my_name) or {}
        return gen_npc_system_prompt(
            npc_name=self.my_name,
            npc_card=self.my_card,
            npc_rules=self.lore.get("npc_rules", {}).get(self.my_name, {}),
            world_name=self.lore["world"]["name"],
            world_description=self.lore["world"]["description"],
            world_outline=self.lore.get("world_outline", {}),
            known_locations=self.known_locations,
            human_player_name=self.human_player_name,
            physical_state=state.get("physical", ""),
            mental_state=state.get("mental", ""),
        )

    def compile_messages(self,
                         user_input: str,
                         react_reason: str="") -> List[Dict[str, str]]:
        sys_prt = self._build_system_prompt()
        history = self.memory.get_last_n_turns(self.config.get("npc_chat_history"))

        # Build history context (most recent first)
        history_lines = []
        for turn in history:
            turn_num = turn.get("turn", "?")
            player_action = turn.get("user_input", "N/A") or "N/A"
            game_response = turn.get("displayed_action", turn.get("game_action", "")) or ""

            entry = f"Turn {turn_num}:\n  Player: {player_action}"
            if game_response:
                entry += f"\n  Game: {game_response}"

            # Other NPC actions
            for npc_name in self.other_npc_names:
                sanitized = self.memory._inverse_npc_mapping.get(npc_name, npc_name)
                npc_action = turn.get(sanitized)
                if npc_action:
                    entry += f"\n  {npc_name}: {npc_action}"

            # This NPC's own past action
            my_sanitized = self.memory._inverse_npc_mapping.get(self.my_name, self.my_name)
            my_action = turn.get(my_sanitized)
            if my_action:
                entry += f"\n  You: {my_action}"

            history_lines.append(entry)

        history_context = "\n".join(history_lines) if history_lines else "No recent history."

        user_prompt = f"""You are {self.my_name}. Stay in character at all times.

RECENT HISTORY:
{history_context}

CURRENT INPUT: "{user_input}"
Reason to act: {react_reason}

As {self.my_name}, decide what to do. Respond with your action, and optionally update your state and location.

POST-ACTION REFLECTION:
After deciding your action, consider how the events and your actions have shaped your mental state.
Update your mental state to reflect this."""

        return [
            {"role": "system", "content": sys_prt},
            {"role": "user", "content": user_prompt},
        ]


    def run(self, user_input: str, **kwargs) -> Dict[str, str]:

        # gateway definition
        gateway_result = self._input_gateway(user_input)
        should_act = gateway_result["should_act"]
        should_act_reason = gateway_result["reason"]
        response = {}

        if should_act:
            messages = self.compile_messages(user_input, should_act_reason)
            response = generate_with_retry(client=self.llm_client,
                                           messages=messages,
                                           response_model=NPCResponseModel,
                                           max_retries=self.config["max_generation_retries"],
                                           fallback_value=None,
                                           component_name=f"NPC response: {self.my_name}",
                                           temperature_cooldown_step=self.config["temperature_cooldown_step"],
                                           temperature_min=self.config["temperature_min"],
                                           temperature=self.config["temperature"],
                                           **kwargs)
            response["reason"] = should_act_reason
            # ToDo: based on the response, we shall update mental state of the NPC

        return response


# ------------------------------ DEPRECATED: NPC AI class ------------------------------
class NPC_old(BaseTool):
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
