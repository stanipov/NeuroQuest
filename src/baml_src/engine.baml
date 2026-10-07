// =====================================================================================================================
// Game Engine — input classification
// =====================================================================================================================

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

// =====================================================================================================================
// Game Engine — runtime deltas
// =====================================================================================================================

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

// =====================================================================================================================
// Functions — prompt bodies are stubs; fleshed out in Phase 2/3.
// =====================================================================================================================

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
