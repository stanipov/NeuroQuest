# Game Engine — Phase 2 Development Notes

Date: 2026-10-06
Branch: `dev/v2`
Plan: `dev_notes/game/phase2.md` — implemented in full.
Environment: Python 3.14.7, `langgraph 1.2.9`, `baml-py 0.222.0`,
`langgraph-checkpoint-sqlite 3.1.1`, `aiosqlite 0.22.1`, `pytest 9.1.1`.

## Status

Phase 2 complete and green.

```
uv run pytest -q   # 25 passed (11 Phase 1 + 14 Phase 2)
```

Graph renders; real-SQLite `Engine` seeding verified without any LLM call.

## What was implemented

| File | Contents |
|------|----------|
| `src/agents/engine/nodes.py` | `build_context`, `classification`, `route_classification`, `game_response` (stub), `brief` (stub), `narration` |
| `src/agents/engine/graph.py` | `NodeFns`, `default_node_fns`, `build_graph`, `Engine` |
| `src/agents/engine/__init__.py` | extended exports (`Engine`, `NodeFns`, `build_graph`, `default_node_fns`, node functions, `build_context`) |
| `tests/test_engine_graph.py` | 14 deterministic tests (routing, turn accounting, streaming, seeding, SQLite persistence, real-node BAML stubs) |
| `.env` | added `GAME_GENERIC_LLM`, `GAME_NARRATE_LLM` (gitignored) |

Topology wired exactly as planned:

```
START → classification ─┬─ valid         → game_response* → narration → END
                         ├─ clarification → brief*         → narration → END
                         └─ invalid       → narration       → END
```

`*` deterministic stub in Phase 2; Phase 3 replaces the bodies only.

### Key implementation choices

- **Config injection into nodes.** `classification` / `narration` are
  module-level `async def (state, cfg)`; `default_node_fns(cfg)` binds `cfg` via
  `functools.partial`. Tests pass a `NodeFns` bundle of fakes, so no BAML global
  monkeypatching is needed for graph tests.
- **Deterministic IDs.** `classification` appends
  `HumanMessage(id=f"user:t{turn}")`; `narration` appends
  `AIMessage(name="narrator", id=f"narrator:t{turn}")`. Both are retry-stable via
  `add_messages`.
- **Streaming.** `narration` emits incremental suffixes
  `{"narration_token": <suffix>}` through `get_stream_writer()`, with a snapshot
  fallback when a BAML partial is not an extension of the previous one. The final
  node update carries the full `narration`.
- **Engine lifecycle.** `__aenter__` (inside the running loop) opens
  `aiosqlite.connect(sqlite_path)` (creating the parent dir), builds
  `AsyncSqliteSaver(conn, serde=build_serde())`, `await setup()`, and compiles.
  `__aexit__` closes the connection. A `checkpointer=` injection lets unit tests
  use `InMemorySaver(serde=build_serde())`.
- **Seeding.** `new_game(lore)` writes `initial_state(lore)` via
  `aupdate_state(..., as_node=START)`; `turn` / `stream_turn` send only
  `{"raw_input": ...}`.

### Real-node tests (BAML stubbed)

`tests/test_engine_graph.py` replaces `src.agents.engine.nodes.b` with a
`SimpleNamespace` fake and stubs `get_stream_writer` to assert:
- decision → `Classification` mapping and `invalid_reason` handling;
- `turn_no` bump + `user:t{turn}` message;
- cumulative BAML partials `["Hel", "Hello"]` → emitted deltas `["Hel", "lo"]`,
  final `"Hello"`, `narrator:t{turn}` message.

## Deviations from the plan

1. **Added `default_node_fns` to `__init__` exports** (plan §6 listed `NodeFns`,
   `build_graph`, and the node functions). Trivial, improves testability.
2. **Plan §8's helper sketch omitted the `HumanMessage` append** in the fake
   classification node; the fixture was made faithful to the real node so the
   turn-accounting assertions hold.
3. **`ctx.output_format` prompt tweak not applied.** It is conditional on live
   output being noisy; no live LLM smoke was run (see below), so the three
   `-> string` functions are unchanged. No BAML regeneration was needed.
4. **`build_context` role labels** use `getattr(msg, "type", ...)` mapped to
   `player` / `narrator` / NPC name, rather than importing concrete message
   classes.

## Empirical findings (already in `phase2.md` §2)

Confirmed while implementing/verifying:

- `AsyncSqliteSaver.from_conn_string(path)` yields `cls(conn)` and cannot carry
  `serde`; constructing `AsyncSqliteSaver(conn, serde=build_serde())` works.
- `aupdate_state(cfg, values, as_node=START)` on a fresh thread succeeds, and a
  later partial `ainvoke({"raw_input": ...})` retains every seeded channel.
- `astream(..., stream_mode=["updates", "custom"], version="v2",
  subgraphs=False)` yields `{"type": "custom"/"updates", "ns": (), "data": ...}`.
- `AsyncSqliteSaver.__init__` captures the running loop → construct inside
  `__aenter__`.

## Verification

```
uv run pytest -q                      # 25 passed
uv run python -m compileall ...       # clean
python: build_graph(...).draw_mermaid() shows classification/game_response/brief/narration
python: Engine(cfg) seeds real SQLite tmp db and reads state back
```

`ruff` is not installed in the project environment, so no lint run.

## Not done (deferred / follow-up)

- **Live LLM smoke** (`§9` of the plan) was not run: it needs the local
  OpenAI-compatible server and `GAME_*_LLM`. Once available, observe narration
  streaming and decide whether to drop `{{ ctx.output_format }}` from
  `NarrateTurn` / `AnswerBrief` / `NpcAct`.
- Phase 3: `npc.py` fan-out with full-state `Send`, real `b.ResolveGame`,
  real `b.AnswerBrief`, `max_npc_parallelism`.

## Uncommitted files at end of Phase 2

```
 M pyproject.toml
 M src/baml_src/clients.baml
 M uv.lock
?? .opencode/
?? AGENTS.md
?? dev_notes/game/            (incl. phase2.md, this file)
?? dev_notes/instructions/engine.md
?? src/agents/engine/         (nodes.py, graph.py added)
?? src/baml_src/engine.baml
?? tests/
?? tmp/
```

`.env` is gitignored and was updated locally with the two `GAME_*_LLM` vars.
