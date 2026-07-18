from typing import NotRequired, TypedDict, Literal
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
    ContextCritiqueItem,
    SceneCritiqueItem,
    StartingContextGenHistory,
    StartingSceneGenHistory,
)


class StartingPlaceState(TypedDict):
    world_type: WorldTypes
    world_concept: WorldConcept
    world_narrative: WorldNarrative
    player_card: PlayerCharacterCard
    npc_card: PlayerCharacterCard

    context: NotRequired[StartingContext]
    context_iteration: int
    context_gen_history: NotRequired[list[StartingContextGenHistory]]
    context_feedback: NotRequired[list[ContextCritiqueItem]]

    arrangement: NotRequired[CharacterArrangement]
    scene: NotRequired[OpeningScene]
    scene_iteration: int
    scene_gen_history: NotRequired[list[StartingSceneGenHistory]]
    scene_feedback: NotRequired[list[SceneCritiqueItem]]

    max_iterations: int


async def generate_context_node(state: StartingPlaceState) -> dict:
    attempt = state.get("context_iteration", 0) + 1
    print(f"[StartingPlace] Generating location context... (attempt {attempt})")
    ctx = await b.GenStartingContext(
        type=state["world_type"],
        concept=state["world_concept"],
        narrative=state["world_narrative"],
        player=state["player_card"],
        npc=state["npc_card"],
        history=state.get("context_gen_history"),
    )
    return {"context": ctx, "context_iteration": attempt}


async def critique_context_node(state: StartingPlaceState) -> dict:
    print("[StartingPlace] Critiquing location context...")
    result = await b.CritiqueStartingContext(
        concept=state["world_concept"],
        narrative=state["world_narrative"],
        context=state["context"],
    )
    if not result.is_satisfied:
        for item in result.feedback:
            print(f"  \u21b3 {item.field.value}: {item.fix}")
    history = list(state.get("context_gen_history", []))
    history.append(StartingContextGenHistory(draft=state["context"], critique=result))
    return {"context_feedback": result.feedback, "context_gen_history": history}


def route_context(state: StartingPlaceState) -> Literal["generate_context", "generate_scene"]:
    feedback = state.get("context_feedback", [])
    iteration = state.get("context_iteration", 0)
    max_iter = state.get("max_iterations", 5)

    if not feedback:
        print("[StartingPlace] Location context accepted \u2192 generating scene")
        return "generate_scene"
    if iteration >= max_iter:
        print(f"[StartingPlace] Max context iterations ({max_iter}) reached, proceeding to scene...")
        return "generate_scene"
    print(f"[StartingPlace] Revising location context ({iteration}/{max_iter})...")
    return "generate_context"


async def generate_scene_node(state: StartingPlaceState) -> dict:
    attempt = state.get("scene_iteration", 0) + 1
    print(f"[StartingPlace] Generating opening scene... (attempt {attempt})")
    output = await b.GenStartingScene(
        type=state["world_type"],
        concept=state["world_concept"],
        narrative=state["world_narrative"],
        player=state["player_card"],
        npc=state["npc_card"],
        context=state["context"],
        history=state.get("scene_gen_history"),
    )
    return {
        "arrangement": output.arrangement,
        "scene": output.scene,
        "scene_iteration": attempt,
    }


async def critique_scene_node(state: StartingPlaceState) -> dict:
    print("[StartingPlace] Critiquing opening scene...")
    result = await b.CritiqueStartingScene(
        concept=state["world_concept"],
        narrative=state["world_narrative"],
        player=state["player_card"],
        npc=state["npc_card"],
        context=state["context"],
        arrangement=state["arrangement"],
        scene=state["scene"],
    )
    if not result.is_satisfied:
        for item in result.feedback:
            print(f"  \u21b3 {item.field.value}: {item.fix}")
    history = list(state.get("scene_gen_history", []))
    history.append(
        StartingSceneGenHistory(
            arrangement=state["arrangement"],
            scene=state["scene"],
            critique=result,
        )
    )
    return {"scene_feedback": result.feedback, "scene_gen_history": history}


def route_scene(state: StartingPlaceState) -> Literal["generate_scene", "finalize"]:
    feedback = state.get("scene_feedback", [])
    iteration = state.get("scene_iteration", 0)
    max_iter = state.get("max_iterations", 5)

    if not feedback:
        print("[StartingPlace] Scene accepted \u2192 finalizing")
        return "finalize"
    if iteration >= max_iter:
        print(f"[StartingPlace] Max scene iterations ({max_iter}) reached, finalizing...")
        return "finalize"
    print(f"[StartingPlace] Revising scene ({iteration}/{max_iter})...")
    return "generate_scene"


async def finalize_node(state: StartingPlaceState) -> dict:
    print("[StartingPlace] Done!")
    return {
        "context": state.get("context"),
        "arrangement": state.get("arrangement"),
        "scene": state.get("scene"),
    }


class StartingPlaceAgent:
    def __init__(self, max_iterations: int = 5):
        self.max_iterations = max_iterations
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        graph = StateGraph(StartingPlaceState)

        graph.add_node("generate_context", generate_context_node)
        graph.add_node("critique_context", critique_context_node)
        graph.add_node("generate_scene", generate_scene_node)
        graph.add_node("critique_scene", critique_scene_node)
        graph.add_node("finalize", finalize_node)

        graph.set_entry_point("generate_context")
        graph.add_edge("generate_context", "critique_context")
        graph.add_conditional_edges("critique_context", route_context)
        graph.add_edge("generate_scene", "critique_scene")
        graph.add_conditional_edges("critique_scene", route_scene)

        return graph.compile()

    async def astream(self, inputs: dict):
        async for event in self.graph.astream(inputs, stream_mode="v2"):
            yield event
