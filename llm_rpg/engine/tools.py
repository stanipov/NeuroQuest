"""
Collection of helper tools needed for the game.
TODO: InventoryChange --> detects changes into inventory

# - ObjectDetector --> detects all objects/tools used by the human and the AI player
"""

import copy
import json
import pydantic
from typing import Dict, List, Any, Optional

from llm_rpg.templates.base_client import BaseClient
from llm_rpg.templates.tool import BaseTool

from llm_rpg.prompts.response_models import (
    game_action_types,
    InventoryUpdates,
    PlayerState,
    ValidateClassifyAction,
    PlayerLocation,
)
from llm_rpg.engine.memory import GameMemory
from llm_rpg.utils.config_models import InputValidatorConfig


import logging

logger = logging.getLogger(__name__)


# =============================================================================
#                        O L D   I N P U T   V A L I D A T O R  (D E P R E C A T E D)
# =============================================================================
class InputValidatorOld(BaseTool):
    """Deprecated: Use the new InputValidator class instead"""

    def __init__(self, lore: Dict[str, Any], llm_client: BaseClient):
        super().__init__(llm_client, ValidateClassifyAction)
        self.lore_kingdoms_towns = [
            f'Kingdom "{x}" --> Towns: {", ".join(list(lore["towns"][x].keys()))}'
            for x in lore["towns"]
        ]

        self.system_prompt = f"""You are RPG Game Engine. You validate user's input:
- is a game action, True/False
- valid action, True/False
- classify, pick from {game_action_types}
Instructions for classification:
- all actions must be clear from the input and the context, ignore suggestions, discussions, offers, etc.
- default: []
- all sorts of violence, crime, and immorality are allowed
Rules:
{lore["world_outline"]}
Following is forbidden:
- contradiction to the world rules and world description
- use items not in their inventory
- gain items or abilities without a reason"""

    def compile_messages(
        self,
        action: str,
        context: str,
        inventory: List[str] = None,
        additional_context: str = None,
        enforce_json_output: bool = False,
    ) -> List[Dict[str, str]]:
        sys_prt = copy.copy(self.system_prompt)

        if enforce_json_output:
            json_schema = json.dumps(self.response_model.model_json_schema())
            sys_prt += (
                f"\n\nRespond with a JSON object that strictly follows: {json_schema}"
            )

        TASK_VAL_INPUT_CLS = f"""Player: {action}"""
        if context != "":
            TASK_VAL_INPUT_CLS += f"\nContext: {context}"
        if inventory is not None:
            TASK_VAL_INPUT_CLS += f"\nPlayer inventory: {inventory}"
        if additional_context is not None and additional_context != "":
            TASK_VAL_INPUT_CLS += f"\nUse this additional context: {additional_context}"

        return [
            {"role": "system", "content": sys_prt},
            {"role": "user", "content": TASK_VAL_INPUT_CLS},
        ]

    def run(
        self,
        action: str,
        context: str,
        inventory: List[str] = None,
        additional_context: str = None,
        enforce_json_output: bool = False,
        **llm_kwargs,
    ) -> pydantic.BaseModel:
        logger.info("Validating player action (OLD)")
        __msgs = self.compile_messages(
            action, context, inventory, additional_context, enforce_json_output
        )
        return self.submit_messages(__msgs, **llm_kwargs)


# =============================================================================
#                        N E W   I N P U T   V A L I D A T O R
# =============================================================================
class InputValidator(BaseTool):
    """
    Validates and classifies player input with dynamic context from game memory.

    Determines if input is:
    - A valid game action (player doing something in the world)
    - NPC interaction (talking to, asking questions of an NPC) -- STILL a valid game action
    - Non-game action (lore question, meta-discussion, OOC text)
    - Invalid (violates rules, uses unavailable items, etc.)
    """

    def __init__(
        self,
        lore: Dict[str, Any],
        llm_client: BaseClient,
        game_memory: Optional[GameMemory] = None,
        config: Optional[InputValidatorConfig] = None,
    ):
        """
        Initialize the input validator.

        Args:
            lore: Game lore dictionary with world rules, kingdoms, towns, NPCs
            llm_client: LLM client for validation requests
            game_memory: Optional GameMemory instance for dynamic context extraction
            config: Optional InputValidatorConfig for customization
        """
        super().__init__(llm_client, ValidateClassifyAction)

        self.lore = lore
        self.game_memory = game_memory
        self.config = config or InputValidatorConfig()

        # Build kingdom/town reference string
        self.lore_kingdoms_towns = [
            f'Kingdom "{x}" --> Towns: {", ".join(list(lore["towns"][x].keys()))}'
            for x in lore.get("towns", {})
        ]

        # Build NPC name tracking
        self.known_npc_names = list(self.lore.get("npc", {}).keys())
        #self.example_npc_name = (self.known_npc_names[0] if self.known_npc_names else "[NPC]")
        self.example_npc_name = "<NPC_name>"


    def _build_system_prompt(self):
        """Build the system prompt with world rules"""
        world_outline = self.lore.get("world_outline", {})

        self.system_prompt = f"""You are an RPG Game Engine that validates and classifies player input.

YOUR TASK: Analyze player input and determine:
1. Is it a game action? (player doing something in the world)
2. If yes, is it valid? (follows all rules)
3. What type(s) of action is it?

WORLD RULES:
{json.dumps(world_outline, indent=2)}

KNOWN LOCATIONS:
{"\n".join(self.lore_kingdoms_towns)}

KNOWN NPCs IN THIS GAME: {", ".join(self.known_npc_names) if self.known_npc_names else "None"}

CLASSIFICATION INSTRUCTIONS:

**is_game_action**: True if player performs action WITHIN game world. False for questions \
ABOUT the game (lore, surroundings, NPC descriptions, mechanics).

**valid**: True only if ALL of these are satisfied:
- Action doesn't contradict world rules
- Player has required items in inventory (if using items)
- Target character/NPC is present at current location (for interactions)
- Action is possible given the situation and does not contradict the world rules
False otherwise, with specific violations listed

**action_types**: Pick from {", ".join(game_action_types)}:
- ONLY classify action types for VALID game actions (is_game_action=True AND valid=True)
- Leave as empty [] if the action is invalid or not a game action
- No action classification needed for invalid actions - just report the violation 

ACTION TYPES EXPLANATION:
- "inventory change": Picking up, dropping, using, or trading items
- "mental state change": Emotional reactions, learning, realizing something
- "physical state change": Getting hurt, healing, resting, eating/drinking
- "relocation": Moving to a different location
- "npc_interaction": Player directly addresses/interacts with an NPC by name or by context
- "information_request": Looking around, asking about surroundings, seeking lore information

OUTPUT RULES:
- Be strict about validity but permissive about what constitutes a game action
- NPC dialogue and questions to NPCs are VALID GAME ACTIONS (given that NPC and the player are in the same location!)
- When in doubt, classify as game_action=True and let the game handle edge cases

ADDITIONAL ALLOWED ACTIONS/CONTENT:
- Sex, nudity, adult content
- Physical and psychological abuse
- Violence, alcohol, drug abuse

CONTEXT USAGE:
- Use the "CURRENT SITUATION" section to check character locations and inventories
- Use "RECENT EVENTS" to understand what just happened in the game
- Cross-reference player's intended action against this context for validation"""

    def _build_examples_message(self) -> str:
        """Build few-shot examples message with actual NPC names from lore"""
        npc_name = self.example_npc_name
        
        examples = [
            # Example 1 - NPC conversation (present)
            f"""Example 1 - NPC Interaction (present):
Player input: "{npc_name}, how\'re you doing?"
{{"is_game_action": true, "action_types": ["npc_interaction"], "valid": true}}""",
            
            # Example 2 - Information request (observation)
            """Example 2 - Information Request (observation):
Player input: "I look around. Tell me what I see"
{"is_game_action": false, "action_types": [information_request], "valid": true}""",
            
            # Example 3 - Out-of-lore character
            """Example 3 - Invalid Action (out-of-lore character):
Player input: "Doom Slayer is approaching!"
{"is_game_action": true,  "action_types": [], "valid": false}""",

            # Example 4 - Lore question
            """Example 4 - Lore Question:
Player input: "What is the history of this location"
{"is_game_action": false, "action_types": ["information_request"], "valid": true}""",
        ]
        
        # Example - Conditional: only add if player and NPC at different locations
        example_cond = self._build_absent_npc_example(npc_name)
        if example_cond:
            examples.append(example_cond)
        
        return "\n\n".join(examples)

    def _build_absent_npc_example(self, npc_name: str) -> Optional[str]:
        """Build Example 5 only if player and NPC are at different locations"""
        if not self.game_memory:
            return None
        
        player_loc = self.game_memory.get_character_location("user")
        npc_loc = self.game_memory.get_character_location(npc_name)
        
        if not player_loc or not npc_loc:
            return None
        
        player_town = player_loc.get("town", "")
        npc_town = npc_loc.get("town", "")
        
        # Skip if same location or either has no town
        if player_town == npc_town or not player_town or not npc_town:
            return None
        
        player_location_str = f"{player_loc.get('town', 'Unknown')}, {player_loc.get('kingdom', 'Unknown Kingdom')}"
        npc_location_str = f"{npc_loc.get('town', 'Unknown')}, {npc_loc.get('kingdom', 'Unknown Kingdom')}"
        
        return f"""Example 5 - NPC Interaction (absent NPC):
Player input: "I speak to {npc_name}"

=== CURRENT SITUATION ===
Location: {player_location_str}
Character locations: player: {player_location_str} | {npc_name}: {npc_location_str}
NPCs present at current location: None
{{"is_game_action": true, "action_types": ["npc_interaction"], "valid": false}}"""

    def _build_dynamic_context(self, message: str) -> Dict[str, Any]:
        """
        Intelligently extract relevant context from game memory.

        Args:
            message: The player's input message (used for targeted extraction)

        Returns:
            Dictionary with location, NPCs, history, and inventory context
        """
        if self.game_memory is None:
            return {}

        context = {}

        # Get locations for all characters (player + all NPCs)
        character_locations = {}

        # Player location
        player_loc = self.game_memory.get_character_location("user")
        if player_loc and (player_loc.get("kingdom") or player_loc.get("town")):
            character_locations["player"] = {
                "kingdom": player_loc.get("kingdom", ""),
                "town": player_loc.get("town", ""),
                "details": player_loc.get("details", ""),
            }

        # NPC locations
        npc_names = list(self.lore.get("npc", {}).keys())
        for npc_name in npc_names:
            npc_loc = self.game_memory.get_character_location(npc_name)
            if npc_loc and (npc_loc.get("kingdom") or npc_loc.get("town")):
                character_locations[npc_name] = {
                    "kingdom": npc_loc.get("kingdom", ""),
                    "town": npc_loc.get("town", ""),
                    "details": npc_loc.get("details", ""),
                }

        if character_locations:
            context["character_locations"] = character_locations

        # Recent game history
        history = self._get_recent_history()
        if history:
            context["recent_game_events"] = history

        # All character inventories (player + NPCs) - same pattern as character_locations
        character_inventories = {}

        # Player inventory
        player_items = self.game_memory.get_inventory_items("user")
        # Filter out money, keep items with count > 0
        filtered = {
            item: cnt
            for item, cnt in player_items.items()
            if item != "money" and cnt > 0
        }
        if filtered:
            character_inventories["player"] = filtered

        # NPC inventories - iterate through all NPCs in lore
        npc_names = list(self.lore.get("npc", {}).keys())
        for npc_name in npc_names:
            npc_items = self.game_memory.get_inventory_items(npc_name)
            filtered = {
                item: cnt
                for item, cnt in npc_items.items()
                if item != "money" and cnt > 0
            }
            if filtered:
                character_inventories[npc_name] = filtered

        if character_inventories:
            context["character_inventories"] = character_inventories

        # Add known NPC information
        npc_data = self.lore.get("npc", {})
        if npc_data:
            context["known_npc_names"] = list(npc_data.keys())

            # NPCs at player's current location
            player_loc = self.game_memory.get_character_location("user")
            if player_loc and (player_loc.get("town") or player_loc.get("kingdom")):
                npcs_here = []
                for npc_name, npc_info in npc_data.items():
                    npc_loc = self.game_memory.get_character_location(npc_name)
                    if npc_loc:
                        # Check if NPC is at same town (or same kingdom if no town match)
                        if (npc_loc.get("town") == player_loc.get("town")
                            or (npc_loc.get("kingdom") == player_loc.get("kingdom") and not player_loc.get("town"))
                        ):
                            npcs_here.append(
                                {
                                    "name": npc_name,
                                    "occupation": npc_info.get("occupation", "Unknown"),
                                }
                            )
                context["npcs_at_current_location"] = npcs_here

        return context

    def _get_recent_history(self) -> str:
        """Get last N turns of game history"""
        if self.game_memory is None:
            # Fall back to start message from lore when no game memory
            return self.lore.get("start", "")

        try:
            n = self.config.history_depth
            turns = self.game_memory.get_last_n_turns(n, character="")

            if not turns:
                # Fall back to start message from lore
                return self.lore.get("start", "")

            history_parts = []
            for turn in reversed(turns):  # Oldest first
                game_action = turn.get("game_action", "")
                displayed_action = turn.get("displayed_action", "")
                user_input = turn.get("user_input", "")

                if user_input or game_action or displayed_action:
                    entry = f"Turn {turn.get('turn', '?')}:"
                    if user_input:
                        entry += f" Player said: {user_input}"
                    if game_action:
                        entry += f" -> Action: {game_action}"
                    if displayed_action:
                        entry += f" | Game: {displayed_action}"
                    history_parts.append(entry)

            return "\\n\\n".join(history_parts[-n:])  # Limit to n entries
        except Exception as e:
            logger.warning(f"Error getting recent history: {e}")
            return ""

    def _format_dynamic_context(self, user_action: str, dynamic_ctx: Dict[str, Any]) -> List[str]:
        user_msg_parts = [f"Player input: {user_action}"]

        if dynamic_ctx:
            user_msg_parts.append("\\n=== CURRENT SITUATION ===")

            if "current_location" in dynamic_ctx:
                loc = dynamic_ctx["current_location"]
                loc_str = f"Location: Town: {loc.get('town', 'Unknown')}, Kingdom: {loc.get('kingdom', 'Unknown')}"
                user_msg_parts.append(loc_str)

            if "npcs_at_location" in dynamic_ctx and dynamic_ctx["npcs_at_location"]:
                npcs = ", ".join(
                    f"{n['name']} ({n['occupation']})"
                    for n in dynamic_ctx["npcs_at_location"]
                )
                user_msg_parts.append(f"NPCs present: {npcs}")

            if (
                "character_locations" in dynamic_ctx
                and dynamic_ctx["character_locations"]
            ):
                loc_parts = []
                for char_name, loc_data in dynamic_ctx["character_locations"].items():
                    if loc_data.get("town") or loc_data.get("kingdom"):
                        location_str = f"{loc_data.get('town', 'Unknown')}, {loc_data.get('kingdom', 'Unknown Kingdom')}"
                        loc_parts.append(f"{char_name}: {location_str}")
                user_msg_parts.append(f"Character locations: {' | '.join(loc_parts)}")

            if (
                "character_inventories" in dynamic_ctx
                and dynamic_ctx["character_inventories"]
            ):
                inv_parts = []
                for char_name, items in dynamic_ctx["character_inventories"].items():
                    # Format: item or item(count) if count > 1, limit to 5 items per character
                    item_strs = []
                    for item, count in list(items.items())[:5]:
                        item_strs.append(f"{item}({count})" if count > 1 else item)
                    if len(items) > 5:
                        item_strs.append(f"+{len(items) - 5} more")
                    inv_parts.append(f"{char_name}: {', '.join(item_strs)}")
                user_msg_parts.append(f"Inventories: {' | '.join(inv_parts)}")

            if (
                "recent_game_events" in dynamic_ctx
                and dynamic_ctx["recent_game_events"]
            ):
                user_msg_parts.append("\\n=== RECENT EVENTS ===")
                user_msg_parts.append(dynamic_ctx["recent_game_events"])

            # Add known NPC names
            if "known_npc_names" in dynamic_ctx:
                npc_list = ", ".join(dynamic_ctx["known_npc_names"])
                user_msg_parts.append(f"Known NPCs in game: {npc_list}")

            # Add NPCs at current location
            if "npcs_at_current_location" in dynamic_ctx:
                if dynamic_ctx["npcs_at_current_location"]:
                    present_npcs = ", ".join(
                        f"{n['name']} ({n['occupation']})"
                        for n in dynamic_ctx["npcs_at_current_location"]
                    )
                    user_msg_parts.append(f"NPCs present at current location: {present_npcs}")
                else:
                    user_msg_parts.append("NPCs present at current location: None")
        return user_msg_parts

    def compile_messages(
        self,
        action: str,
        context: Optional[str] = None,
        use_dynamic_context: bool = True,
    ) -> List[Dict[str, str]]:
        """
        Build messages for the LLM with dynamic context.

        Args:
            action: Player's input to validate
            context: Optional additional context string (deprecated, use dynamic context)
            enforce_json_output: Whether to add JSON schema enforcement
            use_dynamic_context: Whether to extract context from game memory
        """

        self._build_system_prompt()
        self.system_prompt += self._build_examples_message()

        # Build dynamic context
        dynamic_ctx = {}
        if use_dynamic_context:
            dynamic_ctx = self._build_dynamic_context(action)

        # Format user message with all context
        user_msg_parts = self._format_dynamic_context(action, dynamic_ctx)

        # Add any additional manual context
        if context and context.strip():
            user_msg_parts.append(f"\\nAdditional context: {context}")

        user_message = "\\n\\n".join(user_msg_parts)

        return [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_message},
        ]

    def run(
        self,
        action: str,
        context: Optional[str] = None,
        use_dynamic_context: bool = True,
        **llm_kwargs,
    ) -> ValidateClassifyAction:
        """
        Validates player's input.

        Args:
            action: Player's input to validate
            context: Optional additional context string (deprecated)
            enforce_json_output: Whether to enforce JSON schema in response
            use_dynamic_context: Whether to extract dynamic context from game memory
            llm_kwargs: Additional kwargs for LLM call

        Returns:
            ValidateClassifyAction model with validation results
        """
        logger.info("Validating player input")
        messages = self.compile_messages(action, context, use_dynamic_context)
        return self.submit_messages(messages, **llm_kwargs)


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
- Identify who is subject to inventory changes.
- Identify who provided/gave/etc inventory items.
Never add any thinking."""

    def compile_messages(
        self,
        action: str,
        context: str,
        inventory: List[str] = None,
        additional_context: str = None,
        enforce_json_output: bool = False,
    ) -> List[Dict[str, str]]:
        """
        Build the messages/payload for the LLM
        :param action: str -- human action
        :param context: str -- context (e.g. previous actions/etc)
        :param inventory: List[str] -- list of inventory items
        :param additional_context: str -- any additional information to consider
        :param enforce_json_output: bool -- adds system prompt with the JSON schema, default: False
        :return:
        """
        TASK_PRT = f"""Player's actions: {action}"""
        if context is not None and context != "":
            TASK_PRT += f"""Context: {context}"""
        TASK_PRT += f"""Player's inventory: {inventory}"""
        if additional_context is not None and additional_context != "":
            TASK_PRT += f"Additional context: {additional_context}"

        system_message = []
        if enforce_json_output:
            system_message = self.add_struct_sys_prompt()

        return system_message + [
            {"role": "system", "content": self.sys_prt},
            {"role": "user", "content": TASK_PRT},
        ]

    def run(
        self,
        action: str,
        context: str,
        inventory: List[str] = None,
        additional_context: str = None,
        enforce_json_output: bool = False,
        **llm_kwargs,
    ) -> pydantic.BaseModel:
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
        __msgs = self.compile_messages(
            action, context, inventory, additional_context, enforce_json_output
        )
        return self.submit_messages(__msgs, **llm_kwargs)


# ----------------------------------------- PLAYER'S PHYSICAL/MENTAL UPDATER -------------------------------------------
class PlayerState(BaseTool):
    def __init__(self, llm_client):
        super().__init__(llm_client, PlayerState)
        self.sys_prt = "You are RPG Game Engine. Task: detect changes in physical and mental state of the player."

    def compile_messages(
        self,
        action: str,
        context: str,
        additional_context: str = None,
        enforce_json_output: bool = False,
    ) -> List[Dict[str, str]]:
        task = f"Player: {action}"
        if context is not None and context != "":
            task += f"\nContext: {context}"
        if additional_context is not None and additional_context != "":
            task += f"\nAdditional context: {additional_context}"

        system_message = []
        if enforce_json_output:
            system_message = self.add_struct_sys_prompt()

        return system_message + [
            {"role": "system", "content": self.sys_prt},
            {"role": "user", "content": task},
        ]

    def run(
        self,
        action: str,
        context: str,
        additional_context: str = None,
        enforce_json_output: bool = False,
        **llm_kwargs,
    ) -> PlayerState:
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
        __msgs = self.compile_messages(
            action, context, additional_context, enforce_json_output
        )
        return self.submit_messages(__msgs, **llm_kwargs)


# ----------------------------------------- PLAYER'S LOCATION UPDATER -------------------------------------------
class PlayerLocation(BaseTool):
    def __init__(self, llm_client):
        super().__init__(llm_client, PlayerLocation)
        self.sys_prt = """You are RPG Game Engine. Task to identify:
- current location if any
- destination location if any"""

    def compile_messages(
        self,
        action: str,
        context: str,
        additional_context: str = None,
        enforce_json_output: bool = False,
    ) -> List[Dict[str, str]]:
        TASK_PRT = f"""Player's actions: {action}"""
        if context is not None and context != "":
            TASK_PRT += f"""Context: {context}"""
        if additional_context is not None and additional_context != "":
            TASK_PRT += f"Additional context: {additional_context}"

        system_message = []
        if enforce_json_output:
            system_message = self.add_struct_sys_prompt()

        return system_message + [
            {"role": "system", "content": self.sys_prt},
            {"role": "user", "content": TASK_PRT},
        ]

    def run(
        self,
        action: str,
        context: str,
        additional_context: str = None,
        enforce_json_output: bool = False,
        **llm_kwargs,
    ) -> PlayerLocation:
        logger.info("Detecting location change")
        __msgs = self.compile_messages(
            action, context, additional_context, enforce_json_output
        )
        return self.submit_messages(__msgs, **llm_kwargs)
