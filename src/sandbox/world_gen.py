from src.baml_client.async_client import b
from src.baml_client.types import WorldTypes
from src.utils.logger import setup_logging
from src.agents.world_concept_writer import WorldConceptWriter
from src.agents.world_narrative_writer import WorldNarrativeWriter
from src.agents.lore.start_loc import StartingPlaceAgent

import asyncio
from pprint import pprint
from loguru import logger


async def main():
    rules, narrative, player_card, npc_card = None, None, None, None

    world_type = WorldTypes(
        type="high fantasy",
        inspiration="Political intrigues of Game of Thrones combined with epic fantasy world",
    )

    logger.info(f"Creating a world concept for {world_type}")
    concept_writer = WorldConceptWriter(max_iteration=10)
    rules = await concept_writer.run(world_type)

    logger.info("Creating the narrative")
    narrative_writer = WorldNarrativeWriter(max_iteration=10)
    narrative = await narrative_writer.run(world_type, rules)

    logger.info("Creating the player's card")
    player_card = await b.GenPlayerCard(world_type, rules, narrative)

    logger.info("Creating the NPC card")
    npc_card = await b.GenNPCCard(world_type, rules, narrative, player_card)

    logger.info("Generating the starting place")
    agent = StartingPlaceAgent(max_iterations=5)
    result = await agent.graph.ainvoke(
        {
            "world_type": world_type,
            "world_concept": rules,
            "world_narrative": narrative,
            "player_card": player_card,
            "npc_card": npc_card,
            "context_iteration": 0,
            "scene_iteration": 0,
            "max_iterations": 5,
        }
    )
    
    print(f"\n{'='*60}")
    print("FINAL RESULTS")
    print(f"{'='*60}")

    items = [rules, narrative, player_card, npc_card]
    labels = ["World Concept", "World Narrative", "Player Card", "NPC Card"]
    for label, item in zip(labels, items):
        if item:
            print(f"\n{label}:")
            pprint(item.model_dump())

    print("\n\nSTARTING PLACE:")
    print(f"\n--- Region ---")
    pprint(result["context"].region_name)
    pprint(result["context"].region_description)
    print(f"\n--- Settlement ---")
    pprint(result["context"].settlement.model_dump())
    print(f"\n--- Location ---")
    pprint(result["context"].location.model_dump())
    print(f"\n--- Character Arrangement ---")
    pprint(result["arrangement"].model_dump())
    print(f"\n--- Opening Scene ---")
    pprint(result["scene"].model_dump())


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()
    setup_logging(console_level="DEBUG")
    asyncio.run(main())
