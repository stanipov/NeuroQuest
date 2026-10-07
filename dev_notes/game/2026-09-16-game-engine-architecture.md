# Game Engine Graph — Architecture (v1.3, 2026-10-07)

Status: frozen for first iteration. Game response internals TBD (single vs. split).

Changelog vs v1.2 (2026-10-06):
- Phase 3 shipped. NPC fan-out is wired as a plain `npc` node reached from
  `classification` by a full-state `Send`; `npc → game_response` is the barrier.
  Zero NPC cards route straight to `game_response` (an empty `Send` list ends
  the graph). `initial_state` still maps the single `lore["npc_card"]`.
- `game_response` is wired to a single `b.ResolveGame` call and applies
  `InventoryDelta`/`StateDelta` as **complete per-actor dicts** (`or_` merges per
  key); `current_location` follows the player only.
- `npc_act` catches its own errors and writes nothing on a no-op; only
  `game_response`, `brief`, and `narration` failures propagate.
- `max_concurrency` is wired from `EngineConfig.max_npc_parallelism`.

Changelog vs v1.1 (2026-09-17):
- NPC fan-out is a **plain node** taking a full-state `Send` payload, not a
  shared-state subgraph. `NpcSubgraphState` is removed. `Send("npc", {**state,
  "my_card": card})`; `npc_act` writes only the reducer-backed `npc_actions`.
- `classification` owns the per-turn input: it bumps `turn_no` **and** appends
  `HumanMessage(raw_input, id=f"user:t{turn}")`. `initial_state(lore)` no longer
  receives `raw_input`; it seeds the opening `AIMessage(scene.narrative,
  id="opening")`.
- Checkpointer is `AsyncSqliteSaver` constructed from an engine-owned
  `aiosqlite.connect(path)` with `serde=build_serde()`. Its
  `from_conn_string(path)` helper does not accept `serde` and constructs the
  saver inside its own context manager, so the Engine opens the connection
  itself (also required because the saver captures the running loop at
  construction).
- Streaming: narration is the only streaming point, driven by
  `get_stream_writer()` fed from `b.stream.NarrateTurn`. The Engine uses
  `stream_mode=["updates", "custom"], version="v2", subgraphs=False`.

Changelog vs v1 (2026-09-16):
- `NpcMsg` TypedDict dropped. NPC intents are now a flat `list[AIMessage]` with
  `name=npc_name`, merged by `add_messages`. Dict key + custom `merge_npc_messages` removed.
- Added `turn_no: int` to `GameState` (exactly-once increment in classification).
- NPC message IDs are deterministic: `npc:{name}:t{turn}:blake2b(content)`.
  Wall-clock timestamp lives in `additional_kwargs`, never in the ID (retry safety).
- No-op NPC = no write (not an appended empty message).
- Checkpointer confirmed: `AsyncSqliteSaver` (async SQLite). Custom per-session
  tables from `dev_notes/instructions/engine.md` Notes are rejected.

## Topology

START → classification → valid → NPC intents (×N, parallel) → game response stage → narration → END
                     → clarification → brief → narration → END
                     → invalid → narration → END

- One entry (classification), one exit (narration).
- Narration is the only user-visible output and the only streaming point.
- Invalid carries no intermediate node; narration explains refusal from classification reasoning.

## State

```python
Classification = Literal["valid_action", "clarification", "invalid"]

class ActorInventory(TypedDict):
    items: list[str]
    money: int

class GameState(TypedDict):
    # Lore — set once at init, never written by nodes
    world_type: NotRequired[WorldTypes]
    world_concept: NotRequired[WorldConcept]
    world_narrative: NotRequired[WorldNarrative]
    starting_context: NotRequired[StartingContext]   # mapped from lore `context`
    arrangement: NotRequired[CharacterArrangement]
    scene: NotRequired[OpeningScene]
    player_card: NotRequired[PlayerCharacterCard]
    npc_cards: NotRequired[list[PlayerCharacterCard]]

    # Runtime — checkpointed, mutated across turns
    messages: Annotated[list[AnyMessage], add_messages]
    npc_actions: Annotated[list[AIMessage], add_messages]  # flat; msg.name = npc name
    inventories: Annotated[dict[str, ActorInventory], or_]
    physical_states: Annotated[dict[str, str], or_]
    mental_states: Annotated[dict[str, str], or_]
    current_location: NotRequired[str]
    turn_no: int                                     # bumped once per turn in classification

    # Turn scratch
    raw_input: str                                   # required graph input
    classification: NotRequired[Classification]
    classification_reason: NotRequired[str]
    invalid_reason: NotRequired[str]
    game_action: NotRequired[str]                    # terse stage summary
    brief_answer: NotRequired[str]
    narration: NotRequired[str]                      # final, only streaming output
```

- BAML types from `src/baml_client/types.py` (same imports as `LorePipelineState`).
- `npc_actions`: flat list of `AIMessage`, one per acting NPC per valid turn.
  Convention: `content` = terse intent, `name` = NPC name,
  `additional_kwargs = {"turn_no": int, "ts": iso_timestamp}`.
- Message IDs (built by `make_npc_msg()`, stdlib `hashlib.blake2b`, no new dep):
  `f"npc:{npc_name}:t{turn_no}:{blake2b(content, digest_size=8).hexdigest()}"`.
  Deterministic per (turn, NPC, content), so a retried node overwrites via
  `add_messages` ID match instead of duplicating. Timestamp is metadata only:
  same-ms parallel fan-out and retry idempotency both break if time is in the ID.
- No-op NPC writes nothing (no empty-content messages in checkpointed state).
- Reducers: `messages` / `npc_actions` append-or-update by ID (`add_messages`);
  `inventories` / `physical_states` / `mental_states` replace per actor
  (`or_`, game stage returns complete actor dicts).
- Read helpers (in `state.py`): `npc_history(state, npc_name, k)` filters on
  `name`, sorts by `turn_no`; `turn_actions(state, turn_no)` filters on
  `additional_kwargs["turn_no"]`, sorts by `name` (parallel completion order
  is nondeterministic — never rely on list position).
- Init (`initial_state(lore, raw_input)`): `lore["context"] → starting_context`;
  `lore["npc_card"] → npc_cards[0]` (or `lore["npc_cards"]` when pipeline grows);
  drop `None` lore keys; seed `inventories` from cards; `turn_no=0`;
  `messages=[HumanMessage(raw_input)]`, `npc_actions=[]`, states empty.

## NPC fan-out (plain node)

NPC fan-out is a **plain node** (`npc_act`), not a shared-state subgraph. A
`Send` to a shared-state subgraph exposes only the payload as the subgraph input
and fails on non-reducer channels; a plain node receives the payload directly.

```python
class NpcInput(GameState):
    my_card: PlayerCharacterCard   # identity only; not a parent channel
```

- Fan-out: `route_classification` returns
  `[Send("npc", {**state, "my_card": card}) for card in state["npc_cards"]]`.
  The payload is the **full state** (the plain node's input replaces the graph
  state), so every shared channel the node reads is present.
- Per-NPC prompt context = `build_context(state, cfg)` (lore + runtime + recency
  history) plus `npc_history(state, my_card.name, k=cfg.npc_window)`.
  Windowing at read time; no checkpoint pruning in v1.
- Writes: only shared `npc_actions` (one `AIMessage` per acting NPC). The NPC
  path never writes inventories/states, and never writes `my_card` back.
- Parallel supersteps are transactional: one NPC failure fails the step, so
  `npc_act` catches BAML errors internally and skips the write.
- Empty NPC set routes directly to the game stage (returning `[]` from the
  router silently ends the graph, so the router returns `"game_response"`).
- `npc → game_response` is the barrier edge: the game stage runs once, after all
  NPC tasks complete.
- Node I/O: classification reads lore + history + input → writes decision + reasons
  (+ `turn_no` bump); `npc_act` reads full state + card → writes `npc_actions`;
  game stage reads intents + runtime → writes `game_action` + runtime; brief reads
  lore + input → writes `brief_answer`; narration reads decision + branch outputs →
  writes `narration` + message append.

## Nodes

- **Classification.** Valid in-world action vs. question about the world vs.
  world-rule violation, with brief reasoning. No side effects (besides `turn_no` bump).
- **NPC intent.** Per-NPC terse intent or no-op (no write), faithful to card
  and world. No shared-state authority. Parallel fan-out.
- **Game response stage.** Sole authority for inventory, location, physical/mental
  states + terse turn summary. v1 = single step, e.g.
  `ResolveGame → {terse, inventory_deltas, state_deltas, location?}`. May split into
  focused steps (inventory / states / location / summary) if one LLM call proves
  unreliable; stage boundary stays fixed.
- **Brief.** Terse lore-grounded answer (1–3 sentences), no narration.
- **Narration.** Final Markdown for all three paths. Merges NPC intents + game
  summary, or renders brief answer, or renders invalid refusal.

## Cross-cutting

- Persistence via LangGraph checkpointer + thread id. `AsyncSqliteSaver`
  (`langgraph-checkpoint-sqlite`, `sqlite+aiosqlite:///...`, `await setup()`),
  owned with `async with` lifecycle by the Engine class; `InMemorySaver` for tests.
  No custom session tables.
- LLM I/O via BAML per responsibility (gateway, NPC act, game resolve, brief, narrate).
  BAML functions stay `str`-typed; nodes wrap `str → AIMessage`.
- History derived from stored messages per call (recency window); per-NPC context
  policies deferred (data concern, not arch).
- Game stage runs as barrier after all NPC tasks complete.

## Phasing

1. State + init + ID scheme + read helpers + stage contract. — done (Phase 1)
2. Classification + routing + narration skeleton. — done (Phase 2)
3. NPC fan-out + game stage (single) + brief. — done (Phase 3)
4. Smoke valid / clarification / invalid on persisted threads; lore regression;
   retry idempotency via deterministic IDs.
5. Split game stage only on observed quality failure.

## Deferred

NPC context tuning, N-NPC lore generation, TUI, eval harness, checkpoint retention.
