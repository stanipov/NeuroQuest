from __future__ import annotations

from src.agents.engine.config import EngineConfig
from src.agents.engine.nodes import build_context
from src.agents.engine.state import GameState, make_npc_msg, npc_history
from src.baml_client.async_client import b
from src.baml_client.types import PlayerCharacterCard


class NpcInput(GameState):
    """A full-state `Send` payload plus the identity of the acting NPC.

    `my_card` is not a graph channel; it travels only in the `Send` payload and
    is never written back to the parent state.
    """

    my_card: PlayerCharacterCard


def _npc_history_text(state: NpcInput, name: str, k: int) -> str:
    return "\n".join(m.content for m in npc_history(state, name, k=k))


async def npc_act(state: NpcInput, cfg: EngineConfig) -> dict:
    """Decide one NPC's intent; write one deterministic message or nothing.

    Errors are swallowed: a raised exception in a parallel superstep would fail
    every branch and discard the whole step's updates.
    """
    card = state["my_card"]
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
