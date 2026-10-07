# Game Engine — Phase 3 Development Notes

Date: 2026-10-07
Branch: `dev/v2`
Plan: `dev_notes/game/phase3.md` — implemented in full.
Environment: Python 3.14.7, `langgraph 1.2.9`, `baml-py 0.222.0`,
`langgraph-checkpoint-sqlite 3.1.1`, `aiosqlite 0.22.1`, `pytest 9.1.1`,
`ruff 0.16.10`.

## Status

Phase 3 complete and green.

```
uv run pytest -q                     # 42 passed (11 Phase 1 + 14 Phase 2 + 17 Phase 3)
uv run ruff check src/agents/engine tests   # All checks passed!
```

## What was implemented

| File | Change |
|------|--------|
| `src/agents/engine/npc.py` (new) | `NpcInput(GameState)`, `_npc_history_text`, `npc_act` |
| `src/agents/engine/nodes.py` | `route_classification` fan-out via `Send`; `_known_actors`, `_apply_inventory_deltas`, `_apply_state_deltas`, `_intents_text`; real `game_response`; real `brief` |
| `src/agents/engine/graph.py` | `NodeFns.npc`; `npc` node; `npc → game_response` barrier; explicit conditional destinations; `max_concurrency` in `_cfg` |
| `src/agents/engine/__init__.py` | export `NpcInput`, `npc_act` |
| `tests/test_engine_npc.py` (new) | 17 deterministic tests |
| `tests/test_engine_graph.py` | `NodeFns` gains the `npc` fake |
| `pyproject.toml`, `uv.lock` | `ruff` added to the dev dependency group |

Topology wired exactly as planned:

```
START → classification ─┬─ valid ─ Send("npc", {**state,"my_card":card}) ×N ─→ npc ─┐
                         │        (0 NPCs) ───────────────────────────────────────→ game_response → narration → END
                         ├─ clarification → brief → narration → END
                         └─ invalid       → narration → END
```

### Key implementation choices

- **Fan-out payload is the full state.** `route_classification` returns
  `[Send("npc", {**state, "my_card": card}) for card in state["npc_cards"]]`.
  The zero-NPC case returns the string `"game_response"` — an empty `Send` list
  ends the graph (Phase 1 finding).
- **`npc_act` writes only `npc_actions`.** A no-op (empty/whitespace intent)
  writes nothing; any exception from `b.NpcAct` is caught, logged, and skipped
  so the parallel superstep does not fail as a unit.
- **`game_response` returns complete per-actor dicts.** `inventories` is merged
  by `or_` per actor key, so the node rebuilds each changed actor's full
  `{"items", "money"}` rather than a partial delta. `physical_states` /
  `mental_states` are partial dicts (one key per changed actor). `current_location`
  is written only for the player card's `StateDelta.location`; NPC locations are
  ignored (P3.2).
- **Unknown actors are ignored** with a printed warning.
- **`max_concurrency` is top-level** in the runnable config (not under
  `configurable`), sourced from `EngineConfig.max_npc_parallelism`.

## Decisions applied (from plan §1)

- **P3.1 single NPC** — `initial_state` unchanged; the router iterates the
  generic `npc_cards` list. N>1 fan-out is covered by a router unit test that
  builds a two-card state directly.
- **P3.2** player-only `current_location`.
- **P3.3** NPC errors skipped; `game_response`/`brief`/`narration` propagate.
- **P3.4** no live LLM smoke (deferred to Phase 4).

## Deviations from the plan

1. **`ruff` added as a dev dependency and the tree linted.** `ruff` was not
   installed (Phase 2 had noted this). `uv add --dev ruff` → `ruff 0.16.10`.
   `ruff check --fix` cleaned 11 pre-existing issues (`__all__` ordering,
   `UP037` quotes, `UP035` `collections.abc`, `UP017` `datetime.UTC`, test import
   sorting); `PYI034` was fixed by hand (`Engine.__aenter__ -> Self`). No
   behaviour change.
2. **`_intents_text` factored out** of `_narration_events` so `game_response`
   and `narration` share the same intent formatting (the plan sketch inlined it
   in both).
3. **`_known_actors` returns `set[str]`** and takes only `state` (the plan
   sketch had a stray `cfg` argument / inconsistent call site).
4. **No worktree.** Implemented directly on `dev/v2`, matching how Phases 1–2
   landed.

## Verification

```
uv run pytest -q                            # 42 passed
uv run ruff check src/agents/engine tests   # All checks passed!
```

New Phase 3 coverage: router (0/2 cards, clarification, invalid); `npc_act`
(deterministic id, no-op, swallowed error, windowed history); game stage
(inventory add/remove/money, unknown actor, player-only location, empty deltas);
real `brief`; narration intents; `max_concurrency`; graph render; and graph-level
valid turns with 1 and 0 NPCs (including barrier ordering).

## Not done (deferred / follow-up)

- **Live LLM smoke** (plan §9 / architecture Phase 4): needs the local
  OpenAI-compatible server and `GAME_*_LLM`. Observe whether
  `{{ ctx.output_format }}` pollutes `NarrateTurn` / `AnswerBrief` / `NpcAct`, and
  drop it only if noisy.
- Phase 4: persisted-thread smoke, resume-after-restart, retry idempotency.
- Phase 5: split the game stage only on observed quality failure.
- N-NPC lore generation (the router already supports the list).

## Uncommitted files at end of Phase 3

```
 M pyproject.toml
 M src/baml_src/clients.baml
 M uv.lock
?? .opencode/
?? AGENTS.md
?? dev_notes/game/            (incl. phase3.md, this file; arch/plan bumped to v1.3)
?? dev_notes/instructions/engine.md
?? src/agents/engine/         (npc.py added; nodes.py/graph.py/__init__.py extended)
?? src/baml_src/engine.baml
?? tests/                     (test_engine_npc.py added)
?? tmp/
```

## Next

Phase 4 — persisted-thread smoke (valid / clarification / invalid across 2+
turns on `AsyncSqliteSaver`, resume after restart), lore regression against a
fixed fixture, retry idempotency via the deterministic IDs, and the live prompt
review.
