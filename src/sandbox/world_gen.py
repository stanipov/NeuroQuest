from src.baml_client.async_client import b
from src.baml_client.types import *
from src.utils.logger import setup_logging

import asyncio
from pprint import pprint
from loguru import logger

async def main():
    rules, narrative, player_card, npc_card = None, None, None, None

    # world_type = WorldTypes(type="dystopian dark fantasy",
    #                         inspiration="Orwell's 1984 totalitarianism meets brutality of Game of Thrones and \
    #                         horrors of cosmic dread, where ancient curses and forgotten gods twist \
    #                         the natural order")

    world_type = WorldTypes(type="high fantasy",
                            inspiration="Political intrigues of Game of Thrones combined with epic fantasy world")

    logger.info(f"Creating a world rules for {world_type}")
    rules = await b.GenWorldRules(world_type)

    logger.info(f"Creating the narrative")
    narrative = await b.NarrateWorld(world_type, rules)

    # logger.info("Creating the player's card")
    # player_card = await b.GenPlayerCard(world_type, rules, narrative)
    #
    # logger.info("Creating the NPC card")
    # npc_card = await b.GenNPCCard(world_type, rules, narrative, player_card)

    results = [rules, narrative, player_card, npc_card]
    for item in results:
        if item:
            print(f"{'='*25}")
            pprint(item.model_dump())


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()
    setup_logging()
    asyncio.run(main())