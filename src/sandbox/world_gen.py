from src.baml_client.types import WorldTypes
from src.utils.logger import setup_logging
from src.agents.lore.pipeline import LorePipelineAgent

import asyncio
from pprint import pprint
from loguru import logger


async def main():
    world_type = WorldTypes(
        type="high fantasy",
        inspiration="Political intrigues of Game of Thrones combined with epic fantasy world",
    )

    agent = LorePipelineAgent.from_json("configs/lore_pipeline.json")
    result = await agent.graph.ainvoke(
        {
            "world_type": world_type,
            "concept_iteration": 0,
            "narrative_iteration": 0,
            "context_iteration": 0,
            "scene_iteration": 0,
        }
    )

    print(f"\n{'='*60}")
    print("FINAL RESULTS")
    print(f"{'='*60}")

    labels = ["World Concept", "World Narrative", "Player Card", "NPC Card"]
    items = [
        result.get("world_concept"),
        result.get("world_narrative"),
        result.get("player_card"),
        result.get("npc_card"),
    ]
    for label, item in zip(labels, items):
        if item:
            print(f"\n{label}:")
            pprint(item.model_dump())

    print("\n\nSTARTING PLACE:")
    print(f"\n--- Region ---")
    context = result.get("context")
    if context:
        pprint(context.region_name)
        pprint(context.region_description)
        print(f"\n--- Settlement ---")
        pprint(context.settlement.model_dump())
        print(f"\n--- Location ---")
        pprint(context.location.model_dump())
    print(f"\n--- Character Arrangement ---")
    arrangement = result.get("arrangement")
    if arrangement:
        pprint(arrangement.model_dump())
    print(f"\n--- Opening Scene ---")
    scene = result.get("scene")
    if scene:
        pprint(scene.model_dump())


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()
    setup_logging(console_level="DEBUG")
    asyncio.run(main())
