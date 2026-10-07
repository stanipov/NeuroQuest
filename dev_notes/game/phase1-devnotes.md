# Game Engine — Phase 1 Development Notes

Date: 2026-09-17
Branch: `dev/v2`
Plan: `dev_notes/game/phase1.md` (v1.1) — implemented in full.
Environment: Python 3.14.7, `langgraph 1.2.9`, `baml-py 0.222.0`,
`langgraph-checkpoint-sqlite 3.1.1`, `pytest 9.1.1`, `pytest-asyncio 1.4.0`.

## Status

Phase 1 complete and green.

```
uv run baml-cli generate --from=src/baml_src   # 14 files written, new types present
uv run pytest -q                               # 11 passed
```

Package imports, `EngineConfig()`, and `initial_state` tolerance for missing lore
keys verified manually.

## What was implemented

### Dependencies (`uv add`, not pip)

- `langgraph-checkpoint-sqlite 3.1.1` (pulls `aiosqlite 0.22.1`, `sqlite-vec 0.1.9`).
- dev group: `pytest 9.1.1`, `pytest-asyncio 1.4.0`.

`pyproject.toml` gained:

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
pythonpath = ["."]
testpaths = ["tests"]
```

### BAML

- `src/baml_src/engine.baml` (new):
  - enums/types: `InputDecision`, `InputClassification`, `InventoryDelta`,
    `StateDelta`, `GameResolve`.
  - functions (stub prompts, frozen signatures): `ClassifyInput`, `NpcAct`,
    `ResolveGame`, `AnswerBrief`, `NarrateTurn`.
- `src/baml_src/clients.baml` (appended): `GameLLM` (temp 0.8),
  `GameNarrateLLM` (temp 0.6), both `openai-generic` on `env.BASE_URL` /
  `env.API_KEY` with model vars `env.GAME_GENERIC_LLM` / `env.GAME_NARRATE_LLM`.
- Generated into `src/baml_client/` (14 files). New symbols present in
  `types.py` and `async_client.py`.

Note: `GAME_GENERIC_LLM` and `GAME_NARRATE_LLM` are not yet set in `.env`; only
needed at Phase 2/3 runtime, not for generation or Phase 1 tests.

### Engine package (`src/agents/engine/`)

| File | Contents |
|------|----------|
| `state.py` | `GameState`, `ActorInventory`, `Classification`, `make_npc_msg`, `npc_history`, `turn_actions`, `initial_state` |
| `config.py` | `EngineConfig` (`history_window`, `npc_window`, `max_npc_parallelism`, `sqlite_path`) + `from_json` |
| `serde.py` | `build_serde()` — `JsonPlusSerializer` with all generated BAML types allowlisted |
| `__init__.py` | exports the above |

Implementation choices (locked decisions D1–D3 from the plan):
- No `NpcSubgraphState`; NPC fan-out will be a plain node + full-state `Send`.
- `initial_state(lore)` does **not** take `raw_input`. It seeds
  `messages=[AIMessage(scene.narrative, id="opening")]` and seeds
  `inventories` from the player + NPC cards. `turn_no=0`, `npc_actions=[]`,
  `physical_states={}`, `mental_states={}`, `current_location` from
  `lore["context"].location.name`.
- `make_npc_msg` id: `npc:{name}:t{turn}:{blake2b(content, digest_size=8).hexdigest()}`
  (16 hex chars); `ts` lives in `additional_kwargs` only.
- `or_` = `operator.or_` (dict merge, right wins per key). Game stage must return
  complete per-actor dicts.

### Tests (`tests/test_engine_state.py`, 11 tests)

Deterministic IDs, `add_messages` append/overwrite, per-turn duplicates,
`npc_history` filter/order/window, `turn_actions` filter/order, `initial_state`
mapping + missing-key tolerance, `or_` reducer merge, smoke graph render, and an
async BAML-type checkpointer round-trip.

## Deviations from the plan

1. **Added `serde.py` / `build_serde()` (plan §7 anticipated this).** The
   round-trip test produced one warning per BAML type:

   ```
   WARNING langgraph.checkpoint.serde.jsonplus: Deserializing unregistered type
   src.baml_client.types.<X> from checkpoint. This will be blocked in a future
   version. Set LANGGRAPH_STRICT_MSGPACK=true to block now, or add to
   allowed_msgpack_modules ...
   ```

   `build_serde()` builds `JsonPlusSerializer(allowed_msgpack_modules=<classes>)`
   by introspecting `src.baml_client.types`. The test now constructs
   `InMemorySaver(serde=build_serde())` and runs warning-free.
   **Phase 2's `Engine` must use `build_serde()` when constructing
   `AsyncSqliteSaver`.**
2. **Smoke test uses `draw_mermaid()`, not `draw_ascii()`.** `draw_ascii()`
   raises `ImportError: Install grandalf to draw graphs`. Mermaid rendering is
   dependency-free. Add `grandalf` only if ASCII output is genuinely wanted.

One test assertion was corrected during execution: the `or_` merge test's input
state already contains `Player`/`NPC` inventories, so the merged key set is
`{"Player", "NPC", "P", "N"}` (`or_` merges, it does not replace — expected).

## Empirical findings that drove the design

These were verified against `langgraph 1.2.9` while reviewing the v1.1 specs and
are why Phase 1 deviates from the architecture doc:

- `Send` to a shared-state **subgraph** passes only the Send payload as the
  subgraph input — the subgraph does **not** see parent channels.
  - `Send("sub", {"my_card": c})` → subgraph sees `foo=None`, `messages=[]`.
  - `Send("sub", {**state, "my_card": c})` with two parallel sends → parent
    `InvalidUpdateError: At key 'foo': Can receive only one value per step`.
  - Same full-state payload to a **plain node** fan-out works.
- Router returning `[]` from an empty map-reduce fan-out silently ends the graph;
  it does **not** advance to a downstream node. Phase 3 must explicitly route the
  empty-NPC case to `game_response`.
- `stream_mode="v2"` is currently accepted by 1.2.9, but the documented API is
  `stream_mode="updates", version="v2"`. Don't propagate the former.

## Gotchas for Phase 2 / Phase 3

- `StateGraph(GameState).compile()` with no nodes raises
  `ValueError: Graph must have an entrypoint` — always compile a graph with at
  least one START edge.
- BAML `-> str` functions with `{{ ctx.output_format }}` generated and imported
  fine; no fallback needed.
- `AsyncSqliteSaver.from_conn_string(path)` takes a filesystem path, then
  `await saver.setup()` inside an `async with`. It is **not** a
  `sqlite+aiosqlite://` URL.
- `data/` does not exist yet; `EngineConfig.sqlite_path` defaults to
  `data/engine_checkpoints.db` and the Engine will need to create the directory.
- Streaming: all LLM I/O is BAML, so LangGraph `stream_mode="messages"` emits
  nothing. Narration streaming will need `get_stream_writer()` (present in
  1.2.9) fed by BAML's `BamlStream`.
- `baml_client/` is gitignored (regenerated), so `uv run baml-cli generate` must
  be part of any fresh setup.

## Uncommitted files at end of Phase 1

```
 M pyproject.toml
 M src/baml_src/clients.baml
 M uv.lock
?? src/baml_src/engine.baml
?? src/agents/engine/
?? tests/
```

(Also untracked pre-existing: `.opencode/`, `AGENTS.md`, `dev_notes/`,
`dev_notes/instructions/engine.md`, `tmp/`.)

## Next

Phase 2 — `nodes.py` (`classification` with `turn_no` bump + `HumanMessage`
append; `narration` skeleton), `graph.py` routing (`valid | clarification |
invalid`), and the `Engine` class (owns `AsyncSqliteSaver` via `build_serde()`,
`compile(checkpointer=...)`, `thread_id` config).
