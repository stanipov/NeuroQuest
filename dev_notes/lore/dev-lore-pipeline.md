# Lore Pipeline Graph

A LangGraph pipeline that generates a complete game entry point from a `WorldType` input, composing three sub-pipelines:

1. **WorldGen** — world concept + narrative (new subgraph)
2. **Character Cards** — player + NPC cards (inline nodes)
3. **StartingPlace** — location context + opening scene (existing subgraph)

Configurable via optional JSON file validated against Pydantic models with sensible defaults at every level.

---

## Architecture

```
                    ┌───────────────────────────────────────────┐
                    │           LorePipelineAgent               │
                    │           (parent StateGraph)             │
                    │                                           │
  ENTRY ──► world_gen ──► gen_player_card ──► gen_npc_card ──► starting_place ──► finalize
               │                    │                  │               │
          ┌────┴────┐          ┌───┴───┐          ┌───┴───┐     ┌────┴────┐
          │WorldGen │          │Single │          │Single  │     │Starting │
          │subgraph │          │BAML   │          │BAML    │     │Place    │
          │(2-phase │          │call   │          │call    │     │subgraph │
          │  loop)  │          │       │          │        │     │(2-phase │
          └─────────┘          └───────┘          └────────┘     │  loop)  │
                                                                 └─────────┘
```

No conditional routing at the parent level — phases are strictly sequential. All loops are internal to subgraphs.

---

## 1. Configuration

### Pydantic models (`src/agents/lore/pipeline/config.py`)

Every field has a sensible default, so `LorePipelineConfig()` always gives a working config.

```python
from pydantic import BaseModel


class PhaseConfig(BaseModel):
    """Per-phase iteration cap. max_iterations is the only parameter needed today."""
    max_iterations: int = 10


class WorldGenConfig(BaseModel):
    concept: PhaseConfig = PhaseConfig(max_iterations=10)
    narrative: PhaseConfig = PhaseConfig(max_iterations=10)


class StartingPlaceConfig(BaseModel):
    context: PhaseConfig = PhaseConfig(max_iterations=5)
    scene: PhaseConfig = PhaseConfig(max_iterations=5)


class LorePipelineConfig(BaseModel):
    world_gen: WorldGenConfig = WorldGenConfig()
    starting_place: StartingPlaceConfig = StartingPlaceConfig()
```

### JSON config file (`configs/lore_pipeline.json`)

Optional — if absent all defaults apply. Pydantic validates on load; missing keys fill from defaults at every nesting level.

```json
{
  "world_gen": {
    "concept": { "max_iterations": 10 },
    "narrative": { "max_iterations": 10 }
  },
  "starting_place": {
    "context": { "max_iterations": 5 },
    "scene": { "max_iterations": 5 }
  }
}
```

### Config loading (on `LorePipelineAgent`)

```python
@classmethod
def from_json(cls, path: str = "configs/lore_pipeline.json") -> LorePipelineAgent:
    if Path(path).exists():
        data = json.loads(Path(path).read_text())
        return cls(LorePipelineConfig(**data))
    return cls()
```

### No config in state

Config values are **never** written into graph state. They live on agent instances and are closed over by router functions. State tracks only runtime data (iteration counters, generated content, critique results).

---

## 2. WorldGen Subgraph (new)

**File:** `src/agents/lore/world_gen/__init__.py`, `src/agents/lore/world_gen/agent.py`

A 2-phase generate→critique loop: first concept, then narrative (depends on concept). Exactly mirrors the graph topology of `StartingPlaceAgent`.

### State: `WorldGenState`

Key names align with `StartingPlaceState` (`world_concept`, `world_narrative`) for frictionless subgraph composition.

| Field | Type | Notes |
|-------|------|-------|
| `world_type` | `WorldTypes` | Input, set once |
| `world_concept` | `NotRequired[WorldConcept]` | Phase 1 output |
| `concept_iteration` | `int` | Counter, must be 0 in initial input |
| `concept_gen_history` | `NotRequired[list[WorldConceptGenHistory]]` | BAML-generated type, used in lore.baml |
| `concept_feedback` | `NotRequired[list[WorldConceptInconsistency]]` | BAML critique type |
| `world_narrative` | `NotRequired[WorldNarrative]` | Phase 2 output |
| `narrative_iteration` | `int` | Counter, must be 0 in initial input |
| `narrative_gen_history` | `NotRequired[list[WorldNarrativeGenHistory]]` | BAML-generated type |
| `narrative_feedback` | `NotRequired[list[WorldNarrativeInconsistency]]` | BAML critique type |

### Graph topology

```
 generate_concept ──► critique_concept ──┬── (sat / max reach) ──► generate_narrative ──► critique_narrative ──┬── (sat / max reach) ──► finalize
       ▲                                 │                                                                      │
       └──── (unsat & iter < max) ───────┘                              └──── (unsat & iter < max) ───────────────┘
```

### Nodes

#### `generate_concept_node`
```python
async def generate_concept_node(state: WorldGenState) -> dict:
    attempt = state.get("concept_iteration", 0) + 1
    print(f"[WorldGen] Generating world concept... (attempt {attempt})")
    result = await b.GenWorldConcept(
        type=state["world_type"],
        history=state.get("concept_gen_history"),
    )
    return {"world_concept": result, "concept_iteration": attempt}
```

**BAML:** `b.GenWorldConcept(type, history) → WorldConcept`

#### `critique_concept_node`
```python
async def critique_concept_node(state: WorldGenState) -> dict:
    print("[WorldGen] Critiquing world concept...")
    result = await b.WorldConceptCritique(
        type=state["world_type"],
        concept=state["world_concept"],
        history=state.get("concept_gen_history"),
    )
    if not result.is_satisfied:
        for item in result.feedback:
            print(f"  ↳ {item.world_concept}: {item.fix}")
    history = list(state.get("concept_gen_history", []))
    history.append(WorldConceptGenHistory(draft=state["world_concept"], critique=result))
    return {"concept_feedback": result.feedback, "concept_gen_history": history}
```

**BAML:** `b.WorldConceptCritique(type, concept, history) → WorldConceptCritiqueResult`

#### `route_concept`
```python
def route_concept(state: WorldGenState) -> Literal["generate_concept", "generate_narrative"]:
    feedback = state.get("concept_feedback", [])
    iteration = state.get("concept_iteration", 0)
    if not feedback:
        print("[WorldGen] Concept accepted → generating narrative")
        return "generate_narrative"
    if iteration >= concept_max:  # concept_max closed over from agent instance
        print(f"[WorldGen] Max concept iterations ({concept_max}) reached, proceeding...")
        return "generate_narrative"
    print(f"[WorldGen] Revising concept ({iteration}/{concept_max})...")
    return "generate_concept"
```

#### `generate_narrative_node`
```python
async def generate_narrative_node(state: WorldGenState) -> dict:
    attempt = state.get("narrative_iteration", 0) + 1
    print(f"[WorldGen] Generating world narrative... (attempt {attempt})")
    result = await b.NarrateWorld(
        world_type=state["world_type"],
        concept=state["world_concept"],
        history=state.get("narrative_gen_history"),
    )
    return {"world_narrative": result, "narrative_iteration": attempt}
```

**BAML:** `b.NarrateWorld(world_type, concept, history) → WorldNarrative`

#### `critique_narrative_node`
```python
async def critique_narrative_node(state: WorldGenState) -> dict:
    print("[WorldGen] Critiquing world narrative...")
    result = await b.NarrateWorldCritique(
        concept=state["world_concept"],
        narrative=state["world_narrative"],
        history=state.get("narrative_gen_history"),
    )
    if not result.is_satisfied:
        for item in result.feedback:
            print(f"  ↳ {item.field}: {item.fix}")
    history = list(state.get("narrative_gen_history", []))
    history.append(WorldNarrativeGenHistory(draft=state["world_narrative"], critique=result))
    return {"narrative_feedback": result.feedback, "narrative_gen_history": history}
```

**BAML:** `b.NarrateWorldCritique(concept, narrative, history) → WorldNarrativeCritiqueResult`

#### `route_narrative`
```python
def route_narrative(state: WorldGenState) -> Literal["generate_narrative", "finalize"]:
    feedback = state.get("narrative_feedback", [])
    iteration = state.get("narrative_iteration", 0)
    if not feedback:
        print("[WorldGen] Narrative accepted → finalizing")
        return "finalize"
    if iteration >= narrative_max:
        print(f"[WorldGen] Max narrative iterations ({narrative_max}) reached, finalizing...")
        return "finalize"
    print(f"[WorldGen] Revising narrative ({iteration}/{narrative_max})...")
    return "generate_narrative"
```

#### `finalize_node`
```python
async def finalize_node(state: WorldGenState) -> dict:
    print("[WorldGen] Done!")
    return {
        "world_concept": state.get("world_concept"),
        "world_narrative": state.get("world_narrative"),
    }
```

### Agent class

```python
class WorldGenAgent:
    def __init__(self, config: WorldGenConfig | None = None):
        cfg = config or WorldGenConfig()
        self.concept_max = cfg.concept.max_iterations
        self.narrative_max = cfg.narrative.max_iterations
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        concept_max = self.concept_max
        narrative_max = self.narrative_max

        def route_concept(state: WorldGenState) -> Literal["generate_concept", "generate_narrative"]:
            feedback = state.get("concept_feedback", [])
            iteration = state.get("concept_iteration", 0)
            if not feedback:
                return "generate_narrative"
            if iteration >= concept_max:
                return "generate_narrative"
            return "generate_concept"

        def route_narrative(state: WorldGenState) -> Literal["generate_narrative", "finalize"]:
            feedback = state.get("narrative_feedback", [])
            iteration = state.get("narrative_iteration", 0)
            if not feedback:
                return "finalize"
            if iteration >= narrative_max:
                return "finalize"
            return "generate_narrative"

        graph = StateGraph(WorldGenState)
        graph.add_node("generate_concept", generate_concept_node)
        graph.add_node("critique_concept", critique_concept_node)
        graph.add_node("generate_narrative", generate_narrative_node)
        graph.add_node("critique_narrative", critique_narrative_node)
        graph.add_node("finalize", finalize_node)
        graph.set_entry_point("generate_concept")
        graph.add_edge("generate_concept", "critique_concept")
        graph.add_conditional_edges("critique_concept", route_concept)
        graph.add_edge("generate_narrative", "critique_narrative")
        graph.add_conditional_edges("critique_narrative", route_narrative)
        return graph.compile()

    async def astream(self, inputs: dict):
        async for event in self.graph.astream(inputs, stream_mode="v2"):
            yield event
```

---

## 3. StartingPlace Subgraph (existing, modified)

**File:** `src/agents/lore/start_loc/agent.py`

### Changes from current version

| Change | Reason |
|--------|--------|
| `__init__` takes `context_max_iterations` and `scene_max_iterations` (separate ints) instead of single `max_iterations` | Independent config per phase |
| Routers become closures that close over these values | Keeps config out of state |
| `max_iterations` field removed from `StartingPlaceState` | Config doesn't belong in state |
| `StartingPlaceState.world_concept` and `StartingPlaceState.world_narrative` become `NotRequired` | When composed as subgraph, these keys overlap with the parent state but don't need to be required since they're populated upstream |

### Updated state

```python
class StartingPlaceState(TypedDict):
    world_type: WorldTypes
    world_concept: NotRequired[WorldConcept]
    world_narrative: NotRequired[WorldNarrative]
    player_card: PlayerCharacterCard
    npc_card: PlayerCharacterCard

    context: NotRequired[StartingContext]
    context_iteration: int
    context_gen_history: NotRequired[list[StartingContextGenHistory]]
    context_feedback: NotRequired[list[ContextCritiqueItem]]

    arrangement: NotRequired[CharacterArrangement]
    scene: NotRequired[OpeningScene]
    scene_iteration: int
    scene_gen_history: NotRequired[list[StartingSceneGenHistory]]
    scene_feedback: NotRequired[list[SceneCritiqueItem]]
```

### Updated agent

```python
class StartingPlaceAgent:
    def __init__(self, context_max_iterations: int = 5, scene_max_iterations: int = 5):
        self.context_max = context_max_iterations
        self.scene_max = scene_max_iterations
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        context_max = self.context_max
        scene_max = self.scene_max

        def route_context(state) -> Literal["generate_context", "generate_scene"]:
            feedback = state.get("context_feedback", [])
            iteration = state.get("context_iteration", 0)
            if not feedback:
                return "generate_scene"
            if iteration >= context_max:
                return "generate_scene"
            return "generate_context"

        def route_scene(state) -> Literal["generate_scene", "finalize"]:
            feedback = state.get("scene_feedback", [])
            iteration = state.get("scene_iteration", 0)
            if not feedback:
                return "finalize"
            if iteration >= scene_max:
                return "finalize"
            return "generate_scene"

        # ... nodes unchanged, use same closures for routers
```

Nodes (`generate_context_node`, `critique_context_node`, `generate_scene_node`, `critique_scene_node`, `finalize_node`) remain identical to the existing implementation.

---

## 4. Parent Pipeline Graph (new)

**File:** `src/agents/lore/pipeline/__init__.py`, `src/agents/lore/pipeline/agent.py`

Orchestrates the three phases. State is a superset of all subgraph state keys.

### State: `LorePipelineState`

```python
class LorePipelineState(TypedDict):
    # Input
    world_type: WorldTypes

    # Phase 1+2 — WorldGen subgraph
    world_concept: NotRequired[WorldConcept]
    concept_iteration: int
    concept_gen_history: NotRequired[list[WorldConceptGenHistory]]
    concept_feedback: NotRequired[list[WorldConceptInconsistency]]
    world_narrative: NotRequired[WorldNarrative]
    narrative_iteration: int
    narrative_gen_history: NotRequired[list[WorldNarrativeGenHistory]]
    narrative_feedback: NotRequired[list[WorldNarrativeInconsistency]]

    # Phase 3 — Character cards
    player_card: NotRequired[PlayerCharacterCard]
    npc_card: NotRequired[PlayerCharacterCard]

    # Phase 4 — StartingPlace subgraph
    context: NotRequired[StartingContext]
    context_iteration: int
    context_gen_history: NotRequired[list[StartingContextGenHistory]]
    context_feedback: NotRequired[list[ContextCritiqueItem]]
    arrangement: NotRequired[CharacterArrangement]
    scene: NotRequired[OpeningScene]
    scene_iteration: int
    scene_gen_history: NotRequired[list[StartingSceneGenHistory]]
    scene_feedback: NotRequired[list[SceneCritiqueItem]]
```

### Inline nodes

#### `gen_player_card_node`
```python
async def gen_player_card_node(state: LorePipelineState) -> dict:
    print("[Pipeline] Generating player character card...")
    card = await b.GenPlayerCard(
        type=state["world_type"],
        concept=state["world_concept"],
        narrative=state["world_narrative"],
    )
    return {"player_card": card}
```

**BAML:** `b.GenPlayerCard(type, concept, narrative) → PlayerCharacterCard`

#### `gen_npc_card_node`
```python
async def gen_npc_card_node(state: LorePipelineState) -> dict:
    print("[Pipeline] Generating NPC companion card...")
    card = await b.GenNPCCard(
        type=state["world_type"],
        concept=state["world_concept"],
        narrative=state["world_narrative"],
        player=state["player_card"],
    )
    return {"npc_card": card}
```

**BAML:** `b.GenNPCCard(type, concept, narrative, player) → PlayerCharacterCard`

#### `finalize_node`
```python
async def finalize_node(state: LorePipelineState) -> dict:
    print("[Pipeline] Lore pipeline complete!")
    return {
        "world_concept": state.get("world_concept"),
        "world_narrative": state.get("world_narrative"),
        "player_card": state.get("player_card"),
        "npc_card": state.get("npc_card"),
        "context": state.get("context"),
        "arrangement": state.get("arrangement"),
        "scene": state.get("scene"),
    }
```

### Agent class

```python
class LorePipelineAgent:
    def __init__(self, config: LorePipelineConfig | None = None):
        self.config = config or LorePipelineConfig()
        self.world_gen_subgraph = WorldGenAgent(self.config.world_gen).graph
        self.start_place_subgraph = StartingPlaceAgent(
            context_max_iterations=self.config.starting_place.context.max_iterations,
            scene_max_iterations=self.config.starting_place.scene.max_iterations,
        ).graph
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        graph = StateGraph(LorePipelineState)
        graph.add_node("world_gen", self.world_gen_subgraph)
        graph.add_node("gen_player_card", gen_player_card_node)
        graph.add_node("gen_npc_card", gen_npc_card_node)
        graph.add_node("starting_place", self.start_place_subgraph)
        graph.add_node("finalize", finalize_node)

        graph.set_entry_point("world_gen")
        graph.add_edge("world_gen", "gen_player_card")
        graph.add_edge("gen_player_card", "gen_npc_card")
        graph.add_edge("gen_npc_card", "starting_place")
        graph.add_edge("starting_place", "finalize")
        return graph.compile()

    @classmethod
    def from_json(cls, path: str = "configs/lore_pipeline.json") -> LorePipelineAgent:
        config_path = Path(path)
        if config_path.exists():
            data = json.loads(config_path.read_text())
            return cls(LorePipelineConfig(**data))
        return cls()

    async def astream(self, inputs: dict):
        async for event in self.graph.astream(inputs, stream_mode="v2"):
            yield event
```

---

## 5. Usage

### Pipeline entry (`src/sandbox/world_gen.py`)

```python
from src.agents.lore.pipeline import LorePipelineAgent

async def main():
    world_type = WorldTypes(
        type="high fantasy",
        inspiration="Political intrigues of Game of Thrones combined with epic fantasy world",
    )

    agent = LorePipelineAgent.from_json("configs/lore_pipeline.json")

    # Or with programmatic config:
    # cfg = LorePipelineConfig(
    #     world_gen=WorldGenConfig(concept=PhaseConfig(max_iterations=20))
    # )
    # agent = LorePipelineAgent(config=cfg)

    result = await agent.graph.ainvoke({
        "world_type": world_type,
        "concept_iteration": 0,
        "narrative_iteration": 0,
        "context_iteration": 0,
        "scene_iteration": 0,
    })

    # Access everything from one result:
    result["world_concept"]    # WorldConcept
    result["world_narrative"]  # WorldNarrative
    result["player_card"]      # PlayerCharacterCard
    result["npc_card"]         # PlayerCharacterCard
    result["context"]          # StartingContext
    result["arrangement"]      # CharacterArrangement
    result["scene"]            # OpeningScene
```

### Input dict

```python
{
    "world_type": world_type,        # required, no default
    "concept_iteration": 0,          # required, must start at 0
    "narrative_iteration": 0,        # required, must start at 0
    "context_iteration": 0,          # required, must start at 0
    "scene_iteration": 0,            # required, must start at 0
}
```

---

## 6. BAML Dependency Check

All BAML types and functions already exist in `src/baml_src/lore.baml`. No changes needed.

| BAML Function | Used By |
|---------------|---------|
| `GenWorldConcept` | `generate_concept_node` |
| `WorldConceptCritique` | `critique_concept_node` |
| `NarrateWorld` | `generate_narrative_node` |
| `NarrateWorldCritique` | `critique_narrative_node` |
| `GenPlayerCard` | `gen_player_card_node` |
| `GenNPCCard` | `gen_npc_card_node` |
| `GenStartingContext` | `generate_context_node` (in StartingPlaceAgent) |
| `CritiqueStartingContext` | `critique_context_node` (in StartingPlaceAgent) |
| `GenStartingScene` | `generate_scene_node` (in StartingPlaceAgent) |
| `CritiqueStartingScene` | `critique_scene_node` (in StartingPlaceAgent) |

---

## 7. File Map

| Path | Action |
|------|--------|
| `dev_notes/lore/dev-lore-pipeline.md` | **Write** — this spec |
| `configs/lore_pipeline.json` | **Create** — optional external config |
| `src/agents/lore/pipeline/__init__.py` | **Create** — exports `LorePipelineAgent`, `LorePipelineConfig` |
| `src/agents/lore/pipeline/agent.py` | **Create** — parent graph |
| `src/agents/lore/pipeline/config.py` | **Create** — Pydantic models |
| `src/agents/lore/world_gen/__init__.py` | **Create** — exports `WorldGenAgent`, `WorldGenState` |
| `src/agents/lore/world_gen/agent.py` | **Create** — WorldGen subgraph |
| `src/agents/lore/start_loc/agent.py` | **Modify** — split max_iterations, state `max_iterations` removal, `world_concept`/`world_narrative` as NotRequired |
| `src/sandbox/world_gen.py` | **Rewrite** — uses `LorePipelineAgent` |
| `src/agents/world_concept_writer.py` | **Keep** — legacy, not deleted |
| `src/agents/world_narrative_writer.py` | **Keep** — legacy, not deleted |

---

## 8. Edge Cases & Gotchas

| Issue | Mitigation |
|-------|-----------|
| **Subgraph state narrowing** requires matching key names between parent and subgraph states | All three states use `world_concept` / `world_narrative` consistently. LorePipelineState includes all keys from both subgraph states. |
| **NotRequired fields in subgraph state** — subgraph may read a key that doesn't exist yet in parent | Parent initializes iteration keys at 0. Content keys (concept, narrative, etc.) are NotRequired and populated as subgraph runs. |
| **StartingPlaceState.world_concept and world_narrative were required** — breaking change for standalone usage | Change to NotRequired. Standalone callers must still provide them; the subgraph will fail gracefully if they're missing. For pipeline usage, they're already populated by WorldGen. |
| **Router closures capture config by value** | Closures are defined inside `_build_graph()`, capturing scalars. Each agent instance gets its own closure values. |
| **Empty feedback = satisfied** | All routers check `not feedback` (empty list = accepted). BAML critique functions must return `[]` when satisfied, not `null`. |
| **`NotRequired` import** | Requires `from typing import NotRequired` (Python 3.14+). For older Python use `typing_extensions`. |
| **History lists grow linearly** | Each iteration appends one entry. Max size = `max_iterations`. Acceptable for current use. |
| **No `with` statement for config file** | Config file is read once at construction time. File not found = all defaults silently applied. |
