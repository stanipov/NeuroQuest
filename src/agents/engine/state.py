from __future__ import annotations

from datetime import UTC, datetime
from hashlib import blake2b
from operator import or_
from typing import Annotated, Literal, NotRequired, TypedDict

from langchain_core.messages import AIMessage, AnyMessage
from langgraph.graph.message import add_messages

from src.baml_client.types import (
    CharacterArrangement,
    OpeningScene,
    PlayerCharacterCard,
    StartingContext,
    WorldConcept,
    WorldNarrative,
    WorldTypes,
)

Classification = Literal["valid_action", "clarification", "invalid"]

# Key under which the lore pipeline exposes its starting context.
LORE_CONTEXT_KEY = "context"


class ActorInventory(TypedDict):
    items: list[str]
    money: int


class GameState(TypedDict):
    # Lore — set once at init, never written by nodes
    world_type: NotRequired[WorldTypes]
    world_concept: NotRequired[WorldConcept]
    world_narrative: NotRequired[WorldNarrative]
    starting_context: NotRequired[StartingContext]
    arrangement: NotRequired[CharacterArrangement]
    scene: NotRequired[OpeningScene]
    player_card: NotRequired[PlayerCharacterCard]
    npc_cards: NotRequired[list[PlayerCharacterCard]]

    # Runtime — checkpointed, mutated across turns
    messages: Annotated[list[AnyMessage], add_messages]
    npc_actions: Annotated[list[AIMessage], add_messages]
    inventories: Annotated[dict[str, ActorInventory], or_]
    physical_states: Annotated[dict[str, str], or_]
    mental_states: Annotated[dict[str, str], or_]
    current_location: NotRequired[str]
    turn_no: int

    # Turn scratch
    raw_input: str
    classification: NotRequired[Classification]
    classification_reason: NotRequired[str]
    invalid_reason: NotRequired[str]
    game_action: NotRequired[str]
    brief_answer: NotRequired[str]
    narration: NotRequired[str]


def make_npc_msg(npc_name: str, turn_no: int, content: str) -> AIMessage:
    """Build one deterministic NPC intent message.

    The ID is deterministic per (name, turn, content) so a retried node
    overwrites the existing entry via `add_messages` instead of duplicating.
    The wall-clock timestamp is metadata only and never part of the ID.
    """
    digest = blake2b(content.encode("utf-8"), digest_size=8).hexdigest()
    return AIMessage(
        content=content,
        name=npc_name,
        id=f"npc:{npc_name}:t{turn_no}:{digest}",
        additional_kwargs={
            "turn_no": turn_no,
            "ts": datetime.now(UTC).isoformat(),
        },
    )


def npc_history(
    state: GameState, npc_name: str, k: int | None = None
) -> list[AIMessage]:
    """All `npc_actions` for one NPC, oldest first, optionally windowed to `k`."""
    msgs = [m for m in state.get("npc_actions", []) if m.name == npc_name]
    msgs.sort(key=lambda m: m.additional_kwargs.get("turn_no", 0))
    return msgs if k is None else msgs[-k:]


def turn_actions(state: GameState, turn_no: int) -> list[AIMessage]:
    """All `npc_actions` for a turn, sorted by NPC name (completion order is nondeterministic)."""
    msgs = [
        m
        for m in state.get("npc_actions", [])
        if m.additional_kwargs.get("turn_no") == turn_no
    ]
    return sorted(msgs, key=lambda m: m.name or "")


def _opening_message(lore: dict) -> AIMessage | None:
    scene = lore.get("scene")
    if scene is None:
        return None
    return AIMessage(content=scene.narrative, id="opening")


def initial_state(lore: dict) -> GameState:
    """Map a `LorePipelineAgent` result dict onto a fresh `GameState`.

    `raw_input` is intentionally not set here: `classification` owns the
    per-turn `HumanMessage` append and the Engine passes `raw_input` on each
    invoke. `turn_no` starts at 0 and is bumped by `classification`.
    """
    npc_cards = [lore["npc_card"]] if lore.get("npc_card") else []

    cards = [lore.get("player_card"), *npc_cards]
    inventories: dict[str, ActorInventory] = {
        card.name: {"items": list(card.inventory), "money": card.money}
        for card in cards
        if card is not None
    }

    opening = _opening_message(lore)
    state: GameState = {
        "messages": [opening] if opening else [],
        "npc_actions": [],
        "inventories": inventories,
        "physical_states": {},
        "mental_states": {},
        "turn_no": 0,
    }

    starting_context = lore.get(LORE_CONTEXT_KEY)
    if starting_context is not None:
        state["starting_context"] = starting_context
        state["current_location"] = starting_context.location.name

    lore_fields = {
        "world_type": "world_type",
        "world_concept": "world_concept",
        "world_narrative": "world_narrative",
        "arrangement": "arrangement",
        "scene": "scene",
        "player_card": "player_card",
    }
    for src, dst in lore_fields.items():
        value = lore.get(src)
        if value is not None:
            state[dst] = value  # type: ignore[literal-required]

    if npc_cards:
        state["npc_cards"] = npc_cards

    return state
