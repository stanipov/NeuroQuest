# Game Engine — Phase 2 Implementation Plan

Status: ready to implement.
Parent specs:
- `dev_notes/game/2026-09-16-game-engine-architecture.md` (v1.1)
- `dev_notes/game/2026-09-17-game-engine-implementation-plan.md` (v1.1)
- `dev_notes/game/phase1.md` (Phase 1, complete)

This document is authoritative for Phase 2 where the specs above disagree.
Environment: Python 3.14.7, `langgraph 1.2.9`, `baml-py 0.222.0`,
`langgraph-checkpoint-sqlite 3.1.1`.

## 0. Scope

Deliver the graph skeleton and the ownership of the checkpointer, without any
NPC fan-out or real game-runtime resolution:

1. `src/agents/engine/nodes.py` — `build_context`, `classification`,
   `route_classification`, `game_response` (stub), `brief` (stub), `narration`.
2. `src/agents/engine/graph.py` — `build_graph(...)` + `Engine` (owns
   `AsyncSqliteSaver` lifecycle, compile, `new_game`, `turn`, `stream_turn`).
3. Extend `src/agents/engine/__init__.py` exports.
4. `.env`: add `GAME_GENERIC_LLM` and `GAME_NARRATE_LLM`.
5. `tests/test_engine_graph.py` — deterministic, network-free.
6. Doc housekeeping: record Phase 1 D6 deltas + Phase 2 findings in the v1.1
   arch/plan docs (v1.2 note).

Explicitly out of scope for Phase 2: NPC fan-out (`npc.py`, `Send`), real
`b.ResolveGame`, real `b.AnswerBrief`, game-stage split, TUI/`rich`, eval
harness, checkpoint retention, checkpoint pruning.

## 1. Locked decisions for Phase 2

Carried from Phase 1 (do not revisit):

- **D1** NPC fan-out is a plain node with a full-state `Send` payload (Phase 3),
  not a shared-state subgraph. No `NpcSubgraphState`.
- **D2** `classification` owns the per-turn input: it bumps `turn_no` **and**
  appends the `HumanMessage`. `initial_state(lore)` does not take `raw_input`.
- **D3** Deterministic NPC message IDs (`make_npc_msg`).
- **D4** `AsyncSqliteSaver` takes a filesystem path (not a `sqlite+aiosqlite://`
  URL).
- **D5** A `StateGraph` must have an entrypoint before compile.

New in Phase 2 (chosen with the user):

- **P2.1** The valid path uses deterministic **stub** nodes
  (`game_response`, `brief`) so all three branches run and are unit-tested now.
  Phase 3 replaces the node bodies only; node names and edges stay fixed.
- **P2.2** `Engine.new_game(lore)` seeds the checkpoint via
  `graph.aupdate_state(config, initial_state(lore), as_node=START)`. Subsequent
  turns call `turn(thread_id, raw_input)` / `stream_turn(thread_id, raw_input)`,
  which invoke only `{"raw_input": ...}`. Lore is never re-sent.
- **P2.3** The `Engine` opens `aiosqlite.connect(path)` itself and constructs
  `AsyncSqliteSaver(conn, serde=build_serde())` (see F1). It does **not** use
  `AsyncSqliteSaver.from_conn_string`.
- **P2.4** Narration is the only streaming point and uses
  `get_stream_writer()`. Custom chunks are incremental deltas shaped
  `{"narration_token": <suffix str>}`; the final node update carries the full
  text. Fallback (if BAML partials are non-monotonic): emit full snapshots.

## 2. Findings verified for Phase 2

Verified empirically this cycle against `langgraph 1.2.9` and `baml-py 0.222.0`.
These are the reason for decisions P2.2–P2.4.

### F1 — `from_conn_string` cannot carry `serde`

`AsyncSqliteSaver.from_conn_string` is an `@asynccontextmanager` that does
literally `yield cls(conn)` (`langgraph/checkpoint/sqlite/aio.py:131-145`); the
`serde` keyword exists only on `__init__`
(`AsyncSqliteSaver(conn, *, serde=None)`, line 118). Phase 1's note
("`Engine` must use `build_serde()` when constructing `AsyncSqliteSaver`")
therefore forces P2.3.

Confirmed working:

```python
conn = await aiosqlite.connect(path)
saver = AsyncSqliteSaver(conn, serde=build_serde())
await saver.setup()
```

### F2 — `aupdate_state` seeding works on a fresh thread

- `await graph.aupdate_state(cfg, values, as_node=START)` on a thread with no
  checkpoint succeeds.
- A later `await graph.ainvoke({"raw_input": "..."}, cfg)` retains every seeded
  channel.
- A partial `ainvoke` on a *fresh, unseeded* thread also succeeds (LangGraph does
  not enforce non-`NotRequired` keys at runtime), but P2.2 does not rely on that.

### F3 — streaming shape

`graph.astream(input, cfg, stream_mode=["updates", "custom"], version="v2",
subgraphs=False)` yields:

```python
{"type": "custom",  "ns": (), "data": {"narration_token": "Hel"}}
{"type": "custom",  "ns": (), "data": {"narration_token": "lo "}}
{"type": "updates", "ns": (), "data": {"narration": {"narration": "Hello"}}}
```

`subgraphs=False` is the default and keeps narration the only streaming point.

### F4 — loop capture

`AsyncSqliteSaver.__init__` calls `asyncio.get_running_loop()`, so the saver
**must** be constructed inside the running loop (i.e. inside `Engine.__aenter__`,
not `Engine.__init__`).

### F5 — async `get_stream_writer`

`get_stream_writer()` works in async nodes on Python ≥ 3.11. Python is 3.14, so
the writer-parameter fallback is not needed.

## 3. Graph topology (Phase 2)

```
START → classification ─┬─ valid         → game_response* → narration → END
                         ├─ clarification → brief*         → narration → END
                         └─ invalid       → narration       → END
```

`*` deterministic stub node in Phase 2.

Phase 3 replaces the stub bodies and inserts the NPC fan-out **before**
`game_response` (barrier edge `npc → game_response`); the `game_response` node
name and its inbound/outbound edges do not move.

## 4. `src/agents/engine/nodes.py`

### 4.1 Imports and constants

```python
from __future__ import annotations

from typing import Literal

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.config import get_stream_writer

from src.baml_client.async_client import b
from src.baml_client.types import InputDecision
from src.agents.engine.config import EngineConfig
from src.agents.engine.state import GameState, turn_actions

Classification = Literal["valid_action", "clarification", "invalid"]

_DECISION_MAP = {
    InputDecision.ValidAction: "valid_action",
    InputDecision.Clarification: "clarification",
    InputDecision.Invalid: "invalid",
}
```

`turn_actions` is imported for the Phase 3 narration path and used now (empty
list in Phase 2) so the valid events string is already correct.

### 4.2 `build_context(state, cfg) -> str`

One helper (kept in `nodes.py` to match the Phase 2 file map; split to
`context.py` only if it grows). Serializes:

- world: `world_narrative.name` / `current_state`, `world_concept` categories;
- place: `starting_context` (region/settlement/location), `current_location`;
- actors: `player_card`, `npc_cards` (name/occupation/strengths/weaknesses);
- runtime: `inventories`, `physical_states`, `mental_states`;
- history: the last `cfg.history_window` `messages`, role-tagged
  (`player:` / `narrator:` / `npc:<name>:`).

All lore/runtime keys are `NotRequired`; the helper must tolerate any of them
being absent (Phase 1's `initial_state` is tolerant too). It returns a plain
string; `classification` embeds history inside `context` because the frozen
`ClassifyInput(context: string, input: string)` signature has no history
parameter.

### 4.3 `classification(state) -> dict`

```python
async def classification(state: GameState) -> dict:
    cfg = _active_config(state)  # see note below
    res = await b.ClassifyInput(
        context=build_context(state, cfg),
        input=state["raw_input"],
    )
    turn = state.get("turn_no", 0) + 1
    return {
        "turn_no": turn,
        "classification": _DECISION_MAP[res.decision],
        "classification_reason": res.reason,
        "invalid_reason": res.invalid_reason,
        "messages": [
            HumanMessage(content=state["raw_input"], id=f"user:t{turn}")
        ],
    }
```

- `turn_no` bumped exactly once per turn (D2).
- `HumanMessage` id is deterministic per turn (`user:t{turn}`); a node retry
  overwrites via `add_messages` instead of duplicating.
- `invalid_reason` is `None` for non-invalid decisions; it is written anyway so
  stale values from a previous turn cannot leak (last-value channel).

**Config access in nodes.** Node functions are module-level and injected into the
graph by `build_graph`; `EngineConfig` is therefore passed by binding the nodes
in `build_graph(cfg, fns)` rather than reading a global. `build_context` takes
`cfg` explicitly; the node callables are thin closures created in `build_graph`:

```python
async def _classification(state):
    ...
```

See §5.1 for the `NodeFns` injection mechanism used by tests.

### 4.4 `route_classification(state) -> Literal[...]`

```python
def route_classification(
    state: GameState,
) -> Literal["game_response", "brief", "narration"]:
    decision = state.get("classification")
    if decision == "clarification":
        return "brief"
    if decision == "valid_action":
        return "game_response"
    return "narration"
```

Pattern mirrors `src/agents/lore/world_gen/agent.py:101`.

### 4.5 `game_response` (Phase 2 stub)

```python
async def game_response(state: GameState) -> dict:
    # ponytail: Phase 3 replaces this with a real b.ResolveGame call; name and
    # edges stay fixed.
    return {"game_action": "[(stub) turn resolved; game stage lands in Phase 3]"}
```

### 4.6 `brief` (Phase 2 stub)

```python
async def brief(state: GameState) -> dict:
    # ponytail: Phase 3 replaces this with a real b.AnswerBrief call.
    return {"brief_answer": "[(stub) no lore answer yet; brief lands in Phase 3]"}
```

### 4.7 `narration(state) -> dict`

Streaming is the only side channel; the node still writes the full narration and
a deterministic `AIMessage`.

```python
async def narration(state: GameState) -> dict:
    mode = state.get("classification", "invalid")
    events = _narration_events(state, mode)
    turn = state.get("turn_no", 0)

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
        else:  # non-monotonic partial: fall back to snapshot
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
```

`_narration_events`:

```python
def _narration_events(state: GameState, mode: str) -> str:
    if mode == "clarification":
        return state.get("brief_answer", "")
    if mode == "invalid":
        return state.get("invalid_reason", "") or state.get(
            "classification_reason", ""
        )
    # valid: game summary + this turn's NPC intents (empty until Phase 3)
    parts = [state.get("game_action", "")]
    for msg in turn_actions(state, state.get("turn_no", 0)):
        parts.append(f"{msg.name}: {msg.content}")
    return "\n".join(p for p in parts if p)
```

Valid branch: `game_action` plus (Phase 3) the turn's NPC intents. In Phase 2
the intents list is empty because the stub game stage writes no `npc_actions`.

Deterministic narrative id `narrator:t{turn}` → node retry overwrites.

### 4.8 Streaming contract

- Custom chunks: `{"narration_token": <str>}` (incremental suffix).
- Final node update: `{"narration": <full str>, "messages": [...]}`.
- Only `narration` writes custom data (F3), so it is the only streaming point.

## 5. `src/agents/engine/graph.py`

### 5.1 `NodeFns` bundle + `build_graph`

To make tests deterministic without monkeypatching BAML globals, the graph is
built from an injectable bundle:

```python
from dataclasses import dataclass
from typing import Awaitable, Callable

NodeFn = Callable[[GameState], Awaitable[dict]]

@dataclass
class NodeFns:
    classification: NodeFn
    game_response: NodeFn
    brief: NodeFn
    narration: NodeFn


def default_node_fns(cfg: EngineConfig) -> NodeFns:
    return NodeFns(
        classification=partial(classification, cfg=cfg),
        game_response=game_response,
        brief=brief,
        narration=partial(narration, cfg=cfg),
    )
```

`classification` / `narration` accept `cfg` as a keyword so they stay module-level
(the default bundle binds it via `functools.partial`). `build_context` needs
`cfg`, hence the binding.

```python
def build_graph(cfg, fns=None):
    fns = fns or default_node_fns(cfg)
    graph = StateGraph(GameState)
    graph.add_node("classification", fns.classification)
    graph.add_node("game_response", fns.game_response)
    graph.add_node("brief", fns.brief)
    graph.add_node("narration", fns.narration)

    graph.add_edge(START, "classification")
    graph.add_conditional_edges("classification", route_classification)
    graph.add_edge("game_response", "narration")
    graph.add_edge("brief", "narration")
    graph.add_edge("narration", END)
    return graph
```

`build_graph` returns an *uncompiled* `StateGraph`; `Engine` compiles it with the
checkpointer.

### 5.2 `Engine`

```python
class Engine:
    def __init__(
        self,
        config: EngineConfig | None = None,
        *,
        checkpointer: BaseCheckpointSaver | None = None,
        node_fns: NodeFns | None = None,
    ):
        self.config = config or EngineConfig()
        self._checkpointer = checkpointer
        self._node_fns = node_fns
        self._conn = None
        self.graph = None

    async def __aenter__(self) -> "Engine":
        if self._checkpointer is not None:
            saver = self._checkpointer
        else:
            path = Path(self.config.sqlite_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = await aiosqlite.connect(str(path))
            saver = AsyncSqliteSaver(self._conn, serde=build_serde())
            await saver.setup()
        self.graph = build_graph(self.config, self._node_fns).compile(
            checkpointer=saver
        )
        return self

    async def __aexit__(self, *exc) -> None:
        if self._conn is not None:
            await self._conn.close()
            self._conn = None

    async def new_game(self, lore: dict, thread_id: str | None = None) -> str:
        tid = thread_id or str(uuid4())
        await self.graph.aupdate_state(
            self._cfg(tid), initial_state(lore), as_node=START
        )
        return tid

    async def turn(self, thread_id: str, raw_input: str) -> GameState:
        return await self.graph.ainvoke(
            {"raw_input": raw_input}, self._cfg(thread_id)
        )

    async def stream_turn(self, thread_id: str, raw_input: str):
        async for event in self.graph.astream(
            {"raw_input": raw_input},
            self._cfg(thread_id),
            stream_mode=["updates", "custom"],
            version="v2",
            subgraphs=False,
        ):
            yield event

    async def state(self, thread_id: str):
        return await self.graph.aget_state(self._cfg(thread_id))

    @staticmethod
    def _cfg(thread_id: str) -> dict:
        return {"configurable": {"thread_id": thread_id}}
```

Notes:

- The saver is constructed inside `__aenter__` (F4).
- `checkpointer=` injection lets unit tests use
  `InMemorySaver(serde=build_serde())` with no SQLite file.
- `new_game` seeds lore once (P2.2 / F2); `turn`/`stream_turn` send only
  `raw_input`.
- `sqlite_path`'s parent directory is created on `__aenter__` (Phase 1 left
  `data/` absent).

## 6. `src/agents/engine/__init__.py`

Extend exports:

```python
from .config import EngineConfig
from .graph import Engine, NodeFns, build_graph
from .nodes import classification, game_response, brief, narration, route_classification
from .serde import build_serde
from .state import (...)

__all__ = [
    "EngineConfig", "Engine", "NodeFns", "build_graph",
    "classification", "route_classification", "game_response", "brief", "narration",
    "build_serde", "ActorInventory", "Classification", "GameState",
    "initial_state", "make_npc_msg", "npc_history", "turn_actions",
]
```

Beware of import cycles: `graph.py` imports `nodes.py` and `state.py`; `nodes.py`
imports `config.py` and `state.py` only. `__init__` imports both; keep the order
above (`config` → `graph` → `nodes` → `serde` → `state`) or use explicit
relative imports, which are order-independent.

## 7. BAML / `.env`

### 7.1 `.env`

Add (values point at the same local model used by the lore clients):

```
GAME_GENERIC_LLM="qwen3.8-27b-nvfp4-fp4-dflash2-sglang"
GAME_NARRATE_LLM="qwen3.8-27b-nvfp4-fp4-dflash2-sglang"
```

Generation and CI do not need them; live smoke does.

### 7.2 Prompt tweak (conditional)

For the three `-> string` functions (`NarrateTurn`, `AnswerBrief`, `NpcAct`),
remove `{{ ctx.output_format }}` **only if** a live call shows wrapper/JSON noise
in the returned string (Phase 1 §10 flagged this; streaming makes plain text
important). Do not change the prompt pre-emptively. Re-run
`uv run baml-cli generate --from=src/baml_src` after any edit.

### 7.3 Signatures are frozen

No new BAML types or functions in Phase 2. `ClassifyInput`, `NarrateTurn`,
`GameResolve`, `AnswerBrief`, `NpcAct` already exist from Phase 1.

## 8. Tests — `tests/test_engine_graph.py`

Deterministic and network-free. Use injected `NodeFns`, canned
`InputClassification` values, and `InMemorySaver(serde=build_serde())` for unit
paths; use `tmp_path` + a real file only for the persistence test.

Helpers:

```python
def make_fns(decision=InputDecision.ValidAction, narration_text="Rendered."):
    def cls(state):
        return {
            "turn_no": state.get("turn_no", 0) + 1,
            "classification": _DECISION_MAP[decision],
            "classification_reason": "r",
            "invalid_reason": "nope" if decision is InputDecision.Invalid else None,
        }
    async def narr(state):
        writer = get_stream_writer()
        for tok in ["Ren", "dered."]:
            writer({"narration_token": tok})
        return {
            "narration": narration_text,
            "messages": [AIMessage(content=narration_text, name="narrator",
                                   id=f"narrator:t{state.get('turn_no', 0)}")],
        }
    ...
```

Tests:

1. **Routing — valid:** classification → `game_response` → `narration`; the
   final state has `game_action` (stub text) and `narration`.
2. **Routing — clarification:** classification → `brief` → `narration`; final
   state has `brief_answer` (stub) and `narration`; `game_action` absent.
3. **Routing — invalid:** classification → `narration` directly; neither
   `game_action` nor `brief_answer` present; `invalid_reason` written.
4. **Turn accounting:** one turn bumps `turn_no` to 1 and appends exactly one
   `HumanMessage` with `id == "user:t1"`; a node-level re-run on the same input
   checkpoint does not duplicate it.
5. **Narration message:** `AIMessage` with `id == "narrator:t{turn}"`,
   `name == "narrator"`, `content == final text`.
6. **Classification fields:** writes `classification`, `classification_reason`,
   `invalid_reason` (None on non-invalid).
7. **Engine seeding (`InMemorySaver`):** `new_game(lore)` then two `turn()`
   calls → lore channels survive; `turn_no == 2`; `messages` = opening + 2 human
   + 2 narrator.
8. **Streaming:** `stream_turn` yields ≥1 `{"type": "custom",
   "data": {"narration_token": ...}}` before the `{"type": "updates", ...}`
   event; concatenated tokens == final narration.
9. **SQLite lifecycle (`tmp_path`):** `async with Engine(cfg, checkpointer=None)`
   → `new_game` + `turn` + exit; reopen a second `Engine` on the same file and
   assert the thread's `turn_no`/`messages` are visible (persistence + warning-
   free serde).
10. **Graph render:** `build_graph(cfg).compile().get_graph().draw_mermaid()`
    contains `classification`, `game_response`, `brief`, `narration`.

`tests/test_engine_state.py` (11 tests) must stay green.

## 9. Acceptance

```bash
uv run baml-cli generate --from=src/baml_src   # only if prompts changed
uv run pytest -q                               # 11 existing + new, all green
```

Manual live smoke (local model, needs `GAME_*_LLM` in `.env`):

```bash
uv run python - <<'PY'
import asyncio
from src.agents.engine import Engine, EngineConfig

async def main():
    cfg = EngineConfig(sqlite_path="tmp/engine_smoke.db")
    async with Engine(cfg) as e:
        tid = await e.new_game({})          # empty lore is tolerated (Phase 1)
        async for ev in e.stream_turn(tid, "What is this place?"):
            print(ev)
        st = (await e.state(tid)).values
        print("turn", st["turn_no"], "class", st["classification"])

asyncio.run(main())
PY
```

Expected: custom `narration_token` events stream first, then updates for
`classification` → `brief`/`game_response` → `narration`; the final state holds
the full narration and a bumped `turn_no`. Only `narration` emits custom data.

## 10. Risks / gotchas

| Risk | Mitigation |
|------|------------|
| `from_conn_string` cannot take `serde` (F1) | Engine opens `aiosqlite.connect` and constructs `AsyncSqliteSaver(conn, serde=build_serde())` (P2.3). |
| Saver captures the loop at construction (F4) | Construct it inside `__aenter__`. |
| BAML string partials may be cumulative or snapshots | Emit suffix deltas when monotonic, snapshot fallback otherwise (P2.4). Verify on live smoke. |
| `{{ ctx.output_format }}` on `-> string` functions pollutes narration | Observe live; drop it only if noisy. |
| `raw_input` is a required channel; seeding vs invoke | `new_game` seeds via `aupdate_state`; verified partial invoke retains state (F2). |
| Node functions need `EngineConfig` | Bind `cfg` in `default_node_fns` via `functools.partial`; tests inject `NodeFns`. |
| `or_` merges, does not replace (Phase 3) | Not touched here; Phase 3 game stage must return complete actor dicts. |
| Import cycle `graph ↔ nodes ↔ __init__` | `nodes.py` imports only `config`/`state`; keep relative imports in `__init__`. |
| `data/` does not exist | `Engine.__aenter__` creates the parent dir. |
| `get_stream_writer` outside a run context | Called only inside the `narration` node. |
| Async SQLite + pytest | `asyncio_mode = "auto"` already configured (Phase 1). |

## 11. Doc housekeeping (Phase 1 D6 + Phase 2)

Update the two v1.1 docs to a v1.2 note recording:

- plain-node fan-out with full-state `Send`; `NpcSubgraphState` removed;
- human message appended in `classification`;
- `AsyncSqliteSaver.from_conn_string` does not accept `serde`, so the Engine owns
  `aiosqlite.connect` + `AsyncSqliteSaver(conn, serde=build_serde())`;
- narration streaming via `get_stream_writer()` with
  `stream_mode=["updates","custom"], version="v2", subgraphs=False`.

## 12. Deferred (do not implement in Phase 2)

- `src/agents/engine/npc.py`, `Send` fan-out, `max_npc_parallelism` wiring.
- Real `b.ResolveGame` (game stage) and `b.AnswerBrief` (brief).
- Game-stage split into inventory / states / location / summary (Phase 5 trigger).
- TUI / `rich` rendering of the streamed narration.
- Eval harness, checkpoint retention/pruning.
