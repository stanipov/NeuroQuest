# Agent: StartingPlaceAgent

File: `src/agents/lore/start_loc/agent.py`
Depends on BAML types/functions in `src/baml_src/lore.baml` (generated to `src/baml_client/`).

## Purpose

Generates a starting location (region → settlement → specific place) and opening narrative scene where both the player character and NPC companion begin the game. Wraps a LangGraph `StateGraph` with 5 nodes and 2 conditional routing loops.

---

## State: `StartingPlaceState` (TypedDict)

**Immutable inputs** (set once, never mutated by nodes):

| Field | Type | Description |
|-------|------|-------------|
| `world_type` | `WorldTypes` | Genre + inspiration |
| `world_concept` | `WorldConcept` | World rules (magic, physics, society, geography, tech) |
| `world_narrative` | `WorldNarrative` | Name, history, current state |
| `player_card` | `PlayerCharacterCard` | Generated player character |
| `npc_card` | `PlayerCharacterCard` | Generated NPC companion |

**Phase 1 — Context** (location hierarchy):

| Field | Type | Notes |
|-------|------|-------|
| `context` | `StartingContext` (NotRequired) | Populated by `generate_context_node` |
| `context_iteration` | `int` | Counter, starts at 0 |
| `context_gen_history` | `list[StartingContextGenHistory]` (NotRequired) | Accumulated drafts + critiques for loop |
| `context_feedback` | `list[ContextCritiqueItem]` (NotRequired) | Output of critique; empty list = satisfied |

**Phase 2 — Scene** (character arrangement + narrative):

| Field | Type | Notes |
|-------|------|-------|
| `arrangement` | `CharacterArrangement` (NotRequired) | Why player/NPC are here and together |
| `scene` | `OpeningScene` (NotRequired) | Narrative + immediate hook |
| `scene_iteration` | `int` | Counter, starts at 0 |
| `scene_gen_history` | `list[StartingSceneGenHistory]` (NotRequired) | Accumulated drafts + critiques |
| `scene_feedback` | `list[SceneCritiqueItem]` (NotRequired) | Output of critique; empty = satisfied |

**Control:**

| Field | Type | Default |
|-------|------|---------|
| `max_iterations` | `int` | 5 (set in `StartingPlaceAgent.__init__`) |

---

## Graph Structure

```
ENTRY → generate_context → critique_context ──┬── (sat) → generate_scene → critique_scene ──┬── (sat) → finalize
                                               │ loop to generate_context                 │ loop to generate_scene
                                               └── if unsat & iter < max                   └── if unsat & iter < max
```

### Node: `generate_context_node`

**Calls:** `b.GenStartingContext(type, concept, narrative, player, npc, history)`
**Returns:** `{ "context": StartingContext, "context_iteration": int }`
**Logic:** Increments iteration counter, calls BAML GenStartingContext with history for iterative refinement.

### Node: `critique_context_node`

**Calls:** `b.CritiqueStartingContext(concept, narrative, context)`
**Returns:** `{ "context_feedback": list[ContextCritiqueItem], "context_gen_history": list }`
**Logic:** Calls critique. Appends `StartingContextGenHistory(draft, critique)` to history. If critique has feedback items, prints each `↳ field: fix` as progress indicator.

### Router: `route_context`

**Logic:**
1. If `context_feedback` is empty list (`not feedback`) → return `"generate_scene"` (accepted, move to phase 2)
2. If `context_iteration >= max_iterations` → return `"generate_scene"` (cap reached, proceed anyway)
3. Else → return `"generate_context"` (loop back)

### Node: `generate_scene_node`

**Calls:** `b.GenStartingScene(type, concept, narrative, player, npc, context, history)`
**Returns:** `{ "arrangement": CharacterArrangement, "scene": OpeningScene, "scene_iteration": int }`
**Note:** BAML returns a `SceneOutput` wrapper with `.arrangement` and `.scene` fields.

### Node: `critique_scene_node`

**Calls:** `b.CritiqueStartingScene(concept, narrative, player, npc, context, arrangement, scene)`
**Returns:** `{ "scene_feedback": list[SceneCritiqueItem], "scene_gen_history": list }`
**Logic:** Same pattern as critique_context_node but for scene. Appends `StartingSceneGenHistory(arrangement, scene, critique)`.

### Router: `route_scene`

**Logic:**
1. Empty feedback → `"finalize"`
2. Hit max_iterations → `"finalize"`
3. Else → `"generate_scene"` (loop)

### Node: `finalize_node`

**Returns:** `{ "context": StartingContext, "arrangement": CharacterArrangement, "scene": OpeningScene }`
**Note:** This makes the final state accessible via `graph.ainvoke()` result.

---

## Agent Class: `StartingPlaceAgent`

```python
class StartingPlaceAgent:
    def __init__(self, max_iterations: int = 5):
        self.max_iterations = max_iterations
        self.graph = self._build_graph()

    async def astream(self, inputs: dict):
        async for event in self.graph.astream(inputs, stream_mode="v2"):
            yield event
```

**`_build_graph()`** assembles the `StateGraph`:
- 5 nodes added (`generate_context`, `critique_context`, `generate_scene`, `critique_scene`, `finalize`)
- Edge: `generate_context → critique_context`
- Conditional edge: `critique_context → route_context`
- Edge: `generate_scene → critique_scene`
- Conditional edge: `critique_scene → route_scene`
- Entry: `generate_context`
- Final: `compile()`

---

## Usage (in `world_gen.py`)

```python
from src.agents.lore.start_loc import StartingPlaceAgent

agent = StartingPlaceAgent(max_iterations=5)
result = await agent.graph.ainvoke({
    "world_type": world_type,
    "world_concept": rules,
    "world_narrative": narrative,
    "player_card": player_card,
    "npc_card": npc_card,
    "context_iteration": 0,
    "scene_iteration": 0,
    "max_iterations": 5,
})

# Access results:
result["context"]          # StartingContext (region, settlement, location)
result["arrangement"]      # CharacterArrangement
result["scene"]            # OpeningScene
```

Or use `.astream()` for streaming events with `print()` progress output.

---

## Key Gotchas

| Issue | Mitigation |
|-------|-----------|
| `NotRequired` import | Requires `from typing import NotRequired` (Python 3.14+). For older Python, use `typing_extensions`. |
| Empty feedback = satisfied | Both routers check `not feedback` (empty list means accepted). BAML critique functions **must** return `[]` when satisfied, not `null`. |
| `b.GenStartingScene` returns `SceneOutput` | The BAML function wraps both `arrangement` and `scene` in a single `SceneOutput` class. The node destructures it: `output.arrangement`, `output.scene`. |
| History list grows linearly | Each iteration pushes one `GenHistory` entry. Max size = `max_iterations`. Acceptable for current use. |
| `state.get("context")` vs `state["context"]` | Use `.get()` for `NotRequired` fields (initial state). Use `[]` for required fields and fields guaranteed to exist at that graph position. |
| `route_context` checks `context_feedback` from critique | Critique node must have run before the router fires. Guaranteed by graph edges. |
| State `max_iterations` must be in inputs | Both routers read `state["max_iterations"]`. Must be provided in the initial input dict, not just in `__init__`. |
