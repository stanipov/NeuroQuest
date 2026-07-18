from typing import NotRequired, TypedDict
from langgraph.graph import StateGraph

from src.baml_client.async_client import b
from src.baml_client.types import (
    WorldTypes,
    WorldConcept,
    WorldNarrative,
    PlayerCharacterCard,
    StartingContext,
    CharacterArrangement,
    OpeningScene,
    WorldConceptGenHistory,
    WorldConceptInconsistency,
    WorldNarrativeGenHistory,
    WorldNarrativeInconsistency,
    ContextCritiqueItem,
    SceneCritiqueItem,
    StartingContextGenHistory,
    StartingSceneGenHistory,
)
from src.agents.lore.world_gen import WorldGenAgent
from src.agents.lore.start_loc import StartingPlaceAgent
from .config import LorePipelineConfig

from pathlib import Path
import json


class LorePipelineState(TypedDict):
    world_type: WorldTypes

    world_concept: NotRequired[WorldConcept]
    concept_iteration: int
    concept_gen_history: NotRequired[list[WorldConceptGenHistory]]
    concept_feedback: NotRequired[list[WorldConceptInconsistency]]

    world_narrative: NotRequired[WorldNarrative]
    narrative_iteration: int
    narrative_gen_history: NotRequired[list[WorldNarrativeGenHistory]]
    narrative_feedback: NotRequired[list[WorldNarrativeInconsistency]]

    player_card: NotRequired[PlayerCharacterCard]
    npc_card: NotRequired[PlayerCharacterCard]

    context: NotRequired[StartingContext]
    context_iteration: int
    context_gen_history: NotRequired[list[StartingContextGenHistory]]
    context_feedback: NotRequired[list[ContextCritiqueItem]]

    arrangement: NotRequired[CharacterArrangement]
    scene: NotRequired[OpeningScene]
    scene_iteration: int
    scene_gen_history: NotRequired[list[StartingSceneGenHistory]]
    scene_feedback: NotRequired[list[SceneCritiqueItem]]


async def gen_player_card_node(state: LorePipelineState) -> dict:
    print("[Pipeline] Generating player character card...")
    card = await b.GenPlayerCard(
        type=state["world_type"],
        concept=state["world_concept"],
        narrative=state["world_narrative"],
    )
    return {"player_card": card}


async def gen_npc_card_node(state: LorePipelineState) -> dict:
    print("[Pipeline] Generating NPC companion card...")
    card = await b.GenNPCCard(
        type=state["world_type"],
        concept=state["world_concept"],
        narrative=state["world_narrative"],
        player=state["player_card"],
    )
    return {"npc_card": card}


async def finalize_node(state: LorePipelineState) -> dict:
    print("[Pipeline] Lore pipeline complete!")
    return {
        "world_concept": state.get("world_concept"),
        "world_narrative": state.get("world_narrative"),
        "player_card": state.get("player_card"),
        "npc_card": state.get("npc_card"),
        "context": state.get("context"),
        "arrangement": state.get("arrangement"),
        "scene": state.get("scene"),
    }


class LorePipelineAgent:
    def __init__(self, config: LorePipelineConfig | None = None):
        self.config = config or LorePipelineConfig()
        self.world_gen_subgraph = WorldGenAgent(self.config.world_gen).graph
        self.start_place_subgraph = StartingPlaceAgent(
            context_max_iterations=self.config.starting_place.context.max_iterations,
            scene_max_iterations=self.config.starting_place.scene.max_iterations,
        ).graph
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        graph = StateGraph(LorePipelineState)
        graph.add_node("world_gen", self.world_gen_subgraph)
        graph.add_node("gen_player_card", gen_player_card_node)
        graph.add_node("gen_npc_card", gen_npc_card_node)
        graph.add_node("starting_place", self.start_place_subgraph)
        graph.add_node("finalize", finalize_node)

        graph.set_entry_point("world_gen")
        graph.add_edge("world_gen", "gen_player_card")
        graph.add_edge("gen_player_card", "gen_npc_card")
        graph.add_edge("gen_npc_card", "starting_place")
        graph.add_edge("starting_place", "finalize")

        return graph.compile()

    @classmethod
    def from_json(cls, path: str = "configs/lore_pipeline.json") -> LorePipelineAgent:
        config_path = Path(path)
        if config_path.exists():
            data = json.loads(config_path.read_text())
            return cls(LorePipelineConfig(**data))
        return cls()

    async def astream(self, inputs: dict):
        async for event in self.graph.astream(inputs, stream_mode="v2"):
            yield event
