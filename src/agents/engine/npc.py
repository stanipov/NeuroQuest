from __future__ import annotations

from langgraph.runtime import Runtime

from src.agents.engine.config import EngineConfig
from src.agents.engine.nodes import build_context
from src.agents.engine.state import GameState, make_npc_msg, npc_history
from src.baml_client.async_client import b


def _npc_history_text(state: GameState, name: str, k: int) -> str:
    return "\n".join(m.content for m in npc_history(state, name, k=k))


async def npc_act(state: GameState, runtime: Runtime[EngineConfig]) -> dict:
    """Decide the NPC's intent; write one deterministic message or nothing.

    Errors are swallowed so a failing NPC call does not fail the turn.
    """
    cfg = runtime.context
    cards = state.get("npc_cards", [])
    if not cards:
        return {}
    card = cards[0]
    turn = state.get("turn_no", 0)
    history = _npc_history_text(state, card.name, cfg.npc_window)

    try:
        intent = await b.NpcAct(
            context=build_context(state, cfg),
            npc=card,
            history=history or None,
        )
    except Exception as exc:  # noqa: BLE001 - deliberate (see docstring)
        print(f"[Engine] NPC {card.name} skipped: {exc}")
        return {}

    intent = (intent or "").strip()
    if not intent:
        print(f"[Engine] NPC {card.name} does nothing")
        return {}

    return {"npc_actions": [make_npc_msg(card.name, turn, intent)]}
