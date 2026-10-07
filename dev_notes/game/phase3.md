# Game Engine — Phase 3 Implementation Plan

Status: ready to implement.
Parent specs:
- `dev_notes/game/2026-09-16-game-engine-architecture.md` (v1.2)
- `dev_notes/game/2026-09-17-game-engine-implementation-plan.md` (v1.2)
- `dev_notes/game/phase1.md` (Phase 1, complete)
- `dev_notes/game/phase2.md` (Phase 2, complete)

This document is authoritative for Phase 3 where the specs above disagree.
Environment: Python 3.14.7, `langgraph 1.2.9`, `baml-py 0.222.0`,
`langgraph-checkpoint-sqlite 3.1.1`, `aiosqlite 0.22.1`, `pytest 9.1.1`.
Baseline verified on `dev/v2`: `uv run pytest -q` → **25 passed**.

## 0. Scope

Replace the two Phase 2 stubs and insert the NPC fan-out, keeping every node
name and edge from Phase 2 fixed:

1. `src/agents/engine/npc.py` — `NpcInput`, `npc_act`.
2. `src/agents/engine/nodes.py` — real `game_response` (delta application) and
   real `brief`; `route_classification` gains the `Send` fan-out; delta helpers.
3. `src/agents/engine/graph.py` — add the `npc` node + `npc → game_response`
   barrier edge; extend `NodeFns`; wire `max_concurrency`.
4. `src/agents/engine/__init__.py` — export the new symbols.
5. `tests/test_engine_npc.py` — deterministic, network-free.
6. Doc housekeeping: record Phase 3 in the v1.2 arch/plan docs (v1.3 note).

Explicitly out of scope for Phase 3:
- Phase 4 persisted-thread smoke, resume-after-restart, retry idempotency.
- Phase 5 game-stage split (inventory / states / location / summary nodes).
- N-NPC *generation* in the lore pipeline, TUI/`rich`, eval harness,
  checkpoint retention/pruning.

## 1. Locked decisions

Carried from Phase 1/2 (do not revisit):

- **D1** NPC fan-out is a plain node with a full-state `Send` payload, not a
  shared-state subgraph. No `NpcSubgraphState`.
- **D2** `classification` owns the per-turn input: it bumps `turn_no` **and**
  appends `HumanMessage(id=f"user:t{turn}")`. `initial_state(lore)` does not take
  `raw_input`.
- **D3** Deterministic NPC message IDs (`make_npc_msg`); timestamp in
  `additional_kwargs` only.
- **D4** `AsyncSqliteSaver(conn, serde=build_serde())` over an engine-owned
  `aiosqlite.connect(path)`.
- **P2.1** Node names and edges stay fixed; Phase 3 replaces node bodies only.
- **P2.2** `Engine.new_game(lore)` seeds via `aupdate_state(..., as_node=START)`;
  `turn`/`stream_turn` send only `{"raw_input": ...}`.
- **P2.4** Narration is the only streaming point (`get_stream_writer()`).

Chosen with the user for Phase 3:

- **P3.1 — Single NPC.** `initial_state` is unchanged: `lore["npc_card"]` maps to
  `npc_cards[0]`. No `npc_cards` list support in `initial_state`; the lore
  pipeline still generates one NPC. The fan-out router still iterates the
  generic `state["npc_cards"]` list, so the mechanism is correct and
  future-proof, but production turns run one NPC. N>1 fan-out is exercised by
  unit tests that build a two-card state directly.
- **P3.2 — Location is player-only.** A `StateDelta.location` updates
  `current_location` only when `delta.actor == player_card.name`. NPC location
  deltas are ignored (the channel tracks the player's scene).
- **P3.3 — Failure policy.** `npc_act` catches exceptions internally and writes
  nothing (the parallel superstep is transactional — one failure must not fail
  the step). `game_response`, `brief`, and `narration` errors propagate and fail
  the turn.
- **P3.4 — No live smoke in Phase 3.** All Phase 3 tests are deterministic and
  network-free with a stubbed `b`. The live LLM smoke and the conditional
  `{{ ctx.output_format }}` decision move to Phase 4.

## 2. Topology (final Phase 3)

```
START → classification ─┬─ valid ─ Send("npc", {**state,"my_card":card}) ×N ─→ npc ─┐
                         │        (0 NPCs) ───────────────────────────────────────→ game_response → narration → END
                         ├─ clarification → brief → narration → END
                         └─ invalid       → narration → END
```

- `npc → game_response` is the barrier: `game_response` runs once, after every
  NPC task in the superstep completes.
- `game_response` is a valid-path-only node; its name and its inbound/outbound
  edges are the same identifiers Phase 2 used. Only its inbound source moves
  from `classification` to `npc` (with `classification → game_response` retained
  for the zero-NPC case).
- Empty fan-out must **never** return `[]`: Phase 1 found that a router returning
  an empty list silently ends the graph instead of advancing downstream.

## 3. `src/agents/engine/npc.py` (new)

```python
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
    lines = [m.content for m in npc_history(state, name, k=k)]
    return "\n".join(lines)


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
    except Exception as exc:  # noqa: BLE001 — deliberate per P3.3
        print(f"[Engine] NPC {card.name} skipped: {exc}")
        return {}

    intent = (intent or "").strip()
    if not intent:
        print(f"[Engine] NPC {card.name} does nothing")
        return {}

    return {"npc_actions": [make_npc_msg(card.name, turn, intent)]}
```

Notes:
- The node writes **only** the reducer-backed `npc_actions` channel. Writing any
  last-value channel here would collide across parallel branches.
- A no-op NPC writes nothing (no empty-content message in the checkpoint).
- `NpcInput` subclasses `GameState` (a `TypedDict`), so it keeps every channel
  annotation and adds `my_card`.

## 4. `src/agents/engine/nodes.py` changes

### 4.1 Imports

Add:

```python
from langgraph.types import Send

from src.baml_client.types import GameResolve, InventoryDelta, StateDelta
```

(`GameResolve`/`InventoryDelta`/`StateDelta` are for type hints only.)

### 4.2 `route_classification` — fan-out on the valid branch

```python
def route_classification(
    state: GameState,
) -> Literal["game_response", "brief", "narration"] | list[Send]:
    decision = state.get("classification")
    if decision == "clarification":
        return "brief"
    if decision == "invalid":
        return "narration"
    # valid_action
    cards = state.get("npc_cards", [])
    if not cards:
        return "game_response"  # never return [] — that ends the graph
    return [Send("npc", {**state, "my_card": card}) for card in cards]
```

- Full-state payload (D1): `Send` to a plain node replaces the node input with
  the payload, so the payload must contain every channel the node reads.
- Returning a mixed `str | list[Send]` from one router is supported; the
  destination list is declared in `build_graph` (§5).

### 4.3 Delta helpers

```python
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
    must be the actor's *complete* inventory.
    """
    current = state.get("inventories", {})
    known = _known_actors(state)
    updates: dict[str, dict] = {}
    for delta in deltas:
        if delta.actor not in known:
            print(f"[Engine] inventory delta for unknown actor {delta.actor!r}; ignored")
            continue
        base = updates.get(delta.actor) or dict(
            current.get(delta.actor, {"items": [], "money": 0})
        )
        items = [i for i in base["items"] if i not in set(delta.items_removed)]
        for item in delta.items_added:
            if item not in items:
                items.append(item)
        updates[delta.actor] = {
            "items": items,
            "money": base["money"] + delta.money_delta,
        }
    return {"inventories": updates} if updates else {}
```

Notes:
- Multiple deltas for the same actor in one call accumulate.
- Removal is idempotent (`items_removed` not present → no-op).

```python
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
```

### 4.4 `game_response` (real)

```python
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
```

### 4.5 `_intents_text` (shared with narration)

Factor the existing valid-branch formatting out of `_narration_events` so
`game_response` and `narration` agree:

```python
def _intents_text(state: GameState, turn_no: int) -> str:
    return "\n".join(
        f"{m.name}: {m.content}" for m in turn_actions(state, turn_no)
    )
```

`_narration_events` valid branch becomes:

```python
parts = [state.get("game_action", ""), _intents_text(state, state.get("turn_no", 0))]
return "\n".join(p for p in parts if p)
```

### 4.6 `brief` (real)

```python
async def brief(state: GameState, cfg: EngineConfig) -> dict:
    print(f"[Engine] Answering clarification for turn {state.get('turn_no', 0)}")
    answer = await b.AnswerBrief(
        context=build_context(state, cfg),
        question=state["raw_input"],
    )
    return {"brief_answer": answer}
```

## 5. `src/agents/engine/graph.py` changes

```python
@dataclass
class NodeFns:
    """Injectable node bundle (tests replace these with deterministic fakes)."""

    classification: NodeFn
    npc: NodeFn               # new
    game_response: NodeFn
    brief: NodeFn
    narration: NodeFn


def default_node_fns(cfg: EngineConfig) -> NodeFns:
    return NodeFns(
        classification=partial(classification, cfg=cfg),
        npc=partial(npc_act, cfg=cfg),
        game_response=partial(game_response, cfg=cfg),
        brief=partial(brief, cfg=cfg),
        narration=partial(narration, cfg=cfg),
    )


def build_graph(cfg: EngineConfig, fns: NodeFns | None = None) -> StateGraph:
    fns = fns or default_node_fns(cfg)
    graph = StateGraph(GameState)

    graph.add_node("classification", fns.classification)
    graph.add_node("npc", fns.npc)
    graph.add_node("game_response", fns.game_response)
    graph.add_node("brief", fns.brief)
    graph.add_node("narration", fns.narration)

    graph.add_edge(START, "classification")
    graph.add_conditional_edges(
        "classification",
        route_classification,
        ["npc", "game_response", "brief", "narration"],
    )
    graph.add_edge("npc", "game_response")  # barrier
    graph.add_edge("game_response", "narration")
    graph.add_edge("brief", "narration")
    graph.add_edge("narration", END)

    return graph
```

The explicit destination list is required because the router returns both node
names (`str`) and `Send` objects; the map-reduce docs use the same
`add_conditional_edges(src, router, [dest, ...])` shape.

`Engine._cfg` gains the top-level concurrency key (not inside `configurable`):

```python
def _cfg(self, thread_id: str) -> dict:
    return {
        "configurable": {"thread_id": thread_id},
        "max_concurrency": self.config.max_npc_parallelism,
    }
```

## 6. `src/agents/engine/__init__.py`

Add `npc` exports:

```python
from .npc import NpcInput, npc_act

__all__ = [
    ...,
    "NpcInput",
    "npc_act",
]
```

No `state.py` change (P3.1).

## 7. BAML / `.env`

- No BAML type or function changes; `ClassifyInput`, `NpcAct`, `ResolveGame`,
  `AnswerBrief`, `NarrateTurn` already exist and their signatures are frozen.
- No `baml-cli generate` needed unless a prompt body is edited.
- `GAME_GENERIC_LLM` / `GAME_NARRATE_LLM` are already in `.env`.

## 8. Tests — `tests/test_engine_npc.py`

Deterministic and network-free. Stub the BAML client with `SimpleNamespace`
(monkeypatch `nodes_module.b` and `npc_module.b`) and inject `NodeFns` for graph
tests. Reuse the `fake_lore()` / `_card()` helpers pattern from
`tests/test_engine_graph.py`.

### 8.1 Router

1. **Zero cards → `"game_response"`.** `route_classification({"classification":
   "valid_action", "npc_cards": []}) == "game_response"`.
2. **Two cards → two `Send`s.** Build a state with two `npc_cards`; assert two
   `Send` objects targeting `"npc"`, each payload has `my_card` set to the
   matching card and retains the shared channels (`turn_no`, `raw_input`).
3. **Clarification/invalid unchanged.** `"brief"` / `"narration"`.

### 8.2 `npc_act` node (BAML stubbed)

4. **Intent → deterministic message.** `b.NpcAct` returns `"draws a blade"`;
   assert the returned `npc_actions[0].id == "npc:NPC:t{turn}:<digest>"`,
   `name == "NPC"`, `additional_kwargs["turn_no"] == turn`.
5. **Empty/whitespace → `{}`** (no write).
6. **Exception → `{}`.** `b.NpcAct` raises; assert no `npc_actions` key and no
   exception propagates.
7. **History passed.** Assert `b.NpcAct` received the windowed
   `npc_history(...)` text (or `None` when empty).

### 8.3 Game stage (BAML stubbed)

8. **Inventory deltas.** Start from `{"Player": {"items": ["rope"], "money":
   10}}`; `GameResolve` with `items_added=["torch"], items_removed=["rope"],
   money_delta=-3` for `"Player"`; assert the returned `inventories["Player"] ==
   {"items": ["torch"], "money": 7}` (complete dict), and that a second
   unchanged actor is absent.
9. **Unknown actor ignored.** A delta for `"Ghost"` produces no `inventories`
   entry.
10. **State deltas.** `physical`/`mental` for the player and an NPC land in the
    respective dicts; a player `location` sets `current_location`; an NPC
    `location` does **not** change `current_location`.
11. **`or_` merge end-to-end.** A graph run with an initial `inventories` from
    lore plus a game-stage delta yields both actors (merge, not replace).

### 8.4 Brief / narration / engine

12. **Brief writes `brief_answer`** from `b.AnswerBrief`.
13. **Narration events include NPC intents** for the current turn (via
    `_intents_text` / `turn_actions`).
14. **`max_concurrency` present:** `Engine(cfg)._cfg("t")["max_concurrency"] ==
    cfg.max_npc_parallelism`.
15. **Graph render** contains `npc`, `classification`, `game_response`, `brief`,
    `narration`.
16. **Valid turn, one NPC, injected `NodeFns`:** exactly one `npc_actions`
    entry with the right `name`/`id`/`turn_no`; `game_action` and `narration`
    present; `game_response` ran once after the NPC branch (record call order in
    the fakes).
17. **Zero NPCs:** `npc` never runs; `game_response` runs.

`tests/test_engine_state.py` (11) and `tests/test_engine_graph.py` (14) must stay
green — **25 existing + new, all green.**

## 9. Acceptance

```bash
uv run pytest -q          # 25 existing + new Phase 3 tests, all green
```

No `baml-cli generate` and no network are required. The live LLM smoke is
deferred to Phase 4.

## 10. Risks / gotchas

| Risk | Mitigation |
|------|------------|
| Router returning `[]` silently ends the graph | Zero-NPC case returns `"game_response"` explicitly. |
| Mixed `str`/`list[Send]` router | Declare destinations `["npc","game_response","brief","narration"]`. |
| `Send` payload must be full state (D1) | Payload is `{**state, "my_card": card}`; the node reads shared channels from it. |
| `my_card` is not a channel | Only the `Send` payload carries it; `npc_act` never writes it back. |
| `or_` merges, does not replace | Game stage returns **complete** per-actor inventory dicts. |
| One NPC branch failure fails the superstep | `try/except` inside `npc_act`; return `{}`. |
| NPC writes a last-value channel | `npc_act` writes only `npc_actions`. |
| `current_location` thrash from NPCs | Player-only write (P3.2). |
| `max_concurrency` placement | Top-level `RunnableConfig` key, not under `configurable`. |
| `NpcInput` vs `GameState` typing | `NpcInput(GameState)` TypedDict subclass adds `my_card`. |

## 11. Doc housekeeping

Add a **v1.3 (Phase 3)** changelog entry to
`2026-09-16-game-engine-architecture.md` and
`2026-09-17-game-engine-implementation-plan.md` recording:

- NPC fan-out shipped as a plain-node `Send` with a full-state payload;
  `npc → game_response` barrier; zero-NPC routing to `game_response`.
- `game_response` applies `InventoryDelta`/`StateDelta` as complete per-actor
  dicts; `current_location` follows the player only.
- `npc_act` swallows errors and no-ops write nothing.
- `max_concurrency` wired from `EngineConfig.max_npc_parallelism`.

## 12. Deferred (do not implement in Phase 3)

- Phase 4 persisted-thread smoke (valid/clarification/invalid across 2+ turns on
  `AsyncSqliteSaver`, resume after restart), retry idempotency, and the live
  `{{ ctx.output_format }}` decision.
- Phase 5 game-stage split (trigger only on observed quality failure).
- N-NPC lore generation, NPC context tuning beyond the recency window,
  TUI/`rich`, eval harness, checkpoint retention/pruning.
