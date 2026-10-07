from __future__ import annotations

from typing import Literal

from langchain_core.messages import AIMessage, AnyMessage, HumanMessage
from langgraph.config import get_stream_writer
from langgraph.types import Send

from src.agents.engine.config import EngineConfig
from src.agents.engine.state import GameState, turn_actions
from src.baml_client.async_client import b
from src.baml_client.types import InputDecision, InventoryDelta, StateDelta

Classification = Literal["valid_action", "clarification", "invalid"]

_DECISION_MAP: dict[InputDecision, Classification] = {
    InputDecision.ValidAction: "valid_action",
    InputDecision.Clarification: "clarification",
    InputDecision.Invalid: "invalid",
}


# ---------------------------------------------------------------------------
# Prompt context
# ---------------------------------------------------------------------------


def _role_label(msg: AnyMessage) -> str:
    role = getattr(msg, "type", "message")
    if role == "human":
        return "player"
    if role == "ai":
        return msg.name or "narrator"
    return role


def _world_section(state: GameState) -> list[str]:
    lines: list[str] = []
    narrative = state.get("world_narrative")
    if narrative is not None:
        lines.append(f"World: {narrative.name}")
        if narrative.current_state:
            lines.append(f"Current state: {narrative.current_state}")
    concept = state.get("world_concept")
    if concept is not None:
        for label, rules in (
            ("Magic", concept.magic),
            ("Physics", concept.physics),
            ("Society", concept.society),
            ("Geography", concept.geography),
            ("Technology", concept.technology),
        ):
            if rules:
                lines.append(f"{label}: " + "; ".join(rules))
    return lines


def _place_section(state: GameState) -> list[str]:
    lines: list[str] = []
    ctx = state.get("starting_context")
    if ctx is not None:
        lines.append(f"Region: {ctx.region_name} — {ctx.region_description}")
        lines.append(
            f"Settlement: {ctx.settlement.name} ({ctx.settlement.type}) — "
            f"{ctx.settlement.description}"
        )
        lines.append(
            f"Location: {ctx.location.name} ({ctx.location.type}) — "
            f"{ctx.location.description}. Atmosphere: {ctx.location.atmosphere}"
        )
    current = state.get("current_location")
    if current:
        lines.append(f"Current location: {current}")
    return lines


def _actor_line(name: str, card) -> str:
    return (
        f"{name}: {card.gender.value} {card.occupation}, age {card.age}. "
        f"{card.biography} Physical: {card.physical} Wisdom: {card.wisdom} "
        f"Strengths: {card.strengths} Weaknesses: {card.weaknesses}"
    )


def _actors_section(state: GameState) -> list[str]:
    lines: list[str] = []
    player = state.get("player_card")
    if player is not None:
        lines.append(_actor_line("Player", player))
    for card in state.get("npc_cards", []):
        lines.append(_actor_line(f"NPC {card.name}", card))
    return lines


def _runtime_section(state: GameState) -> list[str]:
    lines: list[str] = []
    for name, inv in state.get("inventories", {}).items():
        items = ", ".join(inv.get("items", [])) or "nothing"
        lines.append(f"{name} inventory: {items} ({inv.get('money', 0)} coins)")
    for name, value in state.get("physical_states", {}).items():
        lines.append(f"{name} physical state: {value}")
    for name, value in state.get("mental_states", {}).items():
        lines.append(f"{name} mental state: {value}")
    return lines


def _history_section(state: GameState, window: int) -> list[str]:
    messages = state.get("messages", [])
    recent = messages[-window:] if window > 0 else []
    return [f"{_role_label(m)}: {m.content}" for m in recent]


def build_context(state: GameState, cfg: EngineConfig) -> str:
    """Serialize lore, runtime, and recent history into one prompt string.

    Every lore/runtime channel is `NotRequired`, so the helper tolerates an
    almost-empty state (e.g. `initial_state({})`).
    """
    sections = [
        _world_section(state),
        _place_section(state),
        _actors_section(state),
        _runtime_section(state),
        _history_section(state, cfg.history_window),
    ]
    return "\n".join(line for section in sections for line in section)


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------


async def classification(state: GameState, cfg: EngineConfig) -> dict:
    """Classify the player's input, bump the turn, and append the input message.

    `turn_no` is bumped exactly once per turn and the `HumanMessage` id is
    deterministic per turn, so a retried node overwrites instead of duplicating
    via `add_messages`.
    """
    print(f"[Engine] Classifying input: {state['raw_input']!r}")
    result = await b.ClassifyInput(
        context=build_context(state, cfg),
        input=state["raw_input"],
    )
    turn = state.get("turn_no", 0) + 1
    decision = _DECISION_MAP[result.decision]
    print(f"[Engine] Decision: {decision} — {result.reason}")
    return {
        "turn_no": turn,
        "classification": decision,
        "classification_reason": result.reason,
        "invalid_reason": result.invalid_reason,
        "messages": [
            HumanMessage(content=state["raw_input"], id=f"user:t{turn}")
        ],
    }


def route_classification(
    state: GameState,
) -> Literal["game_response", "brief", "narration"] | list[Send]:
    decision = state.get("classification")
    if decision == "clarification":
        return "brief"
    if decision == "invalid":
        return "narration"
    # valid_action: fan out one NPC task per card, or skip straight to the game
    # stage. Never return [] - an empty destination list ends the graph.
    cards = state.get("npc_cards", [])
    if not cards:
        return "game_response"
    return [Send("npc", {**state, "my_card": card}) for card in cards]


def _known_actors(state: GameState) -> set[str]:
    """Every valid actor name (player + NPC cards), for delta validation."""
    names: set[str] = set()
    player = state.get("player_card")
    if player is not None:
        names.add(player.name)
    names.update(card.name for card in state.get("npc_cards", []))
    return names


def _apply_inventory_deltas(
    state: GameState, deltas: list[InventoryDelta]
) -> dict:
    """Return complete per-actor `ActorInventory` dicts (or `{}`).

    `inventories` uses `or_`, which merges per actor key, so each returned entry
    must be the actor's *complete* inventory, not a partial delta.
    """
    current = state.get("inventories", {})
    known = _known_actors(state)
    updates: dict[str, dict] = {}
    for delta in deltas:
        if delta.actor not in known:
            print(
                f"[Engine] inventory delta for unknown actor {delta.actor!r}; ignored"
            )
            continue
        base = updates.get(delta.actor) or dict(
            current.get(delta.actor, {"items": [], "money": 0})
        )
        removed = set(delta.items_removed)
        items = [item for item in base["items"] if item not in removed]
        for item in delta.items_added:
            if item not in items:
                items.append(item)
        updates[delta.actor] = {
            "items": items,
            "money": base["money"] + delta.money_delta,
        }
    return {"inventories": updates} if updates else {}


def _apply_state_deltas(state: GameState, deltas: list[StateDelta]) -> dict:
    """Return `physical_states`/`mental_states` partials and the player's
    `current_location` when a delta changes it."""
    known = _known_actors(state)
    player = state.get("player_card")
    player_name = player.name if player is not None else None

    out: dict = {}
    physical: dict[str, str] = {}
    mental: dict[str, str] = {}
    location: str | None = None

    for delta in deltas:
        if delta.actor not in known:
            print(f"[Engine] state delta for unknown actor {delta.actor!r}; ignored")
            continue
        if delta.physical is not None:
            physical[delta.actor] = delta.physical
        if delta.mental is not None:
            mental[delta.actor] = delta.mental
        if delta.location is not None and delta.actor == player_name:
            location = delta.location

    if physical:
        out["physical_states"] = physical
    if mental:
        out["mental_states"] = mental
    if location is not None:
        out["current_location"] = location
    return out


async def game_response(state: GameState, cfg: EngineConfig) -> dict:
    """Sole authority over runtime: inventory, states, and the player's location."""
    print(f"[Engine] Resolving game turn {state.get('turn_no', 0)}")
    result = await b.ResolveGame(
        context=build_context(state, cfg),
        input=state["raw_input"],
        intents=_intents_text(state, state.get("turn_no", 0)),
    )
    update: dict = {"game_action": result.terse}
    update.update(_apply_inventory_deltas(state, result.inventory_deltas))
    update.update(_apply_state_deltas(state, result.state_deltas))
    return update


async def brief(state: GameState, cfg: EngineConfig) -> dict:
    """Answer a clarification question in 1-3 sentences (no narration)."""
    print(f"[Engine] Answering clarification for turn {state.get('turn_no', 0)}")
    answer = await b.AnswerBrief(
        context=build_context(state, cfg),
        question=state["raw_input"],
    )
    return {"brief_answer": answer}


def _intents_text(state: GameState, turn_no: int) -> str:
    return "\n".join(
        f"{msg.name}: {msg.content}" for msg in turn_actions(state, turn_no)
    )


def _narration_events(state: GameState, mode: Classification) -> str:
    if mode == "clarification":
        return state.get("brief_answer", "")
    if mode == "invalid":
        return state.get("invalid_reason") or state.get("classification_reason", "")
    # valid: game summary + this turn's NPC intents
    parts = [state.get("game_action", ""), _intents_text(state, state.get("turn_no", 0))]
    return "\n".join(part for part in parts if part)


async def narration(state: GameState, cfg: EngineConfig) -> dict:
    """Render the final turn output and stream it as it is generated.

    Narration is the only streaming point: incremental text is emitted through
    `get_stream_writer()` as `{"narration_token": <suffix>}` custom chunks, while
    the node writes the full text and a deterministic `AIMessage` to the state.
    """
    mode = state.get("classification", "invalid")
    turn = state.get("turn_no", 0)
    events = _narration_events(state, mode)
    print(f"[Engine] Narrating turn {turn} (mode={mode})")

    writer = get_stream_writer()
    stream = b.stream.NarrateTurn(
        context=build_context(state, cfg),
        events=events,
        mode=mode,
    )

    emitted = ""
    async for partial in stream:
        text = partial if isinstance(partial, str) else ""
        if text.startswith(emitted):
            delta = text[len(emitted):]
        else:  # non-monotonic partial: fall back to a full snapshot
            delta = text
        if delta:
            writer({"narration_token": delta})
        emitted = text

    final = await stream.get_final_response()
    if final.startswith(emitted) and len(final) > len(emitted):
        writer({"narration_token": final[len(emitted):]})

    return {
        "narration": final,
        "messages": [
            AIMessage(content=final, name="narrator", id=f"narrator:t{turn}")
        ],
    }
