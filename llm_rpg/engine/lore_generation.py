"""
Collection of tools to generate a game lore using some basic inputs

There are currently 2 major classes:
1. GenerateWorld -- generates world and conditions to lose/win
2. GenerateCharacter -- generates characters (player/npc)

These classes provide tools to generate the respective lore part. They are governed
 by LoreGeneratorGvt which instantiates both of these and calls with proper arguments.
"""

import logging
import time
from typing import Dict, Any, List

from llm_rpg.utils.prompt_utils import generate_with_retry
from llm_rpg.prompts.response_models import WorldDescriptionModel

logger = logging.getLogger(__name__)

from llm_rpg.prompts.lore_generation import (
    gen_world_rules_msgs,
    gen_world_msgs,
    gen_kingdom_msgs,
    gen_towns_msgs,
    gen_human_char_msgs,
    gen_condition_end_game,
    gen_npc_behavior_rules,
    gen_entry_point_msg,
    _get_default_world_rules,
    _get_default_npc_rules,
    _get_default_character,
    _get_default_npc_character,
    _get_default_kingdoms,
    kingdoms_traits,
)
from llm_rpg.prompts.response_models import (
    WorldRulesModel,
    NPCBehaviorRulesModel,
    CharacterModel,
)

from llm_rpg.utils.helpers import (
    parse_kingdoms_response,
    parse_character,
    input_not_ok,
)

from llm_rpg.templates.base_client import BaseClient

import random
from time import sleep
from copy import deepcopy as dCP


def _log_generation_summary(game_gen_params: Dict[str, Any], lore: Dict[str, Any]):
    """Log summary of generation results showing what used fallback"""
    logger.info("=" * 60)
    logger.info("LORE GENERATION SUMMARY")
    logger.info("=" * 60)

    issues = []
    successes = []

    if "world_outline" in game_gen_params:
        if game_gen_params["world_outline"].get("used_fallback"):
            issues.append("World Rules (used defaults)")
        else:
            successes.append("World Rules")

    if "npc_rules" in lore and lore["npc_rules"]:
        npc_params = game_gen_params.get("npc_rules", {})
        generated_npcs = npc_params.get("generated", [])
        fallback_usage = npc_params.get("fallback_usage", {})

        for npc_name in generated_npcs:
            if fallback_usage.get(npc_name):
                issues.append(f"NPC Rules: {npc_name} (used defaults)")
            else:
                successes.append(f"NPC Rules: {npc_name}")

    if successes:
        logger.info(f"✓ Successfully generated ({len(successes)} components):")
        for item in successes:
            logger.info(f"  - {item}")

    if issues:
        logger.warning(f"⚠ Components using fallback defaults ({len(issues)}):")
        for item in issues:
            logger.warning(f"  - {item}")
        logger.warning("Consider checking LLM connection and regenerating if needed.")
    else:
        logger.info("All components generated successfully without fallback!")

    logger.info("=" * 60)


class LoreGeneratorGvt:
    def __init__(self, client: BaseClient, **kwargs):
        """
        Governor that generates game lore. The game lore is generated as a plan/brief outline
        as it is intended for feeding into an LLM. A separate component will generate a human-readable
        text.

        :param client: the LLM client
        :param kwargs: any arguments needed in the future
        """
        self.client = client
        self.lore = {}
        self.game_gen_params = {}

        # We can generate own world description or use default one
        # If no world description/outline/rues were generated, then
        # the default will be used
        self.lore["world_outline"] = None
        # Temperature cooldown settings for retry logic (from config or defaults)
        if "temperature_cooldown_step" in kwargs:
            self.temp_cooldown_step = kwargs.pop("temperature_cooldown_step")
        else:
            logger.info("temperature_cooldown_step not in config, using default 0.1")
            self.temp_cooldown_step = 0.1

        if "temperature_min" in kwargs:
            self.temp_min = kwargs.pop("temperature_min")
        else:
            logger.info("temperature_min not in config, using default 0.5")
            self.temp_min = 0.5

        self.world_generator = GenerateWorld(
            self.client,
            temperature_cooldown_step=self.temp_cooldown_step,
            temperature_min=self.temp_min,
        )
        self.char_gen = GenerateCharacter(
            self.client,
            temperature_cooldown_step=self.temp_cooldown_step,
            temperature_min=self.temp_min,
        )

    def _generate_world_outline(
        self, num_rules: int, kind: str, world_type: str, **client_kwargs
    ):
        """
        Generates world rules/outline.
        :param num_rules:
        :param kind: dark, funny, normal
        :param world_type: fantasy, sci-fi
        :param client_kwargs:
        :return:
        """
        self.world_generator.gen_world_outline(
            num_rules, world_type, kind, **client_kwargs
        )
        self.WORLD_DESC = self.world_generator.game_lore["world_outline"]
        self.lore["world_outline"] = self.world_generator.game_lore["world_outline"]
        self.game_gen_params.update(self.world_generator.game_gen_params)

    def generate_world(
        self, num_rules: int, kind: str, world_type: str, **client_kwargs
    ):
        """
        Generates world description and the world based on the AI generated rules description
        :param num_rules: number of world rules
        :param kind: dark, neutral, funny
        :param world_type: fantasy, sci-fi
        :param client_kwargs:
        :return:
        """
        # Pop max_retries before passing to gen_world() since it's not an LLM parameter
        _ = client_kwargs.pop("max_retries", None)

        self._generate_world_outline(num_rules, kind, world_type, **client_kwargs)
        self.world_generator.gen_world(self.lore["world_outline"], **client_kwargs)
        self.lore.update(self.world_generator.game_lore)
        self.game_gen_params.update(self.world_generator.game_gen_params)

    def generate_kingdoms(
        self, num_kingdoms: int, kingdom_types: str | None = None, **client_kw
    ):
        self.world_generator.gen_kingdoms(num_kingdoms, kingdom_types, **client_kw)
        self.lore.update(self.world_generator.game_lore)
        self.game_gen_params.update(self.world_generator.game_gen_params)

    def generate_towns(self, num_towns, **client_kw):
        self.world_generator.gen_towns(num_towns, **client_kw)
        self.lore.update(self.world_generator.game_lore)
        self.game_gen_params.update(self.world_generator.game_gen_params)

    def generate_human_player(self, **client_kw):
        # random choice of starting location
        kingdom_name = random.choice(list(self.lore["kingdoms"].keys()))
        town_name = random.choice(list(self.lore["towns"][kingdom_name].keys()))

        ans = self.char_gen.gen_characters(
            self.lore,
            "human",
            num_chars=1,
            kingdom_name=kingdom_name,
            town_name=town_name,
            **client_kw,
        )
        _key = list(ans.keys())[0]
        self.lore["human_player"] = ans[_key]

        if "start_location" not in self.lore:
            self.lore["start_location"] = {}

        self.lore["start_location"]["human"] = {
            "kingdom": kingdom_name,
            "town": town_name,
        }
        self.game_gen_params.update(self.char_gen.char_gen_params)

    def generate_npc(self, num_chars: int = 1, **client_kw):
        if "start_location" in self.lore and "human" in self.lore["start_location"]:
            kingdom_name = self.lore["start_location"]["human"]["kingdom"]
            town_name = self.lore["start_location"]["human"]["town"]
        else:
            logger.error(f"You must generate a human character before!")
            raise KeyError(f"You must generate a human character before!")

        ans = self.char_gen.gen_characters(
            self.lore,
            "human",
            num_chars=num_chars,
            kingdom_name=kingdom_name,
            town_name=town_name,
            **client_kw,
        )

        if "start_location" not in self.lore:
            self.lore["start_location"] = {}

        if "npc" not in self.lore["start_location"]:
            self.lore["start_location"]["npc"] = {}

        self.lore["npc"] = {}

        for _key in list(ans.keys()):
            logger.info(f"Adding {_key}")
            self.lore["npc"][_key] = dCP(ans[_key])
            self.lore["start_location"]["npc"][_key] = {
                "kingdom": kingdom_name,
                "town": town_name,
            }

    def generate_end_game_conditions(self, num_conditions: int = 3):
        self.world_generator.gen_end_game_conditions(
            player_desc=self.lore["human_player"],
            player_loc=self.lore["start_location"]["human"]["kingdom"],
            num_conditions=num_conditions,
        )
        self.lore.update(self.world_generator.game_lore)
        self.game_gen_params.update(self.world_generator.game_gen_params)

    def generate_npc_action_rules(
        self, num_rules_per_category: int = 3, **client_kw
    ) -> None:
        """Generate categorized behavioral rules for every NPC with retry and fallback"""
        if "npc" not in self.lore:
            logger.error("No NPCs found - generate NPCs first")
            raise KeyError("Must generate NPCs before generating action rules")

        if "npc_rules" not in self.lore:
            self.lore["npc_rules"] = {}

        max_retries = client_kw.pop("max_retries", 3)

        gen_results = {}

        for npc_name in self.lore["npc"]:
            logger.info(f"Generating behavioral rules for {npc_name}")

            msgs = gen_npc_behavior_rules(
                self.lore["npc"][npc_name],
                num_rules_per_category=num_rules_per_category,
            )

            ans = generate_with_retry(
                client=self.client,
                messages=msgs,
                response_model=NPCBehaviorRulesModel,
                max_retries=max_retries,
                fallback_value=_get_default_npc_rules(),
                component_name=f"NPC Rules: {npc_name}",
                # Allow per-call override, otherwise use instance variable (from config)
                temperature_cooldown_step=client_kw.pop(
                    "temperature_cooldown_step", self.temp_cooldown_step
                ),
                temperature_min=client_kw.pop("temperature_min", self.temp_min),
                **client_kw,
            )

            self.lore["npc_rules"][npc_name] = ans["message"]

            used_fallback = ans["stats"]["prompt_tokens"] == 0
            gen_results[npc_name] = used_fallback

            status = "with fallback" if used_fallback else "successfully"
            logger.info(f"Generated rules for {npc_name} {status}")

        self.game_gen_params["npc_rules"] = {
            "generated": list(gen_results.keys()),
            "fallback_usage": gen_results,
            "max_retries": max_retries,
        }

        logger.info("All NPC behavioral rules generation completed")

    def gen_starting_point(self, **client_kw):
        """
        Generates the starting point for the game
        :param client_kw:
        :return:
        """
        human_player = self.lore["human_player"]
        human_start_k = self.lore["start_location"]["human"]["kingdom"]
        human_start_t = self.lore["start_location"]["human"]["town"]

        k_desc = self.lore["kingdoms"][human_start_k]
        t_desc = self.lore["towns"][human_start_k][human_start_t]
        world_desc = self.lore["world"]

        if "npc" in self.lore:
            npcs_desc = self.lore["npc"]
            npc_start_location = self.lore["start_location"]["npc"]
        else:
            npcs_desc = {}
            npc_start_location = {}

        entry_msgs = gen_entry_point_msg(
            world_desc,
            human_player,
            human_start_k,
            k_desc,
            human_start_t,
            t_desc,
            npcs_desc,
            npc_start_location,
        )

        ans = self.client.chat(entry_msgs, **client_kw)
        self.game_gen_params["start"] = entry_msgs
        self.lore["start"] = ans["message"]

    def log_generation_summary(self):
        """Log summary of what succeeded vs used fallback during generation"""
        _log_generation_summary(self.game_gen_params, self.lore)


class GenerateWorld:
    def __init__(self, client: BaseClient, **kwargs):
        """Init the class. Not sure what shall be here"""
        self.client = client
        self.game_lore = {}
        self.game_gen_params = {}

        # Temperature cooldown settings for retry logic (from config or defaults)
        if "temperature_cooldown_step" in kwargs:
            self.temp_cooldown_step = kwargs.pop("temperature_cooldown_step")
        else:
            logger.info(
                "GenerateWorld: temperature_cooldown_step not in config, using default 0.1"
            )
            self.temp_cooldown_step = 0.1

        if "temperature_min" in kwargs:
            self.temp_min = kwargs.pop("temperature_min")
        else:
            logger.info(
                "GenerateWorld: temperature_min not in config, using default 0.5"
            )
            self.temp_min = 0.5

    def gen_world_outline(
        self,
        num_rules: int,
        world_type: str = "fantasy",
        kind: str = "dark",
        **client_kw,
    ):
        """Generate structured world rules with config-driven retry and fallback"""
        msgs = gen_world_rules_msgs(num_rules, world_type, kind)

        max_retries = client_kw.pop("max_retries", 3)

        response = generate_with_retry(
            client=self.client,
            messages=msgs,
            response_model=WorldRulesModel,
            max_retries=max_retries,
            fallback_value=_get_default_world_rules(),
            component_name="World Rules",
            # Allow per-call override, otherwise use instance variable (from config)
            temperature_cooldown_step=client_kw.pop(
                "temperature_cooldown_step", self.temp_cooldown_step
            ),
            temperature_min=client_kw.pop("temperature_min", self.temp_min),
            **client_kw,
        )

        self.game_lore["world_outline"] = response["message"]

        logger.info(
            f"Created structured world outline with categories: "
            f"{list(self.game_lore['world_outline'].keys())}"
        )
        logger.debug(f"Prompt tokens: {response['stats']['prompt_tokens']}")
        logger.debug(f"Eval tokens: {response['stats']['eval_tokens']}")

        self.game_gen_params["world_outline"] = {
            "model": self.client.model_name,
            "messages": msgs,
            "structured_model": "WorldRulesModel",
            "used_fallback": response["stats"]["prompt_tokens"] == 0,
            "max_retries": max_retries,
        }

    def gen_world(self, world_desc: str, **client_kw):
        """
        Generates world description using structured output.

        This is a critical game component - no fallback provided. If generation
        fails after all retries, the exception will propagate and crash the app.
        """
        # Generate prompt
        world_msg = gen_world_msgs(world_desc)

        # Extract retry config
        max_retries = client_kw.pop("max_generation_retries", 3)

        # Use structured output with retry (NO FALLBACK - critical component)
        response = generate_with_retry(
            self.client,
            world_msg,
            response_model=WorldDescriptionModel,
            max_retries=max_retries,
            fallback_value=None,  # NO FALLBACK - let it fail if generation breaks
            component_name="World Description",
            temperature_cooldown_step=client_kw.pop(
                "temperature_cooldown_step", self.temp_cooldown_step
            ),
            temperature_min=client_kw.pop("temperature_min", self.temp_min),
            **client_kw,
        )

        # Store as dict (already JSON-serializable from model_dump())
        self.game_lore["world"] = response["message"]

        logger.info(f"Created world: {self.game_lore['world']['name']}")
        logger.debug(f"Prompt tokens: {response['stats']['prompt_tokens']}")
        logger.debug(f"Eval tokens: {response['stats']['eval_tokens']}")

        self.game_gen_params["world"] = {
            "model": self.client.model_name,
            "messages": world_msg,
            "structured_model": "WorldDescriptionModel",
            "used_fallback": response["stats"]["prompt_tokens"] == 0,
            "max_retries": max_retries,
        }

    def gen_kingdoms(
        self, num_kingdoms: int, kingdom_types: str | None = None, **client_kw
    ):
        """
        Generates kingdoms in the world using structured output.

        This is a critical game component - no fallback provided. If generation
        fails after all retries, the exception will propagate and crash the app.
        """
        from llm_rpg.prompts.response_models import KingdomsModel

        # Use provided kingdom types or default to predefined traits
        if kingdom_types is None or kingdom_types == "":
            kt = kingdoms_traits
        else:
            kt = kingdom_types

        # Generate prompt
        kingdoms_msg = gen_kingdom_msgs(num_kingdoms, kt, self.game_lore["world"])

        # Extract retry config
        max_retries = client_kw.pop("max_generation_retries", 3)

        # Use structured output with retry (NO FALLBACK - critical component)
        response = generate_with_retry(
            self.client,
            kingdoms_msg,
            response_model=KingdomsModel,
            max_retries=max_retries,
            fallback_value=None,  # NO FALLBACK - let it fail if generation breaks
            component_name="Kingdoms",
            temperature_cooldown_step=client_kw.pop(
                "temperature_cooldown_step", self.temp_cooldown_step
            ),
            temperature_min=client_kw.pop("temperature_min", self.temp_min),
            **client_kw,
        )

        # Convert from list to dict for backward compatibility with downstream code
        kingdoms_data = response["message"][
            "kingdoms"
        ]  # List of dicts (JSON-serializable)
        self.game_lore["kingdoms"] = {
            k["name"]: k  # Each k is already a plain dict from model_dump()
            for k in kingdoms_data
        }

        logger.info(f"Created kingdoms: {list(self.game_lore['kingdoms'].keys())}")
        logger.debug(f"Prompt tokens: {response['stats']['prompt_tokens']}")
        logger.debug(f"Eval tokens: {response['stats']['eval_tokens']}")

        self.game_gen_params["kingdoms"] = {
            "model": self.client.model_name,
            "messages": kingdoms_msg,
            "structured_model": "KingdomsModel",
            "used_fallback": response["stats"]["prompt_tokens"] == 0,
            "max_retries": max_retries,
        }

    def gen_towns(self, num_towns, **client_kw):
        """
        Generates towns for each kingdom using structured output.

        This is a critical game component - no fallback provided. If generation
        fails after all retries, the exception will propagate and crash the app.
        """
        from llm_rpg.prompts.response_models import TownsModel

        self.game_lore["towns"] = {}
        self.game_gen_params["towns"] = {}

        for kingdom in self.game_lore["kingdoms"]:
            logger.info(f"Generating {num_towns} towns for {kingdom}")

            # Generate prompt
            towns_msg = gen_towns_msgs(
                num_towns, self.game_lore["world"], self.game_lore["kingdoms"], kingdom
            )

            # Extract retry config
            max_retries = client_kw.pop("max_generation_retries", 3)

            # Use structured output with retry (NO FALLBACK - critical component)
            response = generate_with_retry(
                self.client,
                towns_msg,
                response_model=TownsModel,
                max_retries=max_retries,
                fallback_value=None,  # NO FALLBACK - let it fail if generation breaks
                component_name=f"Towns for {kingdom}",
                temperature_cooldown_step=client_kw.pop(
                    "temperature_cooldown_step", self.temp_cooldown_step
                ),
                temperature_min=client_kw.pop("temperature_min", self.temp_min),
                **client_kw,
            )

            # Convert from list to dict for backward compatibility
            towns_data = response["message"]["towns"]  # List of dicts
            self.game_lore["towns"][kingdom] = {
                t["name"]: t  # Each t is already a plain dict from model_dump()
                for t in towns_data
            }

            logger.info(
                f"Created towns for {kingdom}: {list(self.game_lore['towns'][kingdom].keys())}"
            )
            logger.debug(f"Prompt tokens: {response['stats']['prompt_tokens']}")
            logger.debug(f"Eval tokens: {response['stats']['eval_tokens']}")

            self.game_gen_params["towns"][kingdom] = {
                "model": self.client.model_name,
                "messages": towns_msg,
                "structured_model": "TownsModel",
                "used_fallback": response["stats"]["prompt_tokens"] == 0,
                "max_retries": max_retries,
            }

    def gen_end_game_conditions(
        self,
        player_desc: Dict[str, str],
        player_loc: str,
        num_conditions: int,
    ) -> None:
        """
        Generates conditions to win and loose the game given the description of the human player
        :param player_loc: starting location of the human player
        :param player_desc: description of the human player
        :param num_conditions: number of conditions
        :return:
        """

        kinds = ["win", "loose"]

        self.game_lore["end_game"] = {}
        for kind in kinds:
            logger.info(f"Generating {num_conditions} conditions to {kind}")
            try:
                cond_gen_msgs = gen_condition_end_game(
                    self.game_lore,
                    player_desc,
                    player_loc,
                    num_conditions,
                    kind,
                )
                raw_response = self.client.chat(cond_gen_msgs)
                self.game_lore["end_game"][kind] = raw_response["message"]
                self.game_gen_params["end_game"][kind] = {
                    "model": self.client.model_name,
                    "messages": cond_gen_msgs,
                }

            except Exception as e:
                logger.error(
                    f'Could not generate conditions to "{kind}" with "{e}" error'
                )
                raise ValueError(
                    f'Could not generate conditions to "{kind}" with "{e}" error'
                )
        logger.info("Done")


class GenerateCharacter:
    global CHAR_DESC_STRUCT

    def __init__(self, client: BaseClient, **kwargs):
        self.client = client

        # stores all characters generated (human, npcs, etc)
        self.characters = {}
        # store this data for possible debugging and logging
        self.char_gen_params = {}
        # a mapping between names and kinds (human, npc, etc.)
        self.characters_kinds = {}

        # Temperature cooldown settings for retry logic
        if "temperature_cooldown_step" in kwargs:
            self.temp_cooldown_step = kwargs.pop("temperature_cooldown_step")
        else:
            logger.info(
                "GenerateCharacter: temperature_cooldown_step not provided, using default 0.1"
            )
            self.temp_cooldown_step = 0.1

        if "temperature_min" in kwargs:
            self.temp_min = kwargs.pop("temperature_min")
        else:
            logger.info(
                "GenerateCharacter: temperature_min not provided, using default 0.5"
            )
            self.temp_min = 0.5

    def gen_characters(
        self, game_lore: Dict[str, str], kind: str = "human", **kwargs
    ) -> Dict[str, Any]:
        """
        Creates a character

        :param kind: human, npc
        :param kwargs:
            char_desc_struct -- a dictionary with mandatory fields to generate
            num_char -- number of characters to generate
        :return:
        """

        characters = None

        if kind == "human":
            characters = self.__gen_playable_char(game_lore, **kwargs)
            logger.info(f"Generated {len(characters.keys())} characters")

        if not characters and characters != {}:
            logger.warning("Generation was not successful")
        else:
            self.characters.update(characters)
            # update the mapping
            for key in characters:
                self.characters_kinds[key] = kind

        return characters

    def __gen_playable_char(
        self, game_lore: Dict[str, str], **kwargs
    ) -> Dict[str, Any]:
        """Generates ONE playable character using structured output"""

        kingdom_name = kwargs.get("kingdom_name", "")
        town_name = kwargs.get("town_name", "")
        max_retries = kwargs.pop("max_retries", 3)

        names2avoid = list(self.characters.keys())
        logger.info(f"Generating 1 character, avoiding names: {names2avoid}")

        char_gen_msgs = gen_human_char_msgs(
            game_lore, kingdom_name, town_name, num_chars=1, avoid_names=names2avoid
        )
        self.char_gen_params["characters"] = char_gen_msgs

        # Extract client kwargs (remove non-client parameters)
        client_kw = {
            k: v
            for k, v in kwargs.items()
            if k not in ["char_desc_struct", "num_chars", "kingdom_name", "town_name"]
        }

        try:
            response = generate_with_retry(
                client=self.client,
                messages=char_gen_msgs,
                response_model=CharacterModel,
                max_retries=max_retries,
                fallback_value=_get_default_character(),
                component_name="Human Character",
                temperature_cooldown_step=self.temp_cooldown_step,
                temperature_min=self.temp_min,
                **client_kw,
            )

            # Convert to dict (already done by generate_with_retry via model_dump())
            char_data = response["message"]

            # Convert inventory list to string for lore storage
            if isinstance(char_data.get("inventory"), list):
                char_data["inventory"] = ", ".join(char_data["inventory"])

            character_name = char_data["name"]
            logger.info(
                f"Human Character generated: {character_name}, age={char_data['age']}, money={char_data['money']}"
            )

            return {character_name: char_data}

        except Exception as e:
            logger.error(f"Failed to generate human character: {e}")
            # Return fallback character
            fallback = _get_default_character().model_dump()
            fallback["inventory"] = ", ".join(fallback["inventory"])
            logger.info(f"Using fallback character: {fallback['name']}")
            return {fallback["name"]: fallback}
