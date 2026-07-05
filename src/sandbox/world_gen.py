from src.baml_client.async_client import b
from src.baml_client.types import WorldTypes
from src.utils.logger import setup_logging
from src.agents.world_concept_writer import WorldConceptWriter

import asyncio
from pprint import pprint
from loguru import logger

async def main():
    rules, narrative, player_card, npc_card = None, None, None, None

    world_type = WorldTypes(type="high fantasy",
                            inspiration="Political intrigues of Game of Thrones combined with epic fantasy world")

    logger.info(f"Creating a world concept for {world_type}")
    concept_writer = WorldConceptWriter(max_iteration=10)
    rules = await concept_writer.run(world_type)

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
    setup_logging(console_level="DEBUG")
    asyncio.run(main())