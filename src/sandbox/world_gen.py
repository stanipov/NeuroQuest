from src.baml_client.async_client import b
from src.baml_client.types import *

import asyncio


async def main():

    world_type = WorldTypes(type="post-apocalyptic",
                            inspiration="Biological nanotech plague reshaped reality 200 years ago - now forests grow metal, rivers flow with data, and mutations are currency")

    rules = await b.GenWorldRules(world_type)
    narrative = await b.NarrateWorld(rules)
    player_card = await b.GenPlayerCard(world_type, rules, narrative)

    results = [rules, narrative, player_card]
    for item in results:
        print(f"{'='*25}")
        print(item.model_dump())


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()

    asyncio.run(main())