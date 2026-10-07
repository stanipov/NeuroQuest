# Game Engine — Phase 1 Implementation Plan

Status: ready to implement.
Parent spec: `dev_notes/game/2026-09-16-game-engine-architecture.md` (v1.1)
and `dev_notes/game/2026-09-17-game-engine-implementation-plan.md` (v1.1).
This document is authoritative for Phase 1 where the two specs above disagree.

## 0. Scope

Deliver, with no LLM calls and no network:

1. Dependency + test scaffolding.
2. `src/baml_src/engine.baml` type + stub-function contract, generated into
   `src/baml_client/`.
3. `src/agents/engine/state.py` — `GameState`, reducers, `make_npc_msg`,
   read helpers, `initial_state`.
4. `src/agents/engine/config.py` — `EngineConfig`.
5. `src/agents/engine/__init__.py` exports.
6. `tests/test_engine_state.py` — pure unit tests + one async checkpointer
   round-trip.

Explicitly out of scope for Phase 1: any graph wiring (`graph.py`), nodes
(`nodes.py`, `npc.py`), the `Engine` class, SQLite usage, streaming, prompts.

---

## 1. Locked decisions (deviations from the v1.1 specs)

These were verified empirically against `langgraph 1.2.9` and must be honored by
Phase 2/3 as well.

### D1 — NPC fan-out is a plain node, not a shared-state subgraph

`Send` to a shared-state subgraph does **not** expose parent channels to the
subgraph (payload becomes the subgraph input). Passing the full state in the
payload makes parallel fan-out fail with
`InvalidUpdateError: Can receive only one value per step` on every non-reducer
channel.

Locked design for Phase 3:

```python
# router
return [Send("npc", {**state, "my_card": card}) for card in state["npc_cards"]]
```

`npc_act` is a plain `async def` node. It reads shared channels from its input
and writes **only** the reducer-backed `npc_actions`.

Consequences for Phase 1:
- There is **no `NpcSubgraphState`**. Do not define it.
- Do not add reducer-tolerant annotations to the read-only channels
  (`world_concept`, `turn_no`, `raw_input`, ...). Keep them last-value.

### D2 — `classification` owns per-turn player input

`classification` does `turn_no += 1` **and** appends
`HumanMessage(raw_input, id=...)`. This runs exactly once per turn and is
retry-safe.

Consequences for Phase 1:
- `initial_state(lore)` does **not** take `raw_input`.
- `initial_state(lore)` seeds `messages=[AIMessage(scene.narrative, id="opening")]`.
- Engine per-turn invocation is `ainvoke({"raw_input": text}, config)`.

### D3 — Deterministic NPC message IDs

`id = f"npc:{name}:t{turn_no}:{blake2b(content.encode(), digest_size=8).hexdigest()}"`
(64-bit digest → 16 hex chars). Wall-clock timestamp goes in
`additional_kwargs["ts"]` only. No-op NPC writes nothing.

### D4 — `AsyncSqliteSaver` takes a path

Phase 2 must use `AsyncSqliteSaver.from_conn_string(path)` + `await saver.setup()`,
**not** a `sqlite+aiosqlite://` URL. `EngineConfig.sqlite_path` is a filesystem
path.

### D5 — Phase 1 acceptance ignores empty-graph compile

`StateGraph(GameState).compile()` raises `ValueError: Graph must have an
entrypoint`. Acceptance uses a one-node smoke graph instead.

### D6 — Arch deltas to record later

After Phase 1, update the two v1.1 docs to state: plain-node fan-out with
full-state `Send`; human message appended in `classification`; `NpcSubgraphState`
removed; `AsyncSqliteSaver.from_conn_string(path)`.

---

## 2. Step 0 — Housekeeping, dependencies, scaffolding

### 0.1 Housekeeping

The tree currently has uncommitted work: `src/baml_src/clients.baml` modified,
untracked `dev_notes/`, `AGENTS.md`, `.opencode/`, `tmp/`. Commit or stash the
intended WIP before starting so Phase 1 lands as a clean commit. Branch: `dev/v2`
(a dedicated `feat/engine-phase1` branch is optional; no worktree needed).

### 0.2 Dependencies (UV only — `pip`/`apt` are forbidden)

```bash
uv add langgraph-checkpoint-sqlite       # pulls aiosqlite; needed in Phase 2
uv add --dev pytest pytest-asyncio
```

### 0.3 Pytest config (`pyproject.toml`)

Append:

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
pythonpath = ["."]
testpaths = ["tests"]
```

### 0.4 Test directory

```bash
mkdir -p tests
```

---

## 3. Step 1 — `src/baml_src/engine.baml`

Prompts are stubs here; signatures are frozen so Phase 2/3 do not churn BAML
types. Run `uv run baml-cli generate --from=src/baml_src` after writing.

```baml
// Game Engine — input classification
enum InputDecision {
    ValidAction
    Clarification
    Invalid
}

class InputClassification {
    decision InputDecision @description("valid in-world action, clarification question, or invalid input")
    reason string @description("Brief reasoning, 1-2 sentences")
    invalid_reason string? @description("Only when decision is Invalid; brief user-facing reason")
}

// Game Engine — runtime deltas
class InventoryDelta {
    actor string @description("Actor name; must match a player or NPC card name")
    items_added string[] @description("Item names gained; [] if none")
    items_removed string[] @description("Item names lost; [] if none")
    money_delta int @description("Change in money; 0 if none")
}

class StateDelta {
    actor string @description("Actor name; must match a player or NPC card name")
    physical string? @description("New full physical-state description when changed; null otherwise")
    mental string? @description("New full mental-state description when changed; null otherwise")
    location string? @description("New current location when changed; null otherwise")
}

class GameResolve {
    terse string @description("Terse concept-level summary of the turn, 1-3 sentences")
    inventory_deltas InventoryDelta[] @description("[] if no inventory changes")
    state_deltas StateDelta[] @description("[] if no state changes")
}

// ---------------------------------------------------------------------------
// Functions — prompt bodies are stubs; fleshed out in Phase 2/3.
// ---------------------------------------------------------------------------

function ClassifyInput(context: string, input: string) -> InputClassification {
    client GameLLM
    prompt #"
    {{ _.role("system") }}
    You are the game master of a textual turn-based RPG. Classify the player's
    input as ValidAction, Clarification, or Invalid.

    World context:
    {{ context }}

    {{ _.role("user") }}
    Player input: {{ input }}

    {{ ctx.output_format }}
    "#
}

function NpcAct(context: string, npc: PlayerCharacterCard, history: string?) -> string {
    client GameLLM
    prompt #"
    {{ _.role("system") }}
    Decide one NPC's intent for this turn. Output a single terse declarative
    sentence, or an empty string if the NPC does nothing. Stay faithful to the
    NPC card and the world. Do not narrate outcomes.

    World and situation:
    {{ context }}

    NPC card:
    {{ npc }}

    {% if history %}
    Recent actions by this NPC:
    {{ history }}
    {% endif %}

    {{ _.role("user") }}
    What does this NPC intend to do this turn?

    {{ ctx.output_format }}
    "#
}

function ResolveGame(context: string, input: string, intents: string) -> GameResolve {
    client GameLLM
    prompt #"
    {{ _.role("system") }}
    You are the game master. Decide what actually happens this turn. You are the
    sole authority over inventory, location, and physical/mental states. Be terse
    and concrete; prefer small, plausible deltas.

    World and situation:
    {{ context }}

    Player input:
    {{ input }}

    NPC intents this turn:
    {{ intents }}

    {{ ctx.output_format }}
    "#
}

function AnswerBrief(context: string, question: string) -> string {
    client GameLLM
    prompt #"
    {{ _.role("system") }}
    Answer the player's clarification question in 1-3 sentences, grounded in the
    world context. Do not narrate actions.

    World context:
    {{ context }}

    {{ _.role("user") }}
    Question: {{ question }}

    {{ ctx.output_format }}
    "#
}

function NarrateTurn(context: string, events: string, mode: string) -> string {
    client GameNarrateLLM
    prompt #"
    {{ _.role("system") }}
    You are the narrator of a textual RPG. Render the given events as coherent
    Markdown prose for the player. Mode is one of: valid, clarification, invalid.
    For invalid, explain briefly why the input was refused and continue the scene.

    World and situation:
    {{ context }}

    Events:
    {{ events }}

    Mode: {{ mode }}

    {{ ctx.output_format }}
    "#
}
```

### 3.1 Clients (`src/baml_src/clients.baml`)

Append two clients, matching the existing style (do not clobber the file's
current uncommitted changes). Add `GAME_GENERIC_LLM` and `GAME_NARRATE_LLM` to
`.env`.

```baml
client<llm> GameLLM {
  provider openai-generic
  retry_policy Constant
  options {
    base_url env.BASE_URL
    api_key env.API_KEY
    model env.GAME_GENERIC_LLM
    temperature 0.8

    reasoning_effort: "medium"
    chat_template_kwargs {
      "enable_thinking" true
      "reasoning_effort" "medium"
      "preserve_reasoning" true
    }
  }
}

client<llm> GameNarrateLLM {
  provider openai-generic
  retry_policy Constant
  options {
    base_url env.BASE_URL
    api_key env.API_KEY
    model env.GAME_NARRATE_LLM
    temperature 0.6

    reasoning_effort: "medium"
    chat_template_kwargs {
      "enable_thinking" true
      "reasoning_effort" "medium"
      "preserve_reasoning" true
    }
  }
}
```

### 3.2 Generate

```bash
uv run baml-cli generate --from=src/baml_src
```

Verify `src/baml_client/types.py` contains `InputDecision`,
`InputClassification`, `InventoryDelta`, `StateDelta`, `GameResolve`.

---

## 4. Step 2 — `src/agents/engine/state.py`

```python
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import blake2b
from operator import or_
from typing import Annotated, Literal, NotRequired, TypedDict

from langchain_core.messages import AIMessage, AnyMessage, HumanMessage
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
    digest = blake2b(content.encode("utf-8"), digest_size=8).hexdigest()
    return AIMessage(
        content=content,
        name=npc_name,
        id=f"npc:{npc_name}:t{turn_no}:{digest}",
        additional_kwargs={
            "turn_no": turn_no,
            "ts": datetime.now(timezone.utc).isoformat(),
        },
    )


def npc_history(
    state: GameState, npc_name: str, k: int | None = None
) -> list[AIMessage]:
    msgs = [m for m in state.get("npc_actions", []) if m.name == npc_name]
    msgs.sort(key=lambda m: m.additional_kwargs.get("turn_no", 0))
    return msgs if k is None else msgs[-k:]


def turn_actions(state: GameState, turn_no: int) -> list[AIMessage]:
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

    `raw_input` is intentionally not set here; `classification` writes the
    per-turn `HumanMessage` and the Engine passes `raw_input` on each invoke.
    """
    npc_cards = [lore["npc_card"]] if lore.get("npc_card") else []

    cards = [lore["player_card"], *npc_cards]
    inventories: dict[str, ActorInventory] = {
        card.name: {"items": list(card.inventory), "money": card.money}
        for card in cards
        if card is not None
    }

    starting_context = lore.get(LORE_CONTEXT_KEY)
    opening = _opening_message(lore)

    state: GameState = {
        "messages": [opening] if opening else [],
        "npc_actions": [],
        "inventories": inventories,
        "physical_states": {},
        "mental_states": {},
        "turn_no": 0,
    }

    if starting_context is not None:
        state["starting_context"] = starting_context
        state["current_location"] = starting_context.location.name

    lores = {
        "world_type": "world_type",
        "world_concept": "world_concept",
        "world_narrative": "world_narrative",
        "arrangement": "arrangement",
        "scene": "scene",
        "player_card": "player_card",
    }
    for src, dst in lores.items():
        value = lore.get(src)
        if value is not None:
            state[dst] = value  # type: ignore[literal-required]

    if npc_cards:
        state["npc_cards"] = npc_cards

    # HumanMessage is imported for symmetry with phase 2; unused in phase 1
    _ = HumanMessage
    return state
```

Notes:
- `or_` is `operator.or_` (dict merge, right operand wins per key). The game
  stage must return **complete** per-actor dicts; actor removal is not
  expressible and is acceptable for v1.
- `current_location` is seeded from `starting_context.location.name`; the game
  stage remains the sole writer afterwards.
- `physical_states`/`mental_states` start empty (matches arch). Optional later
  enhancement: seed from `card.physical` / `card.wisdom`.

Refinement during implementation: drop the `_ = HumanMessage` line if unused;
keep the import only when a helper uses it. (Listed here because `classification`
in Phase 2 will need it, but Phase 1 must not import unused names to keep a clean
tree.)

---

## 5. Step 3 — `src/agents/engine/config.py`

```python
from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel


class EngineConfig(BaseModel):
    history_window: int = 10      # messages passed to game/narration prompts
    npc_window: int = 6           # npc_history window per NPC
    max_npc_parallelism: int = 4  # LangGraph max_concurrency for NPC fan-out
    sqlite_path: str = "data/engine_checkpoints.db"

    @classmethod
    def from_json(cls, path: str = "configs/engine.json") -> "EngineConfig":
        config_path = Path(path)
        if config_path.exists():
            return cls(**json.loads(config_path.read_text()))
        return cls()
```

`configs/engine.json` is optional and omitted in Phase 1.

---

## 6. Step 4 — `src/agents/engine/__init__.py`

```python
from .config import EngineConfig
from .state import (
    ActorInventory,
    Classification,
    GameState,
    initial_state,
    make_npc_msg,
    npc_history,
    turn_actions,
)

__all__ = [
    "EngineConfig",
    "ActorInventory",
    "Classification",
    "GameState",
    "initial_state",
    "make_npc_msg",
    "npc_history",
    "turn_actions",
]
```

---

## 7. Step 5 — `tests/test_engine_state.py`

Helpers (used by several tests):

```python
import asyncio

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from src.agents.engine.state import (
    GameState,
    initial_state,
    make_npc_msg,
    npc_history,
    turn_actions,
)
from src.baml_client.types import (
    CharacterArrangement,
    OpeningScene,
    PlayerCharacterCard,
    PlayerGender,
    Settlement,
    SpecificLocation,
    StartingContext,
    WorldConcept,
    WorldNarrative,
    WorldTypes,
)


def _card(name: str, items: list[str], money: int) -> PlayerCharacterCard:
    return PlayerCharacterCard(
        name=name,
        gender=PlayerGender.Male,
        occupation="wanderer",
        age=30,
        biography="b",
        physical="phys",
        wisdom="wis",
        strengths="st",
        weaknesses="wk",
        money=money,
        inventory=items,
    )


def fake_lore() -> dict:
    return {
        "world_type": WorldTypes(type="high fantasy", inspiration="test"),
        "world_concept": WorldConcept(
            magic=[], physics=["p"], society=["s"], geography=["g"], technology=["t"]
        ),
        "world_narrative": WorldNarrative(
            name="Testworld", history="h", current_state="c"
        ),
        "player_card": _card("Player", ["rope"], 10),
        "npc_card": _card("NPC", ["lantern"], 3),
        "context": StartingContext(
            region_name="R",
            region_description="d",
            settlement=Settlement(
                name="S", type="town", description="sd", background="sb"
            ),
            location=SpecificLocation(
                name="L",
                type="tavern",
                description="ld",
                atmosphere="la",
                notable_features=["f"],
            ),
        ),
        "arrangement": CharacterArrangement(
            player_circumstance="pc", npc_circumstance="nc", shared_situation="ss"
        ),
        "scene": OpeningScene(narrative="Opening scene.", immediate_hook="hook"),
    }


def base_state() -> GameState:
    return initial_state(fake_lore())


def base_input() -> dict:
    return {**base_state(), "raw_input": "look around"}
```

Tests:

```python
def test_make_npc_msg_id_is_deterministic():
    a = make_npc_msg("NPC", 1, "draws a blade")
    b = make_npc_msg("NPC", 1, "draws a blade")
    assert a.id == b.id
    assert a.id.startswith("npc:NPC:t1:")
    assert a.name == "NPC"
    assert a.additional_kwargs["turn_no"] == 1
    assert "ts" in a.additional_kwargs
    assert a.additional_kwargs["ts"] not in a.id


def test_make_npc_msg_id_changes_with_content_and_turn():
    a = make_npc_msg("NPC", 1, "draws a blade")
    b = make_npc_msg("NPC", 1, "draws a coin")
    c = make_npc_msg("NPC", 2, "draws a blade")
    assert len({a.id, b.id, c.id}) == 3


def test_add_messages_overwrites_same_id():
    from langgraph.graph.message import add_messages

    a = make_npc_msg("NPC", 1, "acts")
    b = make_npc_msg("NPC", 1, "acts")
    assert len(add_messages([], [a])) == 1
    merged = add_messages([a], [b])
    assert len(merged) == 1


def test_same_content_different_turns_yields_two_entries():
    a = make_npc_msg("NPC", 1, "acts")
    b = make_npc_msg("NPC", 2, "acts")
    from langgraph.graph.message import add_messages

    assert len(add_messages([a], [b])) == 2


def test_npc_history_filters_orders_and_windows():
    s = base_state()
    s["npc_actions"] = [
        make_npc_msg("A", 2, "a2"),
        make_npc_msg("B", 1, "b1"),
        make_npc_msg("A", 1, "a1"),
    ]
    assert [m.content for m in npc_history(s, "A")] == ["a1", "a2"]
    assert [m.content for m in npc_history(s, "B")] == ["b1"]
    assert [m.content for m in npc_history(s, "A", k=1)] == ["a2"]


def test_turn_actions_filters_and_sorts_by_name():
    s = base_state()
    s["npc_actions"] = [
        make_npc_msg("B", 1, "b"),
        make_npc_msg("A", 1, "a"),
        make_npc_msg("A", 2, "a2"),
    ]
    assert [m.content for m in turn_actions(s, 1)] == ["a", "b"]
    assert [m.content for m in turn_actions(s, 2)] == ["a2"]


def test_initial_state_maps_lore_and_seeds_runtime():
    st = initial_state(fake_lore())
    assert st["starting_context"].region_name == "R"
    assert st["current_location"] == "L"
    assert [c.name for c in st["npc_cards"]] == ["NPC"]
    assert st["inventories"]["Player"] == {"items": ["rope"], "money": 10}
    assert st["inventories"]["NPC"] == {"items": ["lantern"], "money": 3}
    assert st["turn_no"] == 0
    assert st["npc_actions"] == []
    assert len(st["messages"]) == 1
    assert st["messages"][0].id == "opening"
    assert st["messages"][0].content == "Opening scene."


def test_initial_state_drops_missing_lore_keys():
    lore = fake_lore()
    lore.pop("context")
    lore.pop("npc_card")
    st = initial_state(lore)
    assert "starting_context" not in st
    assert "current_location" not in st
    assert "npc_cards" not in st
    assert st["inventories"]["Player"] == {"items": ["rope"], "money": 10}


def test_inventories_reducer_merges_complete_actor_dicts():
    def a(state):
        return {"inventories": {"P": {"items": ["x"], "money": 1}}}

    def b(state):
        return {"inventories": {"N": {"items": ["y"], "money": 2}}}

    g = (
        StateGraph(GameState)
        .add_node("a", a)
        .add_node("b", b)
        .add_node("end", lambda s: {})
        .add_edge(START, "a")
        .add_edge(START, "b")
        .add_edge("a", "end")
        .add_edge("b", "end")
        .add_edge("end", END)
        .compile()
    )
    out = asyncio.run(g.ainvoke(base_input()))
    assert set(out["inventories"]) == {"P", "N"}
    assert out["inventories"]["P"]["items"] == ["x"]


def test_state_graph_smoke_renders_ascii():
    g = (
        StateGraph(GameState)
        .add_node("noop", lambda s: {})
        .add_edge(START, "noop")
        .add_edge("noop", END)
        .compile()
    )
    assert "noop" in g.get_graph().draw_ascii()


def test_baml_types_survive_checkpoint_roundtrip():
    g = (
        StateGraph(GameState)
        .add_node("noop", lambda s: {})
        .add_edge(START, "noop")
        .add_edge("noop", END)
        .compile(checkpointer=InMemorySaver())
    )
    cfg = {"configurable": {"thread_id": "roundtrip"}}
    asyncio.run(g.ainvoke(base_input(), cfg))
    values = g.get_state(cfg).values
    assert values["world_concept"].physics == ["p"]
    assert values["player_card"].name == "Player"
    assert values["inventories"]["N"]["money"] == 3
```

If `test_baml_types_survive_checkpoint_roundtrip` emits
`Deserializing unregistered type ... from checkpoint`, resolve it in Phase 1 by
configuring the serde (e.g. `JsonPlusSerializer(allowed_msgpack_modules=[...])`
or `pickle_fallback=True`); record the choice in the Phase 2 plan.

---

## 8. Step 6 — Acceptance

Run from the repo root:

```bash
uv run baml-cli generate --from=src/baml_src
uv run pytest tests/test_engine_state.py -q
```

Expected: generation succeeds and all tests pass.

Manual smoke:

```bash
uv run python - <<'PY'
import asyncio
from langgraph.graph import END, START, StateGraph
from src.agents.engine.state import GameState, initial_state

st = initial_state({
    "player_card": None,
    "scene": None,
})
g = StateGraph(GameState).add_node("noop", lambda s: {}).add_edge(START, "noop").add_edge("noop", END).compile()
print(g.get_graph().draw_ascii())
PY
```

(`initial_state` must tolerate missing lore keys; this exercises the
`NotRequired` contract. The `initial_state` dict above has no `npc_card`, so
`inventories` must be empty and no error raised.)

---

## 9. Deferred (do not implement in Phase 1)

- `graph.py`, `nodes.py`, `npc.py`, `Engine` class — Phase 2/3.
- `NpcSubgraphState` — removed (D1).
- `AsyncSqliteSaver`, `data/` directory, streaming, prompts — Phase 2/3.
- Arch/plan doc update to v1.2 (D6) — do after Phase 1 is green.

## 10. Risks / gotchas

| Risk | Mitigation |
|------|------------|
| BAML generation fails on `-> string` + `ctx.output_format` | If so, drop `{{ ctx.output_format }}` for the three `-> string` functions; keep for structured returns. |
| `or_` merges instead of replaces | Game stage must return complete actor dicts; document in Phase 2. |
| Pydantic/BAML type serialization | Covered by the round-trip test; fix serde in Phase 1 if it warns. |
| `initial_state` `type: ignore` on dynamic key write | Acceptable; alternatively build the dict explicitly. |
| `.env` missing `GAME_*_LLM` | Generation does not need them; runtime (Phase 2/3) does. Add before running any node. |

---

## 11. Implementation notes (post-execution)

Two deviations were made while implementing Phase 1:

1. **Added `src/agents/engine/serde.py`** with `build_serde()` (exported from
   `__init__.py`). The round-trip test showed `JsonPlusSerializer` warns on every
   BAML Pydantic model/enum and will block them in a future version. `build_serde()`
   registers all classes generated into `src.baml_client.types` via
   `allowed_msgpack_modules`. The round-trip test now uses
   `InMemorySaver(serde=build_serde())` and runs warning-free. Phase 2's `Engine`
   must use `build_serde()` when constructing `AsyncSqliteSaver`.
2. **Smoke test renders Mermaid, not ASCII.** `graph.get_graph().draw_ascii()`
   raises `ImportError: Install grandalf` — ASCII rendering needs an extra
   dependency. The smoke test uses `draw_mermaid()` (dependency-free). Add
   `grandalf` only if ASCII rendering is actually wanted.

Confirmed results:
- `uv run baml-cli generate --from=src/baml_src` → 14 files written, new types present.
- `uv run pytest tests/test_engine_state.py -q` → **11 passed**.
- `EngineConfig()`, package imports, and `initial_state` tolerant of missing lore keys verified.

