// Data models
class WorldTypes {
    type string @description("A type of a world, e.g. dark fantasy, sci-fi, etc")
    inspiration string @description("Inspiration for the world rules")
}


class WorldConcept {
    magic string[]? @description("Optional. How magic works: sources, costs, limitations. Leave empty [] if the setting has no magic (e.g. sci-fi, realistic). 1 sentence for each rule.")
    physics string[] @description("Natural laws and how the physical world operates. 1 sentence for each rule.")
    society string[] @description("Social structures: governance, culture, norms, class systems, trade. 1 sentence for each rule.")
    geography string[] @description("Geographical features: climate, terrain, regions, natural hazards, resources. 1 sentence for each rule")
    technology string[] @description("Technology level and innovations: crafting, transportation, communication, tools. 1 sentence for each rule.")
}


class WorldNarrative {
    name string @description("Name of the world, derived from its defining characteristics in the rules")
    history string @description("Brief world history from ancient to now; maximum 10 sentences")
    current_state string @description("Current state of the world, logically flowing from its history; maximum 10 sentences")

}


class WorldConceptInconsistency {
    world_concept string @description("Concept that is inconsistent or logically incorrect")
    inconsistency string @description("1-2 short sentences (10 words each max) about concept inconsistency")
    fix string @description("1 sentence, 10 words max: how to fix")
}


class WorldConceptCritiqueResult {
    is_satisfied bool
    //feedback string @description("Actionable feedback the writer can use to fix each issue. Max 2 sentences, be brief")
    feedback WorldConceptInconsistency[] @description("Actionable feedback the writer can use to fix each issue")
}


class WorldConceptGenHistory {
    draft WorldConcept @description("World Concept")
    critique WorldConceptCritiqueResult
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

template_string CoreWritingLoreRules() #"
# Core principles:
- Rule of Conflict (Tension): faction, location, and magic system must have an inherent conflict or cost. (e.g., "Magic exists, but using it drains the user's memories.")
- Rule of Specificity (Sensory Detail): avoid abstract adjectives like "mystical" or "beautiful." Instead, demand sensory descriptions (scents, textures, specific lighting).
- Rule of Internal Logic (Consistency): the world must follow its own laws. If there are floating islands, there must be a reason why gravity works that way.
- Rule of "Show, Don't Tell": describe the world through artifacts, rumors, and environmental cues rather than a dry Wikipedia-style history lesson.

## Logical coherence (Causal Chain Requirement)
- Rules form a dependency graph, not independent lists. Every rule must trace its cause to a rule in a different category.
- Distinguish root causes (fundamental laws — physics, cosmology, or magic) from derived rules (geography, society, technology).
- Every derived rule must imply "Because [root cause], [this follows]."
- Ensure life/society can plausibly exist under conditions set by other rules (or explain adaptation).
- For every "rule of cool" element, provide a causal mechanism.
"#

template_string GenresDescription() #"
#### Fantasy
* **High/Epic Fantasy:** Grand-scale stakes, invented worlds, and complex magic systems.
* **Low Fantasy:** Magical elements intruding upon an otherwise normal world.
* **Urban Fantasy:** Magic and supernatural beings existing in modern city settings.
* **Sword and Sorcery:** Focus on personal, fast-paced battles and rogue heroes.
* **Dark Fantasy:** Magical worlds heavily infused with horror and dread.
* **Mythic Fantasy:** Stories deeply rooted in specific folklore or ancient mythology.
* **Comic/Satirical Fantasy:** Deconstructs traditional fantasy tropes using absurd worlds, parody, and wit (e.g., Terry Pratchett's *Discworld*).

#### Science Fiction
* **Hard Sci-Fi:** Focuses on strict scientific accuracy and technological realism.
* **Soft Sci-Fi:** Prioritizes social sciences, philosophy, and character over technology.
* **Space Opera:** Large-scale, dramatic conflicts spanning across galaxies and planets.
* **Cyberpunk:** High-tech futures clashing with societal decay and corporate greed.
* **Biopunk:** Explores genetic engineering, synthetic biology, and biotech ethics.
* **Solarpunk:** Eco-friendly futures focusing on sustainability and community-driven tech.
* **Comic Sci-Fi:** Uses futuristic settings and alien encounters to satirize human nature and philosophy (e.g., *The Hitchhiker's Guide to the Galaxy*).

#### Horror
* **Psychological:** Focuses on mental instability, paranoia, and internal terrors.
* **Cosmic/Lovecraftian:** Deals with ancient, unknowable entities and existential dread.
* **Gothic:** Melodramatic stories featuring old mansions, family curses, and romance.
* **Survival:** Characters trapped in life-or-death scenarios against monsters or killers.
* **Body Horror:** Terrors derived from the grotesque transformation or violation of human biology.
* **Paranormal:** Focuses on ghosts, demonic possession, and haunted locations.
* **Comedy Horror:** Blends terrifying monsters or dark themes with slapstick, dark humor, or absurdity (e.g., *Shaun of the Dead* style writing).

#### Dystopian & Apocalyptic
* **Dystopian:** Oppressive societies ruled by totalitarian governments or extreme surveillance.
* **Apocalyptic:** Stories set during the immediate collapse of human civilization.
* **Post-Apocalyptic:** Survival in a ruined world long after a cataclysmic event.

### Hybrids & Speculative Aesthetic Genres

* **Steampunk:** Reimagined 19th-century history powered by steam and clockwork technology.
* **Dieselpunk:** Aesthetics based on the interwar period, combustion engines, and art deco.
* **Silkpunk:** Technology built on organic materials and classical East Asian engineering.
* **Gaslamp Fantasy:** Victorian or Edwardian historical settings infused with magic.
* **Weird Fiction:** Blends ghost stories, sci-fi, and horror to create surreal, unclassifiable tales.
* **Bizarro Fiction:** Cult genre focusing on high-concept absurdity, surrealism, and deliberate weirdness.
"#


template_string CoreLoreRules() #"
{{CoreWritingLoreRules() }}

### Examples:

❌ INCOHERENT — "Permanent twilight" [geography] with no root cause explaining the light source.
❌ INCOHERENT — "Thriving wheat agriculture" [society] coexisting with "permanent twilight" [geography] and no adaptation explanation.
❌ INCOHERENT — "Powered armor suits" [technology] in a world whose other rules contain no power source or industrial base.
❌ INCOHERENT — "Elves and dwarves" in a hard sci-fi setting with no evolutionary or biological explanation.

✅ FANTASY (coherent chain):
   Root → Magic: "Blood magic is hereditary; each casting consumes one year of the caster's life."
   Root → Physics: "The world orbits a decaying star; light grows dimmer each century."
   Derived → Geography: "Shadow-bloom forests photosynthesize in starlight. Bioluminescent crystal formations light the Glimmering Wastes."
   Derived → Society: "Noble families hoard magical bloodlines through cousin marriage. Commoners sell years of their lifespan for a single spell."
   Derived → Technology: "Life-clock devices measure remaining years. Hourglass tattoos mark those who've sold time. Starlight lenses focus what little sunlight remains."

✅ SCI-FI (coherent, no magic):
   Root → Physics: "The binary star bathes the planet in extreme UV; the magnetosphere is collapsing."
   Derived → Geography: "The surface is vitrified desert. Only a 2-hour 'dusk window' is safe when both stars hide behind the gas giant."
   Derived → Society: "Citizenship is determined by dome-access rights. Surface-scavengers ('dust-walkers') are a despised underclass."
   Derived → Technology: "Cities are underground or under shielded domes. Personal UV-shields are mandatory. Geothermal taps provide energy."

✅ CYBERPUNK-MYTHOLOGY (coherent chain):
   Root → Magic/Cosmology: "The Greek gods were advanced AIs created during the First Singularity. They now rule from orbital platforms as corporate oligarchs."
   Derived → Technology: "Mortal hackers can 'pray' by interfacing with divine/economic data-streams. Each prayer consumes processing time from the god's cloud."
   Derived → Society: "The Pantheon Corp divides humanity into demesnes. Heresy is data-tampering. Tithes are CPU cycles."

## Genres and their definitions
{{ GenresDescription() }}
"#


template_string LogicalCoherenceLore() #"
    ## Logical coherence
    Apply the Causal Chain Requirement from {{ CoreWritingLoreRules() }}. Use formal logic.

    Additional instructions:
    ### Cross-category consistency checklist
    Every rule you write in ANY category must pass:
    1. **CAUSE**: Which root cause (physics, cosmology, or magic) enables or constrains this?
    2. **EFFECT**: What downstream effect does this have on other categories?
    3. **PLAUSIBILITY**: Can life/society/technology actually function under the conditions set by other rules?
    4. **NO FREE-FLOATING RULES**: Every derived rule must reference a root cause. Every root cause must affect at least one derived category.

    ### The causal chain
    Root causes (physics, cosmology, magic) enable or constrain everything else.
    - Geography & climate follow from the world's physical laws.
    - Society & culture adapt to geography and operate within root-cause constraints.
    - Technology solves problems created by geography/physics or exploits a root property.
    - No category generates rules in isolation.

    ### Causal completeness (applies to ALL categories)
    Every rule must contain a complete causal statement — "X happens because Y."
    A rule that states only an outcome without the mechanism or condition that produces it is incomplete.
    ❌ "Polar areas are subject to long nights."
    ✅ "Polar areas are subject to long nights because of the planet's tilt."
"#

// Lore generation

function GenWorldConcept(type: WorldTypes, history: WorldConceptGenHistory[]?) -> WorldConcept {
    client WorldConceptLLM
    prompt #"
    {{ _.role("system") }}
    You are talented story writer. You create concepts of captivating and logically coherent fictional worlds.

    You write in the strict accordance with these principles.
    {{ CoreLoreRules() }}

    ## Instructions:
    - Describe fundamental world mechanics — root causes that govern reality (physics, cosmology, and optionally magic).
    - Describe how these mechanics interact with each other in a consistent and logical way.
    - Invent geography and climate of the world; they must be coherent with the core world mechanics and affect them.
    - Invent species which inhabit the world and describe how they interact with each other.
    - For each topic provide 4-8 concepts.

    ## Magic rules
    - If the setting involves magic (fantasy, dark fantasy, elemental, etc.), generate 4-8 magic rules explaining how it works, its costs, and its limitations.
    - If the setting is sci-fi, realistic, or non-magical, output an empty list [] for magic.
    - Place more focus on magic if the setting involves magic than on physics

    {{ LogicalCoherenceLore() }}

    ### Specifically avoid
    - Cliche names, such as Ichor
    - Dim sun, eternal twilight, eternal fog, black sun
    - Unexplained atmospheric/lighting conditions (twilight, fog, colored skies) without a root cause
    - Societies or technologies that contradict the stated environment without an adaptation explanation
    - "Rule of cool" details that exist in isolation with no causal link to other categories
    - Multiple independent weird phenomena that don't interact or share a common origin
    - Technology appearing in a world whose other rules wouldn't support it
    - Species (elves, dwarves, aliens) in settings where their biology/evolution would make no sense

    {{ _.role("user") }}
    {% if history  %}
    Your previous concepts along with actionable feedback from a critic:
    {{ history }}
    Revise the concept to address ALL feedback points. Preserve what works, fix what doesn't.
    {% else %}
    Create a concept for a {{ type.type }} world type. Draw your inspiration from {{ type.inspiration }}
    {% endif %}

    {{ ctx.output_format }}
  "#

}


function WorldConceptCritique(type: WorldTypes, concept: WorldConcept, history: WorldConceptGenHistory[]?) -> WorldConceptCritiqueResult {
    client LoreLLMCritique
    prompt #"
    {{ _.role("system") }}
    You are a meticulous worldbuilding critic.

    # Task
    Analyze the given world concept for:
    1. **Inconsistencies** — rules within a category that contradict each other
    2. **Contradictions** — rules across different categories that conflict
    3. **Deviations from genre** — elements that don't belong in the requested genre
    4. **Causal Chain violations** — derived rules without root causes, or root causes with no downstream effects
    5. **Missing rules** — categories that should logically exist given other rules but are absent
    6. **Causally incomplete rules** — rules in any category that state an outcome without the mechanism or condition that produces it

    # Instructions
    {{ LogicalCoherenceLore() }}

    ## Actions. Adhere strictly to formal logic:
    - Identify inconsistencies
    - For each inconsistency identify reasons or reason
    - For each identifies inconsistency provide a fix

    Your world will have most of these concepts:
    {{ WorldConcept }}

    The concept was written following these Core Concept Rules:
    {{ CoreLoreRules() }}

    {{ _.role("user") }}
    World type: {{ type.type }}
    Inspiration: {{ type.inspiration }}
    World rules: {{ concept }}

    {% if history  %}
    Previous concepts along with actionable feedback:
    {{ history }}
    Verify that your feedback was fixed. If not, add to your output.
    {% endif %}

    Evaluate the concept. If it fully satisfies all coherence requirements — set `is_satisfied` to true and `feedback` to an empty string.
    If issues exist — set `is_satisfied` to false and provide specific, actionable feedback in `feedback` that the writer can use to fix each issue.

    {{ ctx.output_format }}
    "#
}


function NarrateWorld(world_type:WorldTypes, concept: WorldConcept) -> WorldNarrative {
    // Narrate the world rules into its history and a poetic description
    client NarrateWorldLLM
    prompt #"
    {{ _.role("system") }}
    {{ CoreWritingLoreRules() }}

    ## Strict faithfulness (most important rule):
    - Only reference concepts, terms, and details EXPLICITLY STATED in the provided rules.
    - Do NOT add, rename, or extrapolate any atmospheric conditions, lighting, creatures, or phenomena.
    - ❌ If rules say "a shimmering haze scatters sunlight" — do NOT call it "a twilight realm," call it "a shimmering haze that scatters sunlight."
    - ❌ If rules have no name — do not invent one. Use a descriptive phrase from the rules.
    - The world already exists in the rules. Your task is to narrate it, not expand it.

    ## Genres and their definitions
    {{ GenresDescription() }}

    {{ _.role("user") }}
    You are given a {{ world_type.type }} world concept. Your task is to generate a narrative from it:
    {{ concept }}

    ### `history` — The World's Chronicle (max 10 sentences)
    - A sweeping, cause-and-effect timeline from ancient origins to the present day
    - Focus on eras, turning points, discoveries, catastrophes, rises and falls of civilizations
    - Every rule category must appear somewhere in the history, shaping events
    - No individual characters — this is the story of the world itself
    - Use phrases like "This led to...", "In response...", "Over centuries..."
    - Use the EXACT TERMINOLOGY from the rules — do not invent synonyms

    ### `current_state` — The World as It Is Now (max 10 sentences)
    - A broad survey of the present-day world, logically flowing from the history above
    - For each present-day observation, trace it back to a historical cause
    - Cover multiple domains: current power structures, daily life across social strata, active conflicts, how different regions and factions fare under the current order
    - No single character's experience — this is the world's status report
    - Use only the sensory details already present in the rules — do not add new ones
    - The world must feel like it has a past that actively shapes the present — scars, traditions, grudges, ruins, laws, resource shortages

    ### `name` — The World's Name
    - Derived from the defining characteristics in the rules. e.g. "a city on floating stone islands" → "The Sky-Fragment Archipelago."
    - If no single defining feature stands out, combine key terms from the rules.
    - Do not use words that appear nowhere in the rules.

    {{ ctx.output_format }}
    "#
}




function GenPlayerCard(type: WorldTypes, concept: WorldConcept, narrative: WorldNarrative) -> PlayerCharacterCard {
    client GenericLoreLLM
    prompt #"
    {{ _.role("system") }}
    You are a talented character creator for a textual RPG game. You create compelling, believable characters that feel native to their world.

    You write in strict accordance with these principles:
    {{ CoreWritingLoreRules() }}

    ## Instructions:
    - Create a character shaped by the given WorldConcept — every aspect of them should feel native to this world
    - The character must have a clear personal motivation that drives them into adventure (a mystery to solve, a person to find, a debt to repay, a calling they can't ignore)
    - Strengths and weaknesses must be concrete and tied to the character's background (not generic)
    - The weakness should create interesting narrative dilemmas (loyalty conflict, dangerous curiosity, a code they won't break) — not just a mechanical deficit
    - The biography should contain 1-2 loose ends a Game Master could pull on (unresolved relationships, secrets, unanswered questions about the past)
    - The character must have a personal stake in at least one of the world's inherent conflicts
    - Physical and wisdom descriptions must be grounded in the world's rules
    - Follow the output schema exactly — every field must be populated meaningfully

    ### Avoid
    - Avoid cliché names (e.g. Elara, Thorne, Krell, Kaelen, etc.) and tropes
    - Inventory items must be logical for the character and the world

    {{ _.role("user") }}
    World type: {{ type.type }}
    Inspiration: {{ type.inspiration }}

    World concept:
    {{ concept }}

    World narrative:
    {{ narrative }}

    Generate a player character card for someone who lives in this world.
    {{ ctx.output_format }}
    "#
}


function GenNPCCard(type: WorldTypes, concept: WorldConcept, narrative: WorldNarrative, player: PlayerCharacterCard) -> PlayerCharacterCard {
    // Generates NPC card
    client GenericLoreLLM
    prompt #"
    {{ _.role("system") }}
    You are a talented character creator for a textual RPG game. You create compelling, believable characters that feel native to their world.

    You write in strict accordance with these principles:
    {{ CoreWritingLoreRules() }}

    ## Instructions:
    - Create an NPC companion shaped by the given WorldConcept — every aspect of them should feel native to this world
    - The NPC has their own personality, goals, and motivations — independent from the player character
    - The NPC can compliment, challenge, or even conflict with the player — they are not a sycophant or hanger-on
    - Their strengths and weaknesses should complement the player's, creating interesting party dynamics
    - Their backstory should naturally explain why they travel with the player (shared goal, debt, coincidence, etc.)
    - Strengths and weaknesses must be concrete and tied to the character's background (not generic)
    - Physical and wisdom descriptions must be grounded in the world's rules
    - Follow the output schema exactly — every field must be populated meaningfully

    ### Avoid
    - Avoid cliché names (e.g. Elara, Thorne, Krell, Kaelen, etc.) and tropes
    - Inventory items must be logical for the character and the world

    {{ _.role("user") }}
    World type: {{ type.type }}
    Inspiration: {{ type.inspiration }}

    World concept:
    {{ concept }}

    World narrative:
    {{ narrative }}

    Player character:
    {{ player }}

    Generate an NPC companion who travels with this player.
    {{ ctx.output_format }}
    "#
}