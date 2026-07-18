# Plan: Starting Place Generation

A LangGraph agent that generates where the player and NPC begin their journey — a specific location embedded in a settlement within a region, with history, character circumstances, and an opening narrative scene.

## Overview

The agent runs in two phases, each with a generate→critique loop capped at `max_iterations`:

```
Phase 1 (Context):  [generate_context] → [critique_context]  ← loop until satisfied
Phase 2 (Scene):    [generate_scene]   → [critique_scene]    ← loop until satisfied
Final:              [finalize]
```

Called with `.astream()` using v2 protocol — `print()` calls inside nodes serve as progress indicators.

---

## 1. BAML Types

Add to `src/baml_src/lore.baml`:

```baml
// =====================================================================================================================
// Starting Place
// =====================================================================================================================

class Settlement {
    name string @description("Name of the settlement (town, city, space port, outpost, etc.)")
    type string @description("Kind of settlement: town, city, space port, fortress, monastery, mining outpost, village, etc.")
    description string @description("Sensory description of the settlement, 3-5 sentences")
    background string @description("Brief history of this settlement, what it's known for, 3-5 sentences")
}

class SpecificLocation {
    name string @description("Name of the specific place within the settlement (e.g. 'The Rusted Stag', 'Docking Bay 7', 'Temple of the Sunken Flame')")
    type string @description("Kind of place: tavern, temple, market, camp, crossroads, ruin, docks, inn, guild hall, plaza, cantina, docking bay, etc.")
    description string @description("Sensory description of the physical space, 3-5 sentences")
    atmosphere string @description("Mood, lighting, sounds, smells — what it feels like to be here, 2-3 sentences")
    notable_features string[] @description("Distinctive landmarks or details a player can interact with, 3-5 items")
}

class StartingContext {
    region_name string @description("Name of the broader region (kingdom, star system, province, zone)")
    region_description string @description("Brief overview of this region — what it's known for, its character, 2-3 sentences")
    settlement Settlement
    location SpecificLocation
}

class CharacterArrangement {
    player_circumstance string @description("Why the player character is here right now — immediate reason tied to their biography/motivation, 2-3 sentences")
    npc_circumstance string @description("Why the NPC is here right now — immediate reason tied to their biography/motivation, 2-3 sentences")
    shared_situation string @description("How the player and NPC know each other or what brings them together at this moment, 1-2 sentences")
}

class OpeningScene {
    narrative string @description("8-12 sentence narrative opening that sets the scene and hooks the player")
    immediate_hook string @description("The first thread to pull — a question, problem, or opportunity the player can immediately act on, 1-2 sentences")
}

// =====================================================================================================================
// Critique types
// =====================================================================================================================

enum ContextField {
    Region
    Settlement
    SpecificLocation
}

class ContextCritiqueItem {
    field ContextField
    issue string @description("What's wrong, 1-2 sentences")
    fix string @description("How to fix, 10 words max")
}

class ContextCritiqueResult {
    is_satisfied bool
    feedback ContextCritiqueItem[]
}

enum SceneField {
    PlayerCircumstance
    NpcCircumstance
    SharedSituation
    Narrative
    ImmediateHook
}

class SceneCritiqueItem {
    field SceneField
    issue string @description("What's wrong, 1-2 sentences")
    fix string @description("How to fix, 10 words max")
}

class SceneCritiqueResult {
    is_satisfied bool
    feedback SceneCritiqueItem[]
}
```

### GenHistory types (for iteration feedback)

```baml
class StartingContextGenHistory {
    draft StartingContext
    critique ContextCritiqueResult
}

class StartingSceneGenHistory {
    arrangement CharacterArrangement
    scene OpeningScene
    critique SceneCritiqueResult
}
```

---

## 2. BAML Functions

### GenStartingContext

```baml
function GenStartingContext(
    type: WorldTypes,
    concept: WorldConcept,
    narrative: WorldNarrative,
    player: PlayerCharacterCard,
    npc: PlayerCharacterCard,
    history: StartingContextGenHistory[]?
) -> StartingContext {
    client GenericLoreLLM
    prompt #"
    {{ _.role("system") }}
    You are a talented world builder for a textual RPG game. You create vivid, specific locations that feel native to their world.

    {{ CoreWritingLoreRules() }}

    ## Instructions:
    - Generate a starting region, settlement, and specific location where BOTH characters (player and NPC) begin their journey.
    - The entire output must feel native to the provided WorldConcept and WorldNarrative.
    - Use the EXACT TERMINOLOGY from the world concept — do not invent synonyms.
    - The location must have sensory detail: what does the player see, hear, smell, feel?
    - The settlement's background should tie into the world's history from the WorldNarrative.
    - The specific location must be a concrete, named place within the settlement.
    - Avoid cliche location names and tropes.

    {{ _.role("user") }}
    World type: {{ type.type }}
    Inspiration: {{ type.inspiration }}

    World concept:
    {{ concept }}

    World narrative:
    {{ narrative }}

    Player character:
    {{ player }}

    NPC companion:
    {{ npc }}

    {% if history %}
    Previous drafts and critique feedback:
    {{ history }}
    Revise to address ALL feedback points. Preserve what works, fix what doesn't.
    {% else %}
    Generate a starting location context for these two characters.
    {% endif %}

    {{ ctx.output_format }}
    "#
}
```

### CritiqueStartingContext

```baml
function CritiqueStartingContext(
    concept: WorldConcept,
    narrative: WorldNarrative,
    context: StartingContext
) -> ContextCritiqueResult {
    client LoreLLMCritique
    prompt #"
    {{ _.role("system") }}
    You are a meticulous worldbuilding critic.

    Evaluate the starting context against these criteria:
    1. **World faithfulness** — does the location fit the WorldConcept and WorldNarrative?
    2. **Terminology** — does it use exact terms from the rules, not invented synonyms?
    3. **Sensory detail** — is the description vivid and specific, not abstract?
    4. **Specificity** — is the location concrete and named, not generic?
    5. **Character fit** — would both the player and NPC plausibly start here?
    6. **Cliche avoidance** — does it avoid overused tropes and names?
    7. **Causal grounding** — does the settlement background trace to world rules?

    {{ CoreWritingLoreRules() }}
    {{ LogicalCoherenceLore() }}

    {{ _.role("user") }}
    World concept:
    {{ concept }}

    World narrative:
    {{ narrative }}

    Starting context:
    {{ context }}

    Evaluate the context. If it fully satisfies all requirements — set `is_satisfied` to true and `feedback` to an empty list.
    If issues exist — set `is_satisfied` to false and provide specific, actionable feedback in `feedback`.

    {{ ctx.output_format }}
    "#
}
```

### GenStartingScene

```baml
function GenStartingScene(
    type: WorldTypes,
    concept: WorldConcept,
    narrative: WorldNarrative,
    player: PlayerCharacterCard,
    npc: PlayerCharacterCard,
    context: StartingContext,
    history: StartingSceneGenHistory[]?
) -> SceneOutput {
    client GenericLoreLLM
    prompt #"
    {{ _.role("system") }}
    You are a talented narrative writer for a textual RPG game. You create compelling opening scenes.

    {{ CoreWritingLoreRules() }}

    ## Instructions:
    - Given the starting context (region, settlement, specific location), write why each character is here and the opening scene.
    - `player_circumstance`: The player's immediate reason for being at this location. Connect it to their biography, occupation, strengths, and weaknesses. Make it feel personal.
    - `npc_circumstance`: The NPC's immediate reason for being at this location. Connect it to their biography and personality. The NPC has their OWN reasons — they're not just waiting for the player.
    - `shared_situation`: How the player and NPC meet or are brought together. It can be coincidence, shared goal, mutual acquaintance, a crisis, etc.
    - `narrative`: 8-12 sentences. Third person. Establish the sensory moment, show (don't tell) the location, introduce both characters naturally, and build toward the hook.
    - `immediate_hook`: A concrete question, problem, or opportunity the player can immediately act on. This is the first game decision.

    ### Avoid
    - "You wake up in..." openings
    - Characters who are just standing around waiting
    - Explanatory infodumps — reveal through action and detail
    - Telling the player what to feel or think

    {{ _.role("user") }}
    World type: {{ type.type }}
    Inspiration: {{ type.inspiration }}

    World concept:
    {{ concept }}

    World narrative:
    {{ narrative }}

    Player character:
    {{ player }}

    NPC companion:
    {{ npc }}

    Starting context:
    {{ context }}

    {% if history %}
    Previous drafts and critique feedback:
    {{ history }}
    Revise to address ALL feedback points. Preserve what works, fix what doesn't.
    {% endif %}

    Generate the character arrangement and opening scene.

    {{ ctx.output_format }}
    "#
}
```

Note: `SceneOutput` is an inline BAML wrapper because we need both `CharacterArrangement` and `OpeningScene` returned. Define it as:

```baml
class SceneOutput {
    arrangement CharacterArrangement
    scene OpeningScene
}
```

### CritiqueStartingScene

```baml
function CritiqueStartingScene(
    concept: WorldConcept,
    narrative: WorldNarrative,
    player: PlayerCharacterCard,
    npc: PlayerCharacterCard,
    context: StartingContext,
    arrangement: CharacterArrangement,
    scene: OpeningScene
) -> SceneCritiqueResult {
    client LoreLLMCritique
    prompt #"
    {{ _.role("system") }}
    You are a narrative critic.

    Evaluate the scene against these criteria:
    1. **Character faithfulness** — do the circumstances match the characters' biographies, motivations, and world context?
    2. **Believability** — is the shared situation plausible, not contrived?
    3. **Narrative quality** — is the opening engaging? Does it show rather than tell?
    4. **Hook** — is the immediate_hook specific and actionable? Can the player act on it right now?
    5. **Sensory grounding** — does the narrative use the location details from the context?
    6. **Tone** — does the narrative tone fit the world genre?
    7. **Cliché avoidance** — no waking-up-openings, no standing-around-waiting?

    {{ _.role("user") }}
    World concept:
    {{ concept }}

    World narrative:
    {{ narrative }}

    Starting context:
    {{ context }}

    Player character:
    {{ player }}

    NPC companion:
    {{ npc }}

    Arrangement:
    {{ arrangement }}

    Scene:
    {{ scene }}

    Evaluate. If fully satisfied — `is_satisfied` true, `feedback` empty.
    If issues exist — `is_satisfied` false, provide specific actionable feedback.

    {{ ctx.output_format }}
    "#
}
```

---

## 3. LangGraph Agent

File: `src/agents/starting_place_agent.py`

### State

```python
from typing import NotRequired, TypedDict

class StartingPlaceState(TypedDict):
    # Immutable inputs
    world_type: WorldTypes
    world_concept: WorldConcept
    world_narrative: WorldNarrative
    player_card: PlayerCharacterCard
    npc_card: PlayerCharacterCard

    # Phase 1 — context
    context: NotRequired[StartingContext]
    context_iteration: int
    context_gen_history: NotRequired[list[StartingContextGenHistory]]
    context_feedback: NotRequired[list[ContextCritiqueItem]]

    # Phase 2 — scene
    arrangement: NotRequired[CharacterArrangement]
    scene: NotRequired[OpeningScene]
    scene_iteration: int
    scene_gen_history: NotRequired[list[StartingSceneGenHistory]]
    scene_feedback: NotRequired[list[SceneCritiqueItem]]

    # Limits
    max_iterations: int
```

### Node functions

```python
async def generate_context_node(state: StartingPlaceState) -> dict:
    attempt = state.get("context_iteration", 0) + 1
    print(f"[StartingPlace] Generating location context... (attempt {attempt})")
    ctx = await b.GenStartingContext(
        type=state["world_type"],
        concept=state["world_concept"],
        narrative=state["world_narrative"],
        player=state["player_card"],
        npc=state["npc_card"],
        history=state.get("context_gen_history"),
    )
    return {
        "context": ctx,
        "context_iteration": attempt,
    }

async def critique_context_node(state: StartingPlaceState) -> dict:
    print("[StartingPlace] Critiquing location context...")
    result = await b.CritiqueStartingContext(
        concept=state["world_concept"],
        narrative=state["world_narrative"],
        context=state["context"],
    )
    if not result.is_satisfied:
        for item in result.feedback:
            print(f"  ↳ {item.field.value}: {item.fix}")
    # Append to history
    history = list(state.get("context_gen_history", []))
    history.append(StartingContextGenHistory(
        draft=state["context"],
        critique=result,
    ))
    return {
        "context_feedback": result.feedback,
        "context_gen_history": history,
    }

def route_context(state: StartingPlaceState) -> Literal["generate_context", "generate_scene"]:
    feedback = state.get("context_feedback", [])
    iteration = state.get("context_iteration", 0)
    max_iter = state.get("max_iterations", 5)

    if not feedback:
        print("[StartingPlace] Location context accepted → generating scene")
        return "generate_scene"
    if iteration >= max_iter:
        print(f"[StartingPlace] Max context iterations ({max_iter}) reached, proceeding to scene...")
        return "generate_scene"
    print(f"[StartingPlace] Revising location context ({iteration}/{max_iter})...")
    return "generate_context"

async def generate_scene_node(state: StartingPlaceState) -> dict:
    attempt = state.get("scene_iteration", 0) + 1
    print(f"[StartingPlace] Generating opening scene... (attempt {attempt})")
    output = await b.GenStartingScene(
        type=state["world_type"],
        concept=state["world_concept"],
        narrative=state["world_narrative"],
        player=state["player_card"],
        npc=state["npc_card"],
        context=state["context"],
        history=state.get("scene_gen_history"),
    )
    return {
        "arrangement": output.arrangement,
        "scene": output.scene,
        "scene_iteration": attempt,
    }

async def critique_scene_node(state: StartingPlaceState) -> dict:
    print("[StartingPlace] Critiquing opening scene...")
    result = await b.CritiqueStartingScene(
        concept=state["world_concept"],
        narrative=state["world_narrative"],
        player=state["player_card"],
        npc=state["npc_card"],
        context=state["context"],
        arrangement=state["arrangement"],
        scene=state["scene"],
    )
    if not result.is_satisfied:
        for item in result.feedback:
            print(f"  ↳ {item.field.value}: {item.fix}")
    history = list(state.get("scene_gen_history", []))
    history.append(StartingSceneGenHistory(
        arrangement=state["arrangement"],
        scene=state["scene"],
        critique=result,
    ))
    return {
        "scene_feedback": result.feedback,
        "scene_gen_history": history,
    }

def route_scene(state: StartingPlaceState) -> Literal["generate_scene", "finalize"]:
    feedback = state.get("scene_feedback", [])
    iteration = state.get("scene_iteration", 0)
    max_iter = state.get("max_iterations", 5)

    if not feedback:
        print("[StartingPlace] Scene accepted → finalizing")
        return "finalize"
    if iteration >= max_iter:
        print(f"[StartingPlace] Max scene iterations ({max_iter}) reached, finalizing...")
        return "finalize"
    print(f"[StartingPlace] Revising scene ({iteration}/{max_iter})...")
    return "generate_scene"

async def finalize_node(state: StartingPlaceState) -> dict:
    print("[StartingPlace] Done!")
    return {
        "starting_place": StartingPlace(
            context=state.get("context"),
            arrangement=state.get("arrangement"),
            scene=state.get("scene"),
        )
    }
```

### Agent class

```python
from langgraph.graph import StateGraph

class StartingPlaceAgent:
    def __init__(self, max_iterations: int = 5):
        self.max_iterations = max_iterations
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        graph = StateGraph(StartingPlaceState)

        graph.add_node("generate_context", generate_context_node)
        graph.add_node("critique_context", critique_context_node)
        graph.add_node("generate_scene", generate_scene_node)
        graph.add_node("critique_scene", critique_scene_node)
        graph.add_node("finalize", finalize_node)

        graph.set_entry_point("generate_context")
        graph.add_edge("generate_context", "critique_context")
        graph.add_conditional_edges("critique_context", route_context)
        graph.add_edge("generate_scene", "critique_scene")
        graph.add_conditional_edges("critique_scene", route_scene)

        return graph.compile()

    async def astream(self, inputs: dict):
        async for event in self.graph.astream(inputs, stream_mode="v2"):
            yield event
```

### Usage

```python
agent = StartingPlaceAgent(max_iterations=5)
async for event in agent.astream({
    "world_type": world_type,
    "world_concept": rules,
    "world_narrative": narrative,
    "player_card": player_card,
    "npc_card": npc_card,
    "context_iteration": 0,
    "scene_iteration": 0,
    "max_iterations": 5,
}):
    pass  # print() statements inside nodes handle progress output
```

---

## 4. Dependencies

Add to `pyproject.toml`:

```
"langgraph>=0.4.0",
"langchain-core>=0.3.0",
```

---

## 5. Pipeline Integration

Update `src/sandbox/world_gen.py`:

1. Uncomment `GenPlayerCard` and `GenNPCCard` calls
2. Add `StartingPlaceAgent` import
3. Create agent and stream events after NPC generation

```python
logger.info("Creating the player's card")
player_card = await b.GenPlayerCard(world_type, rules, narrative)

logger.info("Creating the NPC card")
npc_card = await b.GenNPCCard(world_type, rules, narrative, player_card)

logger.info("Generating the starting place")
agent = StartingPlaceAgent(max_iterations=5)
async for event in agent.astream({
    "world_type": world_type,
    "world_concept": rules,
    "world_narrative": narrative,
    "player_card": player_card,
    "npc_card": npc_card,
    "context_iteration": 0,
    "scene_iteration": 0,
    "max_iterations": 5,
}):
    pass
```

---

## 6. Gotchas & Edge Cases

| Issue | Mitigation |
|-------|-----------|
| **BAML enum field mismatch** | After re-generation, check `ContextField` and `SceneField` enum values match field names in `ContextCritiqueItem`/`SceneCritiqueItem` exactly |
| **LangGraph v1 vs v2 protocol** | Use `stream_mode="v2"`. v2 emits node-level events; v1 emits per-superstep. |
| **`NotRequired` import** | Python 3.14+ has `typing.NotRequired`. Pin to `typing_extensions` for broader compat. |
| **History list grows unbounded** | Only keep the last N history entries if memory becomes an issue. Currently bounded by `max_iterations`. |
| **Empty feedback list** | Both `route_context` and `route_scene` check `not feedback` (empty list = satisfied). The critique BAML functions must return an empty list when satisfied. |
| **Dependency on `litellm`** | LangGraph uses `langchain-core` which may pull in `litellm`. Ensure the `.env` provider config still takes precedence. |
| **BAML regeneration order** | Add types BEFORE functions in `lore.baml`. BAML requires types to be defined before they're referenced. |
| **`SceneOutput` wrapper** | BAML functions can only return a single class. Use a `SceneOutput` container for `CharacterArrangement + OpeningScene`. |

---

## 7. Implementation Order

1. Add `langgraph` + `langchain-core` to `pyproject.toml`, run `uv lock`
2. Add BAML types to `lore.baml` (Settlement → SpecificLocation → StartingContext → CharacterArrangement → OpeningScene → StartingPlace → critique types)
3. Add BAML functions to `lore.baml` (GenStartingContext → CritiqueStartingContext → GenStartingScene → CritiqueStartingScene)
4. Run `uv run baml-cli generate --from=src/baml_src`
5. Create `src/agents/starting_place_agent.py`
6. Update `src/sandbox/world_gen.py`
7. Run and test
