# Game Engine — Implementation Plan (v1.3, 2026-10-07)

Authoritative spec: `dev_notes/game/2026-09-16-game-engine-architecture.md` (v1.3).
LangGraph mechanics verified against LangChain docs MCP (`use-subgraphs`,
`graph-api#send`, `use-graph-api#messagesstate`, `persistence`, `checkpointers`)
and empirically against `langgraph 1.2.9` (see `phase1.md`, `phase2.md`,
`phase3.md`).

Changelog vs v1.2 (2026-10-06):
- Phase 3 shipped `src/agents/engine/npc.py` and the real `game_response`/`brief`
  nodes; details in `phase3.md` + `phase3-devnotes.md`.
- NPC fan-out is a plain-node full-state `Send` with an `npc → game_response`
  barrier; the zero-NPC valid path routes straight to `game_response`.
- `game_response` applies deltas as complete per-actor dicts; `current_location`
  follows the player only.
- `max_concurrency` is wired from `EngineConfig.max_npc_parallelism`.

Changelog vs v1.1 (2026-09-17):
- Phase 1 shipped `state.py`, `config.py`, `serde.py`, and the BAML contract in
  full; deviations are recorded in `phase1.md` §11.
- Phase 2 shipped `nodes.py`, `graph.py`, and the `Engine` class; decisions and
  empirical findings are recorded in `phase2.md`.
- NPC fan-out is a plain node with a full-state `Send` (no `NpcSubgraphState`);
  its node name and the `game_response` stage boundary stay fixed.
- The `Engine` owns `aiosqlite.connect` + `AsyncSqliteSaver(conn,
  serde=build_serde())` because `from_conn_string` cannot carry `serde`.

## §0. Decisions locked in this plan

| # | Decision | Rationale |
|---|----------|-----------|
| 1 | `npc_actions: Annotated[list[AIMessage], add_messages]`, `name=npc_name`; `NpcMsg`/dict key/`merge_npc_messages` dropped | Native ID-aware merging; per-NPC filter via `name` |
| 2 | `turn_no: int` on state, bumped in classification | ID uniqueness + turn filtering; `len(messages)` skewed by clarification/invalid turns |
| 3 | ID = `npc:{name}:t{turn}:{blake2b(content)[:16]}`, stdlib only, no xxhash | Deterministic retry (ID match → overwrite, not duplicate); no new dep |
| 4 | Timestamp in `additional_kwargs` only, never in ID | Same-ms fan-out collisions; retry duplication; test determinism |
| 5 | NPC no-op = no write | Empty messages pollute checkpointed history + prompt windows |
| 6 | `AsyncSqliteSaver` + `thread_id`; custom per-session tables rejected | Frozen arch; parent checkpointer propagates to subgraphs |
| 7 | BAML stays `str`-typed; nodes wrap `str → AIMessage` | BAML need not know LangChain types |
| 8 | Layout `src/agents/engine/` mirroring `src/agents/lore/` | Follows existing `world_gen`/`start_loc`/`pipeline` precedent |

## Phase 1 — State + init + ID scheme + stage contract

Files: `src/agents/engine/{__init__.py, state.py, config.py}`, `src/baml_src/engine.baml` (stubs),
`tests/test_engine_state.py`.

- [ ] `state.py`: `Classification`, `ActorInventory`, `GameState` (per arch),
  `NpcSubgraphState`, `or_` reducer, `make_npc_msg(npc_name, turn_no, content)`,
  `npc_history(state, npc_name, k)`, `turn_actions(state, turn_no)`,
  `initial_state(lore, raw_input)`.
- [ ] `engine.baml`: stub signatures `ClassifyInput`, `NpcAct`, `ResolveGame`,
  `AnswerBrief`, `NarrateTurn`; new `GameLLM` clients (own temps) in `clients.baml`
  style; `uv run baml-cli generate --from=src/baml_src`.
- [ ] `config.py`: `EngineConfig` (history window `k`, max NPC parallelism,
  SQLite path) mirroring `src/agents/lore/pipeline/config.py`.
- [ ] Tests: `add_messages` append on distinct IDs / overwrite on same ID;
  same content different turns → 2 entries; same (turn, npc, content) retry → 1 entry;
  no-op writes nothing; `npc_history`/`turn_actions` filtering + ordering;
  `initial_state` mapping (`context→starting_context`, `npc_card→npc_cards[0]`,
  inventory seeding, `turn_no=0`).
- Acceptance: `StateGraph(GameState).compile().get_graph().draw_ascii()` renders;
  `uv run pytest tests/test_engine_state.py` green.

## Phase 2 — Classification + routing + narration skeleton

Files: `src/agents/engine/{nodes.py, graph.py}`.

- [ ] `classification` node: `await b.ClassifyInput(...)` → decision + reasons +
  `turn_no` bump. No side effects otherwise.
- [ ] `route` conditional edges → `valid | clarification | invalid`
  (pattern: `src/agents/lore/world_gen/agent.py:101`).
- [ ] `narration` node skeleton: three-path Markdown render + append narration
  `AIMessage` to `messages`. Only streaming point (`subgraphs=False`).
- [ ] `Engine` class: owns `AsyncSqliteSaver` lifecycle (`async with`,
  `await setup()`), `compile(checkpointer=...)`, `ainvoke`/`astream` with
  `{"configurable": {"thread_id": ...}}`; lore passed on first invoke only.
- Acceptance: clarification + invalid paths end-to-end on throwaway threads
  with stubbed brief; narration streams, nothing else does.

## Phase 3 — NPC fan-out + game stage (single) + brief

Files: `src/agents/engine/npc.py`, extend `nodes.py`, `graph.py`.

- [x] Router returns `[Send("npc", {**state, "my_card": card})]` per card (plain
  node, **not** a compiled subgraph); `npc → game_response` barrier edge; empty
  NPC set → straight to game stage (never return `[]`).
- [x] `npc_act` node (`NpcInput` payload): context = `build_context(...)` +
  `npc_history(card.name, k)`; `await b.NpcAct(...)` → `make_npc_msg(...)` or skip
  on `""`/error (try/except inside node — parallel superstep is transactional).
- [x] `game_response` node: single `await b.ResolveGame(...)` →
  `game_action` + complete per-actor `inventories`/`physical_states`/`mental_states`
  dicts + `current_location` (player-only). Sole writer of runtime.
- [x] `brief` node: `await b.AnswerBrief(...)` → 1–3 sentences.
- Acceptance: valid turn with 1 NPC produces 1 `npc_actions` entry with correct
  `name`/`id`/`turn_no`; game deltas applied per actor; `max_concurrency` honored.
  — met (42 tests green; live check deferred to Phase 4.)

## Phase 4 — Smoke + regression + idempotency

- [ ] Persistent-thread smoke: valid / clarification / invalid across 2+ turns on
  `AsyncSqliteSaver`; resume after process restart; fixed lore fixture
  (via `LorePipelineAgent.from_json` output shape) for regression.
- [ ] Retry test: re-invoke same turn after killing one NPC branch → no duplicate
  `npc_actions` (deterministic ID overwrite); pending-writes recovery observed.
- [ ] Regression gate: lore fixture output unchanged; `InMemorySaver` unit path
  stays green for CI (no SQLite file needed).
- Acceptance: all three paths narrate correctly; checkpoint holds full
  `messages` + `npc_actions` + runtime per turn.

## Phase 5 — Split game stage (conditional)

Trigger only: single `ResolveGame` call observably drops inventory/state/location
updates on smoke. Then split into inventory / states / location / summary nodes
inside the stage; node name `game_response` and its inbound/outbound edges stay fixed.

## Deferred (non-goals)

NPC context tuning beyond recency window, N-NPC lore generation, TUI/`rich`,
eval harness, checkpoint retention/pruning policy.

## File map (final)

```text
src/agents/engine/__init__.py
src/agents/engine/state.py      # GameState, reducers, make_npc_msg, helpers, initial_state
src/agents/engine/nodes.py      # classification, game_response, brief, narration
src/agents/engine/npc.py        # NpcInput + npc_act (plain fan-out node)
src/agents/engine/graph.py      # StateGraph wiring + Engine (checkpointer lifecycle)
src/agents/engine/config.py     # EngineConfig
src/baml_src/engine.baml        # ClassifyInput, NpcAct, ResolveGame, AnswerBrief, NarrateTurn
tests/test_engine_state.py
tests/test_engine_graph.py
```
