"""
1. Loads lore, creates and populates the game memory.
2. Or: loads lore and the game memory

Return:
    1. lore ready to use (i.e. without inventories, etc)
    2. memory class instance
"""
from llm_rpg.engine.memory import GameMemorySimple
from typing import Dict, List, Any
import os
import logging
from copy import  deepcopy as dCP

logger = logging.getLogger(__name__)


def populate_db(game_lore: Dict[str, Any], db_path: str):

    lore = dCP(game_lore)
    if os.path.exists(db_path):
        raise Exception(f"DB already exists: \"{db_path}\"!")

    npc_names = list(lore['npc'].keys())
    inventory_lut = lore.pop('inventory_lut')

    memory = GameMemorySimple(db_path, npc_names)

    # human player
    logger.info(f"Populating initial inventory for the human player")
    inventory_list = lore['human_player'].pop('inventory')
    items_desc = {}
    inventory_list_counts = {}
    for item in inventory_list:
        items_desc[item] = inventory_lut[item]
        inventory_list_counts[item] = 1
    inventory_list_counts['gold'] = lore['human_player'].pop('money')
    items_desc['gold'] = {}
    for key in inventory_lut[item].keys():
        if key == "name":
            items_desc['gold'][key] = 'gold'
            continue
        if key == "type":
            items_desc['gold'][key] = 'money'
            continue
        items_desc['gold'][key] = ''
    memory.add_inventory_items('human', inventory_list_counts, items_desc)

    # npcs:
    logger.info(f"Populating initial inventory for each NPC")
    for character in npc_names:
        logger.info(f"NPC: \"{character}\"")
        inventory_list = lore['npc'][character].pop('inventory')
        items_desc = {}
        inventory_list_counts = {}
        for item in inventory_list:
            items_desc[item] = inventory_lut[item]
            inventory_list_counts[item] = 1
        inventory_list_counts['gold'] = lore['npc'][character].pop('money')
        items_desc['gold'] = {}
        for key in inventory_lut[item].keys():
            if key == "name":
                items_desc['gold'][key] = 'gold'
                continue
            if key == "type":
                items_desc['gold'][key] = 'money'
                continue
            items_desc['gold'][key] = ''
        memory.add_inventory_items(character, inventory_list_counts, items_desc)

    # starting the history
    logger.info("Starting the history")
    messages = [
        {
            'role': "ai_response",
            'message': lore.pop('start')
        }
    ]

    memory.add_new_turn(messages, 0)

    return lore, memory


def load_data(game_lore: Dict[str, Any], db_path: str):
    lore = dCP(game_lore)
    if not os.path.exists(db_path):
        raise Exception(f"DB does not exist: \"{db_path}\"!")

    npc_names = list(lore['npc'].keys())
    memory = GameMemorySimple(db_path, npc_names)

    expected_tables = [memory.history_tbl_name, memory.inventory_tbl_name, memory.items_tbl_name]
    for tbl in expected_tables:
        if tbl not in memory.models:
            raise ValueError(f"{tbl} does not exist in {db_path}!")

    # drop parts that will be unused
    _ = lore.pop('inventory_lut')
    _ = lore['human_player'].pop('inventory')
    _ = lore['human_player'].pop('money')
    for character in npc_names:
        _ = lore['npc'][character].pop('inventory')
        _ = lore['npc'][character].pop('money')

    return lore, memory


def init_memory_lore(lore: Dict[str, Any], db_path: str, load: bool):
    """
    Initiates or loads the session-db. It will attempt to read and load the database if load == True
    :param lore: generated lore
    :param db_path: full path to the file.
    :param load: if True, will assume this game session was active and load data, not populate as new
    :return: updated lore and the memory instance
    """
    if load:
        lore, memory = load_data(lore, db_path)
    else:
        lore, memory = populate_db(lore, db_path)

    return lore, memory


