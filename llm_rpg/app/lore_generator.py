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


def GenerateLore(llm: BaseClient,
                 gen_config: Dict[str, Any],
                 save_location: str,
                 console_manager,
                 **llm_kw) -> Dict[str, Any]:
    """
    Generates the game lore.
    :param llm: Callable: BaseClient
    :param gen_config: Dict[str, Any] -- lore generation parameters
    :param save_location: str -- save location
    :return:
    """
    logger = logging.getLogger(__name__)

    # ----- Lore generation parameters -----
    num_kingdoms = gen_config['kingdoms']
    num_towns = gen_config['towns_per_kingdom']
    num_npc = gen_config['companions']
    num_npc_rules = gen_config['num_npc_rules']
    sleep_sec = gen_config.get('sleep_sec', 0)
    api_delay = gen_config.get('api_delay', 0)
    num_world_rules =  gen_config['num_world_rules']
    world_type = gen_config['world_setting']
    world_kind = gen_config['world_type']

    generator = LoreGeneratorGvt(llm, api_delay=api_delay)

    # ----- Generating the world -----
    msg = "Generating the world"
    logger.info(msg)
    if world_kind in ["dark", "neutral", "funny"]:
        msg = f"Generating the world for with {num_world_rules} rules for a {world_kind} {world_type} world."
        logger.info(msg)
        console_manager.console.print(msg)
        generator.generate_world(num_world_rules, world_kind, world_type, temperature=1.5)
    else:
        raise ValueError(f"World kind is not recognized! Got {world_kind}")

    with open(os.path.join(save_location, f'lore.json'), 'w') as f:
        json.dump(generator.lore, f, indent=4)
    logger.info(f"Sleeping {sleep_sec}")
    sleep(sleep_sec)

    # ----- Generating the kingdoms -----
    msg = f"Generating {num_kingdoms} kingdoms"
    logger.info(msg)
    console_manager.console.print(msg)
    generator.generate_kingdoms(num_kingdoms=num_kingdoms, **llm_kw)
    with open(os.path.join(save_location, f'lore.json'), 'w') as f:
        json.dump(generator.lore, f, indent=4)
    logger.info(f"Sleeping {sleep_sec}")
    sleep(sleep_sec)

    # ----- Generating the towns -----
    msg = f"Generating {num_towns} towns for each kingdom"
    logger.info(msg)
    console_manager.console.print(msg)
    generator.generate_towns(num_towns=num_towns, **llm_kw)
    with open(os.path.join(save_location, f'lore.json'), 'w') as f:
        json.dump(generator.lore, f, indent=4)
    logger.info(f"Sleeping {sleep_sec}")
    sleep(sleep_sec)

    # ----- Generating human player card -----
    msg = "Generating human player character"
    logger.info(msg)
    console_manager.console.print(msg)
    generator.generate_human_player(**llm_kw)
    with open(os.path.join(save_location, f'lore.json'), 'w') as f:
        json.dump(generator.lore, f, indent=4)
    logger.info(f"Sleeping {sleep_sec}")
    sleep(sleep_sec)

    # ----- Generating player's antagonist -----
    msg = "Generating player's antagonist"
    logger.info(msg)
    console_manager.console.print(msg)
    generator.generate_antagonist()
    with open(os.path.join(save_location, f'lore.json'), 'w') as f:
        json.dump(generator.lore, f, indent=4)
    logger.info(f"Sleeping {sleep_sec}")
    sleep(sleep_sec)

    # ----- Generating NPCs -----
    msg = f"Generating {num_npc} NPC(s)"
    logger.info(msg)
    console_manager.console.print(msg)
    generator.generate_npc(num_chars=num_npc, temperature=0.75)
    with open(os.path.join(save_location, f'lore.json'), 'w') as f:
        json.dump(generator.lore, f, indent=4)
    logger.info(f"Sleeping {sleep_sec}")
    sleep(sleep_sec)

    # ----- Describing inventories -----
    msg = f"Describing all inventories"
    logger.info(msg)
    console_manager.console.print(msg)
    generator.describe_inventories(temperature=0.25)
    with open(os.path.join(save_location, f'lore.json'), 'w') as f:
        json.dump(generator.lore, f, indent=4)
    logger.info(f"Sleeping {sleep_sec}")
    sleep(sleep_sec)

    # ----- Generating action rules for the NPCs -----
    msg = f"Generation action rules for the NPCs"
    logger.info(msg)
    console_manager.console.print(msg)
    generator.generate_npc_action_rules(num_npc_rules, temperature=0.9)
    with open(os.path.join(save_location, f'lore.json'), 'w') as f:
        json.dump(generator.lore, f, indent=4)
    logger.info(f"Sleeping {sleep_sec}")
    sleep(sleep_sec)

    # ----- Starting point -----
    msg = f"Generating the starting point"
    logger.info(msg)
    console_manager.console.print(msg)
    generator.gen_starting_point(**llm_kw)
    with open(os.path.join(save_location, f'lore.json'), 'w') as f:
        json.dump(generator.lore, f, indent=4)

    logger.info("Saving the lore")
    with open(os.path.join(save_location, f'lore.json'), 'w') as f:
        json.dump(generator.lore, f, indent=4)

    logger.info("Saving the generation prompts")
    with open(os.path.join(save_location, f'gen_lore_params.json'), 'w') as f:
        json.dump(generator.game_gen_params, f, indent=4)

    return generator.lore