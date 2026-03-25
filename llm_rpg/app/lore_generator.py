"""
Function to generate game lore based on the config and prints the nice output to entertain the user
"""

from llm_rpg.engine.lore_generation import LoreGeneratorGvt
from llm_rpg.templates.base_client import BaseClient
from typing import Dict, Any
import logging
from time import sleep
import os
import json


def GenerateLore(
    llm: BaseClient,
    gen_config: Dict[str, Any],
    save_location: str,
    console_manager,
    full_config: Dict[str, Any],
    **llm_kw,
) -> Dict[str, Any]:
    """
    Generates the game lore.
    :param llm: Callable: BaseClient
    :param gen_config: Dict[str, Any] -- lore generation parameters (merged from config and user input)
    :param save_location: str -- save location
    :param full_config: Dict[str, Any] -- full config (AppConfig after validation) including temperatures section
    :return:
    """
    logger = logging.getLogger(__name__)

    temps = full_config["temperatures"]

    temp_world_gen = temps["lore_world_gen"]
    temp_npc_gen = temps["lore_npc_gen"]
    temp_action_rules = temps["lore_action_rules"]

    num_kingdoms = gen_config["kingdoms"]
    num_towns = gen_config["towns_per_kingdom"]
    num_npc = gen_config["companions"]
    num_npc_rules_per_category = gen_config["num_npc_rules_per_category"]
    num_world_rules_per_category = gen_config["num_world_rules_per_category"]
    max_retries = gen_config["max_generation_retries"]
    temperature_cooldown_step = gen_config["temperature_cooldown_step"]
    temperature_min = gen_config["temperature_min"]
    world_type = gen_config["world_setting"]
    world_kind = gen_config["world_type"]

    generator = LoreGeneratorGvt(
        llm,
        temperature_cooldown_step=temperature_cooldown_step,
        temperature_min=temperature_min,
    )

    # ----- Generating the world -----
    msg = "Generating the world"
    logger.info(msg)
    if world_kind in ["dark", "neutral", "funny"]:
        msg = f"Generating the world with {num_world_rules_per_category} rules per category for a {world_kind} {world_type} world."
        logger.info(msg)
        console_manager.console.print(msg)
        generator.generate_world(
            num_world_rules_per_category,
            world_kind,
            world_type,
            max_retries=max_retries,
            temperature=temp_world_gen,
        )
    else:
        raise ValueError(f"World kind is not recognized! Got {world_kind}")

    with open(os.path.join(save_location, f"lore.json"), "w") as f:
        json.dump(generator.lore, f, indent=4)

    # ----- Generating the kingdoms -----
    msg = f"Generating {num_kingdoms} kingdoms"
    logger.info(msg)
    console_manager.console.print(msg)
    generator.generate_kingdoms(num_kingdoms=num_kingdoms, **llm_kw)
    with open(os.path.join(save_location, f"lore.json"), "w") as f:
        json.dump(generator.lore, f, indent=4)

    # ----- Generating the towns -----
    msg = f"Generating {num_towns} towns for each kingdom"
    logger.info(msg)
    console_manager.console.print(msg)
    generator.generate_towns(num_towns=num_towns, **llm_kw)
    with open(os.path.join(save_location, f"lore.json"), "w") as f:
        json.dump(generator.lore, f, indent=4)

    # ----- Generating human player card -----
    msg = "Generating human player character"
    logger.info(msg)
    console_manager.console.print(msg)
    generator.generate_human_player(**llm_kw)
    with open(os.path.join(save_location, f"lore.json"), "w") as f:
        json.dump(generator.lore, f, indent=4)

    # ----- Generating NPCs -----
    msg = f"Generating {num_npc} NPC(s)"
    logger.info(msg)
    console_manager.console.print(msg)
    generator.generate_npc(num_chars=num_npc, temperature=temp_npc_gen)
    with open(os.path.join(save_location, f"lore.json"), "w") as f:
        json.dump(generator.lore, f, indent=4)

    # ----- Generating action rules for the NPCs -----
    msg = f"Generation action rules for the NPCs"
    logger.info(msg)
    console_manager.console.print(msg)
    generator.generate_npc_action_rules(
        num_rules_per_category=num_npc_rules_per_category,
        max_retries=max_retries,
        temperature=temp_action_rules,
    )
    with open(os.path.join(save_location, f"lore.json"), "w") as f:
        json.dump(generator.lore, f, indent=4)

    # ----- Starting point -----
    msg = f"Generating the starting point"
    logger.info(msg)
    console_manager.console.print(msg)
    generator.gen_starting_point(**llm_kw)
    with open(os.path.join(save_location, f"lore.json"), "w") as f:
        json.dump(generator.lore, f, indent=4)

    logger.info("Saving the lore")
    with open(os.path.join(save_location, f"lore.json"), "w") as f:
        json.dump(generator.lore, f, indent=4)

    logger.info("Saving the generation prompts")
    with open(os.path.join(save_location, f"gen_lore_params.json"), "w") as f:
        json.dump(generator.game_gen_params, f, indent=4)

    # Log summary
    generator.log_generation_summary()

    return generator.lore
