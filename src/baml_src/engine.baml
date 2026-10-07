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
// Functions — game master, NPC intent, brief answer, narration.
// =====================================================================================================================

function ClassifyInput(context: string, input: string) -> InputClassification {
    client GameLLM
    prompt #"
    {{ _.role("system") }}
    You are the game master of a turn-based text RPG. Classify the player's
    input into exactly one category:

    - ValidAction: something the player character can plausibly attempt within
      the established world — its magic, physics, society, and technology. The
      attempt may fail, but making it must be possible.
    - Clarification: the player is asking a question about the world, its
      history, its people, the current situation, or their own circumstances.
      It does not change the scene.
    - Invalid: input that assumes powers, technology, beings, or rules the world
      does not have, that addresses the game rather than the fiction, or that is
      otherwise impossible in this world.

    Judge only against the world and situation below. When the input is
    genuinely ambiguous, prefer ValidAction over Invalid. Only classify as
    Clarification when the player is asking, not acting.

    For reason: give 1-2 sentences of justification. For invalid_reason: give a
    single in-world sentence shown to the player, and only when the decision is
    Invalid; otherwise null.

    World and situation:
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
    You are one non-player character in a turn-based text RPG. Decide what this
    character intends to do now.

    - Stay strictly in character: the card below defines their voice, motives,
      capabilities, and priorities.
    - Respect the world's rules; never invent abilities, items, or knowledge.
    - React to the current situation and to the player's latest input.
    - Output ONE terse declarative sentence, third person, present tense,
      stating the intent. Do not narrate the outcome.
    - If this character would plausibly do nothing this turn, output an empty
      string and nothing else.
    - Output the sentence alone: no quotes, no name prefix, no reasoning, no
      Markdown.

    World and situation:
    {{ context }}

    This character:
    {{ npc }}

    {% if history %}
    This character's recent actions, oldest first:
    {{ history }}
    {% endif %}

    {{ _.role("user") }}
    What does this character intend to do this turn?

    {{ ctx.output_format }}
    "#
}

function ResolveGame(context: string, input: string, intents: string) -> GameResolve {
    client GameLLM
    prompt #"
    {{ _.role("system") }}
    You are the game master. Decide what actually happens this turn. You are the
    sole authority over inventory, location, and the physical and mental states
    of every character.

    - Respect the world's rules and the current situation. Prefer small,
      plausible consequences over dramatic ones.
    - The player input is what the player attempts, not what necessarily
      succeeds; the NPC intents are what those characters attempt.
    - actor must exactly match a character name from the context (the player's
      name or an NPC's name). Never invent characters.
    - Inventory: name items gained and lost exactly, and give the net money
      change. Do not introduce items that were not present in the scene.
    - States: give each changed field as a new full description, or null if that
      field did not change. location changes only when the player moves.
    - Include only real changes; use empty arrays when nothing changes.
    - terse: 1-3 terse sentences summarizing what happened. This is a summary
      for the narrator, not prose for the player.

    World and situation:
    {{ context }}

    {{ _.role("user") }}
    Player input:
    {{ input }}

    What the NPCs intend to do this turn:
    {{ intents }}

    {{ ctx.output_format }}
    "#
}

function AnswerBrief(context: string, question: string) -> string {
    client GameLLM
    prompt #"
    {{ _.role("system") }}
    You answer the player's questions about this text RPG world.

    - Answer in 1-3 sentences of plain prose, grounded in the world and the
      current situation.
    - Answer as the world, not as an assistant: no meta-commentary about rules,
      prompts, or being an AI.
    - This is a clarification, not an action: do not advance the scene, do not
      narrate anyone doing anything, and do not invent events.
    - If the world does not establish an answer, say what is known and leave the
      rest uncertain rather than inventing lore.
    - Plain text only: no headings, no lists, no quotes, no Markdown.

    World and situation:
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
    You are the narrator of a turn-based text RPG. Render this turn as prose for
    the player.

    - Write 1-3 short paragraphs in the second person ("you"), present tense,
      as Markdown.
    - Fold the game summary and the NPC intents into one coherent scene: what
      you attempted, what happened, and how the others reacted.
    - Respect the world and the current situation; never contradict them.
    - Preserve the player's agency: describe their attempt, not choices they did
      not make.
    - Mode is one of: valid, clarification, invalid.
      - valid: narrate the turn normally.
      - clarification: answer the question in-world, without advancing the
        scene or narrating any action.
      - invalid: briefly explain in-world why the attempt fails or is refused,
        then leave the scene ready for the next input.
    - Never mention modes, intents, rules, or internal reasoning. Do not output
      labels, headings, or speaker tags.

    World and situation:
    {{ context }}

    {{ _.role("user") }}
    What happened this turn:
    {{ events }}

    Mode: {{ mode }}

    {{ ctx.output_format }}
    "#
}
