// Data models
class WorldTypes {
    type string @description("A type of a world, e.g. dark fantasy, sci-fi, etc")
    inspiration string @description("Inspiration for the world rules")
}

class WorldRules {
    magic string[] @description("How magic works: sources, costs, limitations, wild magic, spell mechanics. 1 sentence for each rule.")
    physics string[] @description("Natural laws and unusual phenomena: gravity, light, time, environmental effects. 1 sentence for each rule.")
    society string[] @description("Social structures: governance, culture, norms, class systems, trade. 1 sentence for each rule.")
    geography string[] @description("Geographical features: climate, terrain, regions, natural hazards, resources. 1 sentence for each rule")
    technology string[] @description("Technology level and innovations: crafting, transportation, communication, tools. 1 sentence for each rule.")
}

class WorldNarrative {
    name string @description("Name of the world")
    history string @description("Brief world history from ancient to now; maximum 10 sentences")
    description string @description("Convert the world rules into a compelling narrative, maximum 10 sentences")

}

// =====================================================================================================================
// Character cards
enum PlayerGender {
    Male
    Female
}

class PlayerCharacterCard {
    name string @description("Character's name; avoid cliche names such as Elara Thorne")
    gender PlayerGender @description("Character's gender; choose randomly")
    occupation string @description("Character's profession/role (e.g., warrior, researcher, magician, crook, merchant)")
    age int @assert({{ this >= 18 and this <= 100 }}) @description("Character's age")
    biography string @description("Brief character backstory (1-2 sentences), 140 characters")
    physical string  @description("Strength, dexterity, endurance as descriptive text (1 sentence), 140 characters")
    wisdom string  @description("Intelligence and wisdom as descriptive text (1 sentence), 140 characters")
    strengths string  @description("Character's notable strong points (1 sentence, up to 10 words), 140 characters")
    weaknesses string  @description("Character's notable weak points (1 sentence, up to 10 words), 140 characters")
    money int @assert({{ this >= 0 }}) @description("Starting gold coins")
    inventory string[] @description("List of starting item names (functional, 1-2 words each)")
}
// =====================================================================================================================

template_string CoreLoreRules() #"
# Core principles:
- Rule of Conflict (Tension): faction, location, and magic system must have an inherent conflict or cost. (e.g., "Magic exists, but using it drains the user's memories.")
- Rule of Specificity (Sensory Detail): avoid abstract adjectives like "mystical" or "beautiful." Instead, demand sensory descriptions (scents, textures, specific lighting).
- Rule of Internal Logic (Consistency): the world must follow its own laws. If there are floating islands, there must be a reason why gravity works that way.
- Rule of "Show, Don't Tell": describe the world through artifacts, rumors, and environmental cues rather than a dry Wikipedia-style history lesson.

## Logical coherency
- avoid adjectives like "mystical" or "beautiful".
- you must provide sensory descriptions (scents, textures, specific lighting).
- the world must follow its own laws.
- there is always a logical explanation and connection to every rule and detail
- every term you invent needs brief explanation
"#

// Lore generation

function NarrateWorld(rules: WorldRules) -> WorldNarrative {
    client LoreLLM
    prompt #"
    {{ _.role("system") }}
    {{ CoreLoreRules() }}

    ## Instructions:
    You are given structured world rules covering {{ WorldRules }}.
    Write a compelling and logically coherent world narrative that brings those rules to life.

    - Every rule category must be reflected somewhere in the narrative
    - Show how the rules interact, conflict, or reinforce each other
    - Use sensory details (scents, textures, lighting, sounds) — no abstract adjectives
    - The world must feel lived-in, not like a textbook entry

    {{ _.role("user") }}
    Generate a world narrative from these rules:
    {{ rules }}

    {{ ctx.output_format }}
    "#
}


function GenWorldRules(type: WorldTypes) -> WorldRules {
    client LoreLLM
    prompt #"
    {{ _.role("system") }}
    You are talented story writer. You create concepts of captivating and logically coherent fictional worlds.

    You write in the strict accordance with these principles.
    {{ CoreLoreRules() }}

    ## Instructions:
    - describe fundamental world mechanics, such as magic, technology, physics, etc.
    - describe how these mechanics interact with each other in a consistent way and logical way.
    - invent geography and climate of the world; they must be coherent with the core world mechanics and can affect them.
    - invent races and species which inhabitate the world.
    - describe how these species and races interact with each other.
    - for each provided topic provide 4-8 concepts

    # The concept covers:
    - The Concept/Cosmology: The "big picture" (Gods, Physics, Magic).
    - The Geography & Biomes: The "map" and how environment shapes culture.
    - The Societal Layer: Factions, economies, and religions.


    {{ _.role("user") }}
    Create a concept for a {{ type.type }} world type. Draw your inspiration from {{ type.inspiration }}

    {{ ctx.output_format }}
  "#

}

function GenPlayerCard(type: WorldTypes, rules: WorldRules, narrative: WorldNarrative) -> PlayerCharacterCard {
    client LoreLLM
    prompt #"
    {{ _.role("system") }}
    You are a talented character creator for a textual RPG game. You create compelling, believable characters that feel native to their world.

    You write in strict accordance with these principles:
    {{ CoreLoreRules() }}

    ## Instructions:
    - Create a character shaped by the given world — their occupation, possessions, and backstory must reflect the world's magic, technology, society, and geography
    - Strengths and weaknesses must be concrete and tied to the character's background (not generic)
    - Physical and wisdom descriptions must be grounded in the world's rules
    - Avoid cliché names and tropes
    - Follow the output schema exactly — every field must be populated meaningfully

    {{ _.role("user") }}
    World type: {{ type.type }}
    Inspiration: {{ type.inspiration }}

    World rules:
    {{ rules }}

    World narrative:
    {{ narrative }}

    Generate a player character card for someone who lives in this world.
    {{ ctx.output_format }}
    "#
}
