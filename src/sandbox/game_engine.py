from __future__ import annotations

import asyncio
import json
from pathlib import Path

from src.agents.engine import Engine, EngineConfig
from src.baml_client.types import (
    CharacterArrangement,
    OpeningScene,
    PlayerCharacterCard,
    StartingContext,
    WorldConcept,
    WorldNarrative,
    WorldTypes,
)
from src.utils.logger import setup_logging

LORE_PATH = "tmp/lore/2026-08-26_22-28_qJ0o.json"

RAW_TO_MODEL = {
    "world_type": WorldTypes,
    "world_concept": WorldConcept,
    "world_narrative": WorldNarrative,
    "player_card": PlayerCharacterCard,
    "npc_card": PlayerCharacterCard,
    "context": StartingContext,
    "arrangement": CharacterArrangement,
    "scene": OpeningScene,
}


def load_lore(path: str = LORE_PATH) -> dict:
    """Read the saved pipeline output and rebuild the BAML objects initial_state expects."""
    data = json.loads(Path(path).read_text())
    return {
        key: model.model_validate(data[key])
        for key, model in RAW_TO_MODEL.items()
        if data.get(key) is not None
    }


async def main() -> None:
    cfg = EngineConfig.from_json("configs/engine.json")
    lore = load_lore()

    async with Engine(cfg) as engine:
        thread_id = await engine.new_game(lore)

        scene = lore.get("scene")
        if scene is not None:
            print(f"\n{scene.narrative}\n")

        while True:
            try:
                raw_input = input("> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if raw_input.lower() in {"quit", "exit"}:
                break
            if not raw_input:
                continue

            print()
            mode = ""
            async for event in engine.stream_turn(thread_id, raw_input):
                if event["type"] == "updates":
                    update = event["data"]
                    if "classification" in update:
                        mode = update["classification"].get("classification", mode)
                elif event["type"] == "custom":
                    print(event["data"]["narration_token"], end="", flush=True)
            print(f"\n[{mode}]\n")

        state = (await engine.state(thread_id)).values
        print(f"[turn {state.get('turn_no', 0)}]")


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()
    setup_logging()
    asyncio.run(main())
