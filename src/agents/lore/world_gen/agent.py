from typing import NotRequired, TypedDict, Literal
from langgraph.graph import StateGraph

from src.baml_client.async_client import b
from src.baml_client.types import (
    WorldTypes,
    WorldConcept,
    WorldNarrative,
    WorldConceptGenHistory,
    WorldConceptInconsistency,
    WorldNarrativeGenHistory,
    WorldNarrativeInconsistency,
)
from src.agents.lore.pipeline.config import WorldGenConfig


class WorldGenState(TypedDict):
    world_type: WorldTypes

    world_concept: NotRequired[WorldConcept]
    concept_iteration: int
    concept_gen_history: NotRequired[list[WorldConceptGenHistory]]
    concept_feedback: NotRequired[list[WorldConceptInconsistency]]

    world_narrative: NotRequired[WorldNarrative]
    narrative_iteration: int
    narrative_gen_history: NotRequired[list[WorldNarrativeGenHistory]]
    narrative_feedback: NotRequired[list[WorldNarrativeInconsistency]]


async def generate_concept_node(state: WorldGenState) -> dict:
    attempt = state.get("concept_iteration", 0) + 1
    print(f"[WorldGen] Generating world concept... (attempt {attempt})")
    result = await b.GenWorldConcept(
        type=state["world_type"],
        history=state.get("concept_gen_history"),
    )
    return {"world_concept": result, "concept_iteration": attempt}


async def critique_concept_node(state: WorldGenState) -> dict:
    print("[WorldGen] Critiquing world concept...")
    result = await b.WorldConceptCritique(
        type=state["world_type"],
        concept=state["world_concept"],
        history=state.get("concept_gen_history"),
    )
    if not result.is_satisfied:
        for item in result.feedback:
            print(f"  \u21b3 {item.world_concept}: {item.fix}")
    history = list(state.get("concept_gen_history", []))
    history.append(WorldConceptGenHistory(draft=state["world_concept"], critique=result))
    return {"concept_feedback": result.feedback, "concept_gen_history": history}


async def generate_narrative_node(state: WorldGenState) -> dict:
    attempt = state.get("narrative_iteration", 0) + 1
    print(f"[WorldGen] Generating world narrative... (attempt {attempt})")
    result = await b.NarrateWorld(
        world_type=state["world_type"],
        concept=state["world_concept"],
        history=state.get("narrative_gen_history"),
    )
    return {"world_narrative": result, "narrative_iteration": attempt}


async def critique_narrative_node(state: WorldGenState) -> dict:
    print("[WorldGen] Critiquing world narrative...")
    result = await b.NarrateWorldCritique(
        concept=state["world_concept"],
        narrative=state["world_narrative"],
        history=state.get("narrative_gen_history"),
    )
    if not result.is_satisfied:
        for item in result.feedback:
            print(f"  \u21b3 {item.field}: {item.fix}")
    history = list(state.get("narrative_gen_history", []))
    history.append(WorldNarrativeGenHistory(draft=state["world_narrative"], critique=result))
    return {"narrative_feedback": result.feedback, "narrative_gen_history": history}


async def finalize_node(state: WorldGenState) -> dict:
    print("[WorldGen] Done!")
    return {
        "world_concept": state.get("world_concept"),
        "world_narrative": state.get("world_narrative"),
    }


class WorldGenAgent:
    def __init__(self, config: WorldGenConfig | None = None):
        cfg = config or WorldGenConfig()
        self.concept_max = cfg.concept.max_iterations
        self.narrative_max = cfg.narrative.max_iterations
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        concept_max = self.concept_max
        narrative_max = self.narrative_max

        def route_concept(state: WorldGenState) -> Literal["generate_concept", "generate_narrative"]:
            feedback = state.get("concept_feedback", [])
            iteration = state.get("concept_iteration", 0)
            if not feedback:
                print("[WorldGen] Concept accepted \u2192 generating narrative")
                return "generate_narrative"
            if iteration >= concept_max:
                print(f"[WorldGen] Max concept iterations ({concept_max}) reached, proceeding...")
                return "generate_narrative"
            print(f"[WorldGen] Revising concept ({iteration}/{concept_max})...")
            return "generate_concept"

        def route_narrative(state: WorldGenState) -> Literal["generate_narrative", "finalize"]:
            feedback = state.get("narrative_feedback", [])
            iteration = state.get("narrative_iteration", 0)
            if not feedback:
                print("[WorldGen] Narrative accepted \u2192 finalizing")
                return "finalize"
            if iteration >= narrative_max:
                print(f"[WorldGen] Max narrative iterations ({narrative_max}) reached, finalizing...")
                return "finalize"
            print(f"[WorldGen] Revising narrative ({iteration}/{narrative_max})...")
            return "generate_narrative"

        graph = StateGraph(WorldGenState)
        graph.add_node("generate_concept", generate_concept_node)
        graph.add_node("critique_concept", critique_concept_node)
        graph.add_node("generate_narrative", generate_narrative_node)
        graph.add_node("critique_narrative", critique_narrative_node)
        graph.add_node("finalize", finalize_node)

        graph.set_entry_point("generate_concept")
        graph.add_edge("generate_concept", "critique_concept")
        graph.add_conditional_edges("critique_concept", route_concept)
        graph.add_edge("generate_narrative", "critique_narrative")
        graph.add_conditional_edges("critique_narrative", route_narrative)

        return graph.compile()

    async def astream(self, inputs: dict):
        async for event in self.graph.astream(inputs, stream_mode="v2"):
            yield event
