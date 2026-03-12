"""
Collection of prompts to generate the world and the lore
"""

from .response_models import (
    WorldRulesModel,
    NPCBehaviorRulesModel,
    KingdomsModel,
    KingdomData,
)
from ..utils.helpers import dict_2_str
import logging
import random

logger = logging.getLogger(__name__)

from typing import Dict, List, Set, Any, Optional


########################################################################################################################
# default descriptions
# instructions to generate a kingdom
# these will be transferred to the LLMs
# instructions to generate a town in a kingdom

# Generic traits/descriptions of kingdoms. The LLM will pick randomly some of these
kingdoms_traits = """The world has many kingdoms. They can be very different:
1. magic, they rely on solving their problems on magic. Magicians are very respected
2. militaristic, they have very strong armies, excel in warfare, tactics. They can be very aggressive towards \
other parties.
3. diplomatic, these can trick anyone. They are very good in deception and plots against others. You never know \
what's happening till it's too late.
4. technology, they combine magic and technology, scientific inquiry is highly valued. These places \
are known for mass production and highly educated people. Their armies are strong and fearsome, but they \
are not interested in conquests, they want trade and earn money."""

########################################################################################################################
# Set of default prompts

# Generic system prompt for lore generation
LORE_GEN_SYS_PRT = """You are AI Game Master who plans and outlines RPG \
game mechanics and game worlds. Your job is to help to create \
interesting fantasy worlds that players would love to play in.

Your answers shall be very short and outline only important \
information. You follow following instructions:
- Only generate in plain text without formatting.
- Use simple clear language without being flowery.
- You strictly follow your instructions.
- You never add anything from yourself.
- You must stay below 5 sentences for each description."""


# The prompt to generate rules fo a world similar to 'world_desc_default' above
WORLD_RULES_GEN_SYS_PRT = """You are a talented fiction story writer. \
Task: invent a compelling and unique fantasy world. 
Instructions:
- Only generate in plain text without formatting.
- describe fundamental world mechanics, such as magic, technology, etc.
- describe how these mechanics interact with each other.
- invent races and species which inhabitate the world.
- describe how these species and races interact with each other.
- respond only with a list of rules/outlines of 1 sentence (10 words max)."""


# A system prompt to describe objects based on instructions
# Used in ObjectDescriptor class
OBJ_ESTIMATOR_SYS_PROMPT = """You are an AI Game engine. 
Your task is to describe these properties of a game object:
- name
- type
- description
- action (how it works)
- strength

Your response must be valid JSON with this exact structure:
{
  "name": "object name (1-2 words)",
  "type": "armor|weapon|food|drink|magical item|document|book|clothing|medical|tool|other",
  "description": "brief description or empty string",
  "action": "how it works or empty string",
  "strength": "weak|moderate|strong or empty string"
}

Rules:
- Short and concise (max 5 words per field)
- Only return valid JSON, no markdown or extra text
- Correct spelling errors in the object name
- Follow task instructions for each field"""


########################################################################################################################
def gen_world_rules_msgs(
    num_rules: int, world_type: str = "fantasy", kind: str = "dark"
) -> List[Dict[str, str]]:
    """
    Generates user prompt for structured world rules generation.

    The system prompt with Pydantic schema is added automatically by struct_output().

    :param num_rules: Number of rules per category (3-5 recommended)
    :param world_type: 'fantasy' or 'sci-fi'
    :param kind: 'dark', 'neutral', or 'funny'
    :return: User message (system message added by struct_output)
    """
    if world_type.lower() not in ["sci-fi", "fantasy"]:
        raise ValueError(
            f"World type '{world_type}' is not recognized! Expected 'sci-fi' or 'fantasy'"
        )

    inspirations = {}
    if world_type.lower() == "fantasy":
        inspirations = {
            "dark": """Blend: Lord of the Rings darkness, Norse mythology harshness, \
Game of Thrones political complexity. Avoid: eternal twilight/rain.""",
            "neutral": "Classic Dungeons & Dragons fantasy with balanced good vs evil.",
            "funny": "Terry Pratchett Discworld humor with absurd but logical magic.",
        }
    elif world_type.lower() == "sci-fi":
        inspirations = {
            "dark": """Blend: Cyberpunk 2077 dystopia, 1984 oppression, Altered Carbon \
inequality, Star Wars imperial tyranny.""",
            "neutral": "Star Wars or Mass Effect style space opera with exploration.",
            "funny": "Futurama-style humor with absurd technology and bureaucracy.",
        }

    if kind not in inspirations:
        raise ValueError(
            f"World kind '{kind}' is not recognized! Expected {list(inspirations.keys())}"
        )

    inspiration = inspirations[kind]

    user_prompt = f"""Create comprehensive world rules for a {kind} {world_type} setting.

WORLD INSPIRATION: {inspiration}

Generate exactly {num_rules} rules per category (each rule 10-15 words).

Rules must be:
- Specific and actionable (not abstract)
- Internally consistent across categories
- Useful for steering gameplay and NPC behavior
- Written in clear, concise language

Example format:
{{
  "MAGIC": [
    "Magic channels through crystal deposits found in mountain ranges across the continent",
    "Prolonged spellcasting drains life force requiring rest or restorative potions"
  ],
  ...
}}
"""

    return [{"role": "user", "content": user_prompt}]


def gen_world_msgs(world_desc: str) -> List[Dict[str, str]]:
    """
    Returns user prompt for structured world description generation.

    System prompt with Pydantic schema is added automatically by struct_output().

    :param world_desc: String describing world peculiarities/requirements
    :return: User message for structured output
    """
    user_prompt = f"""Create a unique fantasy world with an evocative name and description.

WORLD REQUIREMENTS:
{world_desc}

Your task:
1. **Name**: Invent a captivating, memorable fantasy name (exactly 1 word, no spaces)
   - Should sound magical, ancient, or otherworldly
   - Avoid generic names like "Fantasy World" or "Magic Realm"
   - Examples of good names: Aetherea, Eldoria, Xyloth, Drakmora

2. **Description**: Write a poetic, evocative description (maximum 5 sentences)
   - Capture the world's unique essence and atmosphere
   - Hint at geography, magic, culture, or defining characteristics
   - Use vivid, imaginative language that sparks curiosity
   - Make it sound like the opening of an epic tale

Style guidelines:
- Be creative and original, avoid clichés
- Write in a tone suitable for high fantasy
- Focus on what makes this world unique and memorable
- Keep it concise but evocative (quality over quantity)

Output valid JSON matching this structure:
{{
  "name": "OneWordName",
  "description": "Poetic description of up to 5 sentences capturing the world's essence..."
}}

Return ONLY the JSON object, no markdown or additional text."""

    return [{"role": "user", "content": user_prompt}]


def gen_kingdom_msgs(
    num_kingdoms: int, kingdoms_traits: str, world: Dict[str, str]
) -> List[Dict[str, str]]:
    """
    Returns user prompt for structured kingdom generation.

    System prompt with Pydantic schema is added automatically by struct_output().

    :param num_kingdoms: Number of kingdoms to generate
    :param kingdoms_traits: Description of kingdom type options
    :param world: World description dict with 'name' and 'description' keys
    :return: User message for structured output (system added by struct_output)
    """
    if num_kingdoms < 1:
        logger.warning(f'Expected "num_kingdoms">=1, got {num_kingdoms}. Set to 1!')
        num_kingdoms = 1

    user_prompt = f"""Create {num_kingdoms} unique kingdoms for this fantasy world.

WORLD CONTEXT:
World Name: {world["name"]}
World Description: {world["description"]}

KINGDOM TYPE OPTIONS:
{kingdoms_traits}

Instructions:
1. Create exactly {num_kingdoms} kingdoms
2. Each kingdom should blend 2-3 traits from the options above
3. Kingdoms should be diverse and complementary (not all same type)
4. Ensure geographical locations make sense within the world description
5. International relations should reference other generated kingdoms

For each kingdom provide:
- **name**: Unique, memorable fantasy name (1-3 words)
- **history**: Brief founding story (1 sentence, ~10 words)
- **type**: Primary characteristic (magic/militaristic/diplomatic/technology)
- **location**: Where it sits in the world (up to 1 sentence)
- **political_system**: Government type (max 5 words)
- **national_wealth**: Economic status (max 10 words)
- **international**: Relations with neighbors (~10 words)

Output as JSON array of kingdom objects matching the KingdomsModel schema."""

    return [{"role": "user", "content": user_prompt}]


def gen_towns_msgs(
    num_towns: int,
    world: Dict[str, str],
    kingdoms: Dict[str, Dict[str, str]],
    kingdom_name: str,
) -> List[Dict[str, Any]]:
    """
    Returns user prompt for structured town generation.

    System prompt with Pydantic schema is added automatically by struct_output().

    :param num_towns: Number of towns to generate
    :param world: World description dict with 'name' and 'description' keys
    :param kingdoms: Dict of all kingdoms
    :param kingdom_name: Name of the kingdom for which to generate towns
    :return: User message for structured output (system added by struct_output)
    """
    if num_towns < 1:
        logger.warning(f'Expected "num_towns">=1, got {num_towns}. Set to 1!')
        num_towns = 1

    lst_kings = [x for x in kingdoms if x != kingdom_name]

    user_prompt = f"""Create {num_towns} unique, memorable towns for this fantasy kingdom.

WORLD CONTEXT:
World Name: {world["name"]}
World Description: {world["description"]}

KINGDOM CONTEXT:
{dict_2_str(kingdoms[kingdom_name])}

YOUR TASK:
Create exactly {num_towns} distinctive towns that feel authentic to this kingdom's character. Each town should have its own identity while fitting the kingdom's overall theme.

TOWN NAMING RULES:
- Town names MUST NOT match any kingdom names: {", ".join(lst_kings) if lst_kings else "none"}
- Use evocative, fantasy-appropriate names (e.g., "Whisperwood", "Ironcross", "Silverhaven")
- Avoid generic names like "Small Village" or "Big City"

TOWN DESIGN PRINCIPLES:
1. **Variety**: Mix town sizes and purposes (trade hub, mining settlement, religious center, etc.)
2. **Logic**: Locations should make geographical sense within the kingdom description
3. **Character**: Each town should feel unique with distinct landmarks or features
4. **Integration**: Important places should reflect the kingdom's type (magic/militaristic/diplomatic/technology)

EXAMPLES OF GOOD TOWN DESCRIPTIONS:
✅ "Blackforge": Founded when exiled dwarven smiths struck gold in volcanic caves.
   Location: Southern mountain passes near active geysers.
   Places: Massive open-air forges, the Molten Anvil tavern, dwarf-king's observatory.

❌ BAD: "Small Town": A small town with a market. Near the capital. Has a church and inn.

FOR EACH TOWN PROVIDE:
- **name**: Unique fantasy name (1-2 words)
- **history**: Founding story or defining event (1 sentence, ~10 words)
- **location**: Geographical position in kingdom (~10 words)  
- **important_places**: Key landmarks reflecting town's character (~10 words)

Output as JSON array matching the TownsModel schema."""

    return [{"role": "user", "content": user_prompt}]


def gen_human_char_msgs(
    game_lore: Dict[str, Any],
    kingdom_name: str,
    town_name: str,
    num_chars: int = 1,
    char_description: Optional[Dict[str, str]] = None,
    avoid_names: List[str] = [],
) -> List[Dict[str, Any]]:
    """Generates messages to create ONE player's character"""

    if num_chars != 1:
        logger.warning(
            f"Expected num_chars=1 for structured output, got {num_chars}. Generating 1."
        )
        num_chars = 1

    # Generate random bounds for this character
    age_min = random.randint(18, 30)
    age_max = random.randint(age_min + 10, age_min + 40)
    money_min = random.randint(100, 400)
    money_max = random.randint(money_min + 200, 1000)

    world_type = game_lore.get("world", {}).get("type", "fantasy")

    user_prompt = f"""Create ONE original character based on the world, kingdom and town settings.

World Name: {game_lore["world"]["name"]}
World Description: {game_lore["world"]["description"]}

The kingdom: {dict_2_str(game_lore["kingdoms"][kingdom_name])}
The town: {dict_2_str(game_lore["towns"][kingdom_name][town_name])}

Character should include:
- A unique name (1-3 words) NOT in this banned list: {", ".join(avoid_names) if avoid_names else "none"}
- Gender: male or female only
- Occupation appropriate for a {world_type} world
- Age between {age_min} and {age_max} years
- 1-2 sentence backstory
- Emotional wounds (up to 10 words)
- Deepest motivations (up to 10 words)
- An epic goal that drives the story forward
- Physical attributes (strength, dexterity, endurance)
- Mental attributes (intelligence, wisdom)
- Communication style (5 words max)
- Notable strengths (up to 10 words)
- Notable weaknesses (up to 10 words)
- Starting gold between {money_min} and {money_max} coins
- Logical starting inventory (functional item names, 1-2 words each, max 10 items)

The character's occupation should match the world setting. Inventory items must be logical for their profession and goals."""

    return [
        {"role": "system", "content": LORE_GEN_SYS_PRT},
        {"role": "user", "content": user_prompt},
    ]


def gen_antagonist_msgs(
    game_lore: Dict[str, Any],
    player_desc: Dict[str, str],
    kingdom_name: str,
    num_chars: int = 1,
    antag_desc=None,
) -> List[Dict[str, Any]]:
    """Generates messages to create ONE antagonist"""

    if num_chars != 1:
        logger.warning(
            f"Expected num_chars=1 for structured output, got {num_chars}. Generating 1."
        )
        num_chars = 1

    # Generate random age bounds for antagonist (same logic as characters)
    age_min = random.randint(18, 30)
    age_max = random.randint(age_min + 10, age_min + 40)

    user_prompt = f"""Create ONE antagonist who opposes the human player in this world.

World Name: {game_lore["world"]["name"]}
World Description: {game_lore["world"]["description"]}

The human player:
{dict_2_str(player_desc)}

The kingdom: {dict_2_str(game_lore["kingdoms"][kingdom_name])}

The antagonist should include:
- A unique name (1-3 words)
- Occupation as a ruler or significant person in {kingdom_name}
- Age between {age_min} and {age_max} years
- 1-2 sentence backstory explaining their rise to power/influence
- An epic goal that DIRECTLY contradicts the player's goal: "{player_desc.get("goal", "unknown")}"
- Notable advantages (up to 10 words)
- Exploitable vulnerabilities (up to 10 words)
- Physical attributes (1 sentence)
- Mental attributes (1 sentence)
- Social abilities (5 words max)

The antagonist's goal must be in clear contradiction to the player's goal. They should be a worthy opponent."""

    return [
        {"role": "system", "content": LORE_GEN_SYS_PRT},
        {"role": "user", "content": user_prompt},
    ]


def gen_npc_character_msgs(
    game_lore: Dict[str, Any],
    kingdom_name: str,
    town_name: str,
    npc_occupation: str,
    npc_goal: str,
    avoid_names: List[str] = [],
) -> List[Dict[str, Any]]:
    """Generates messages to create ONE NPC character"""

    # Generate random bounds for this NPC
    age_min = random.randint(18, 30)
    age_max = random.randint(age_min + 10, age_min + 40)
    money_min = random.randint(100, 400)
    money_max = random.randint(money_min + 200, 1000)

    world_type = game_lore.get("world", {}).get("type", "fantasy")

    user_prompt = f"""Create ONE NPC character who is a {npc_occupation} in the given kingdom and town.

World Name: {game_lore["world"]["name"]}
World Description: {game_lore["world"]["description"]}

The kingdom: {dict_2_str(game_lore["kingdoms"][kingdom_name])}
The town: {dict_2_str(game_lore["towns"][kingdom_name][town_name])}

NPC Context:
- Occupation: {npc_occupation}
- Goal: {npc_goal}

The NPC should include:
- A unique name (1-3 words) NOT in this banned list: {", ".join(avoid_names) if avoid_names else "none"}
- Gender: male or female only
- Occupation: {npc_occupation}
- Age between {age_min} and {age_max} years
- 1-2 sentence backstory related to their occupation
- Emotional wounds (up to 10 words)
- Deepest motivations (up to 10 words)
- Goal: {npc_goal}
- Physical attributes (strength, dexterity, endurance)
- Mental attributes (intelligence, wisdom)
- Communication style (5 words max)
- Strong points related to occupation
- Weak points (up to 10 words)
- Starting gold between {money_min} and {money_max} coins
- Logical starting inventory for their occupation (functional item names, 1-2 words each, max 10 items)

The character should fit the {npc_occupation} role logically. Inventory items should match their occupation and goal."""

    return [
        {"role": "system", "content": LORE_GEN_SYS_PRT},
        {"role": "user", "content": user_prompt},
    ]


def gen_condition_end_game(
    game_lore: Dict[str, Any],
    player_desc: Dict[str, str],
    antagonist_desc: Dict[str, str],
    human_loc: str,
    antag_loc: str,
    num_conditions: int,
    condition: str,
) -> List[Dict[str, str]]:
    """
    Generates messages to create conditions to win or loose the game

    :param game_lore: condensed game lore, not what is shown to the player
    :param player_desc: a dictionary with description of the human player
    :param antagonist_desc: a dictionary with description of the antagonist/enemy
    :param human_loc: starting kingdom of the human player
    :param antag_loc: (starting?) location of the antagonist
    :param num_conditions: number of conditions to win/loose
    :param condition: win or loose.
    :return: messages (aka list of dictionaries)
    """
    global LORE_GEN_SYS_PRT

    conditions_prt = f"""
Generate {num_conditions} conditions to {condition} for a human player
{player_desc}

This player is against this antagonist:
{antagonist_desc}

These characters act in this world:
World Name: {game_lore["world"]["name"]}
World Description: {game_lore["world"]["description"]}

Players kingdom:
{game_lore["kingdoms"][human_loc]}

Antagonist's kingdom:
{game_lore["kingdoms"][antag_loc]}

Provide only a numbered list without any additional words"""

    return [
        {"role": "system", "content": LORE_GEN_SYS_PRT},
        {"role": "user", "content": conditions_prt},
    ]


def gen_obj_est_msgs(obj: str) -> List[Dict[str, str]]:
    """
    Generates messages to prompt for object description
    :param obj:
    :return:
    """
    global OBJ_ESTIMATOR_SYS_PROMPT

    # Use Pydantic model field descriptions for structured output
    from llm_rpg.prompts.response_models import InventoryItemDescription

    task = f"""Describe this game object: {obj}

Required JSON output format:
{{
  "name": "<shortened name, 1-2 words, no articles>",
  "type": "<one of: armor, weapon, food, drink, magical item, document, book, clothing, medical, tool, other>",
  "description": "<brief description or empty string if not applicable>",
  "action": "<how it works or empty string if not applicable>",
  "strength": "<weak/moderate/strong estimate or empty string if not applicable>"
}}

Name rules: Remove articles and shorten to 1-2 words. Examples:
- "long wooden spear" -> "spear"
- "battle axe" -> "axe"  
- "steel greatsword" -> "greatsword"

Field descriptions:
- type: {InventoryItemDescription.model_fields["type"].description}
- description: {InventoryItemDescription.model_fields["description"].description}
- action: {InventoryItemDescription.model_fields["action"].description}
- strength: {InventoryItemDescription.model_fields["strength"].description}

Return only valid JSON, no markdown formatting."""

    return [
        {"role": "system", "content": OBJ_ESTIMATOR_SYS_PROMPT},
        {"role": "user", "content": task},
    ]


def gen_npc_behavior_rules(
    npc: Dict[str, str], num_rules_per_category: int = 3
) -> List[Dict[str, str]]:
    """
    Generates user prompt for structured NPC behavioral rules.

    The system prompt with Pydantic schema is added automatically by struct_output().

    :param npc: Character description dictionary (name, goal, biography, etc.)
    :param num_rules_per_category: Rules per situational category (3-5 recommended)
    :return: User message for LLM (system added by struct_output)
    """
    import json

    user_prompt = f"""Generate behavioral rules for this NPC based on their character:

{json.dumps(npc, indent=2)}

Create exactly {num_rules_per_category} rules per category (each rule 10-15 words).

Rules must be:
- Specific actionable directives (not vague principles)
- Consistent with the NPC's goals, desires, and personality
- Useful for guiding AI decision-making in gameplay
- Different across categories (combat vs social vs moral, etc.)

Example rule quality:
❌ Bad: "Always help the weak" (too vague)
✅ Good: "Protect innocent civilians from harm even when it delays personal objectives temporarily"

Base rules on the NPC's:
- occupation (warrior fights differently than magician)
- goal (epic objective shapes priorities)
- deeper_desires and deeper_pains (emotional drivers)
- strengths and weaknesses (realistic capabilities)

Output must be valid JSON with this exact structure:
{{
  "COMBAT": ["rule1", "rule2", "rule3"],
  "NEGOTIATION": ["rule1", "rule2", "rule3"],
  "EXPLORATION": ["rule1", "rule2", "rule3"],
  "SOCIAL": ["rule1", "rule2", "rule3"],
  "MORAL": ["rule1", "rule2", "rule3"],
  "GENERAL": ["rule1", "rule2", "rule3"]
}}

Each category must contain exactly {num_rules_per_category} rules as strings in a list.
"""

    return [{"role": "user", "content": user_prompt}]


def gen_entry_point_msg(
    world_desc,
    human_player,
    human_start_k,
    k_desc,
    human_start_t,
    t_desc,
    npcs_desc,
    npc_start_location,
):
    """
    Messages to generate the starting point

    :param world_desc: dict, description of the world
    :param human_player: dict: human player character card
    :param human_start_k: str: kingdom start
    :param k_desc: dict: description of the kingdom
    :param human_start_t: start: starting town
    :param t_desc: dict: starting town description
    :param npcs_desc: dict: npc description cards
    :param npc_start_location: dict: start location of the npcs
    :return:
    """

    global LORE_GEN_SYS_PRT

    entry_point_prt = f"""Generate a starting point for the game.

This is the world:
{world_desc}

This is the human playr:
{human_player}
Starting in: 
Kingdom: {human_start_k}
{k_desc}
Town: {human_start_t}
{t_desc}

These are player's allies (NPCs):
{npcs_desc}
They start in:
{npc_start_location}

Follow these instructions:
- write 10 sentences
- the story shall provide a starting point for the further story
- provide location information
- mention your allies
- mention location of player's allies (if known)
- Write always in third person language"""

    return [
        {"role": "system", "content": LORE_GEN_SYS_PRT},
        {"role": "user", "content": entry_point_prt},
    ]


def _get_default_world_rules() -> WorldRulesModel:
    """Return default world rules for fallback"""
    return WorldRulesModel(
        MAGIC=[
            "Magic exists but is rare and difficult to master without proper training",
            "Spellcasting requires verbal components and often material components",
            "Powerful magic draws attention from authorities and rival mages",
            "Magical items are valuable commodities traded by specialized merchants",
        ],
        PHYSICS=[
            "The world follows standard physical laws with day and night cycles",
            "Seasons change gradually affecting agriculture and travel conditions",
            "Mountains create natural barriers between kingdoms and regions",
            "Rivers serve as important trade routes and sources of fresh water",
        ],
        SOCIETY=[
            "Kingdoms are ruled by monarchs advised by councils of nobles",
            "Commoners have limited political power but form majority population",
            "Merchant guilds influence economy and can sway local politics",
            "Religious institutions hold significant social and moral authority",
        ],
        GEOGRAPHY=[
            "Temperate climates dominate central regions suitable for agriculture",
            "Northern territories are colder with harsher winters and shorter growing seasons",
            "Coastal areas benefit from milder weather and maritime trade opportunities",
            "Forests provide resources but harbor dangerous creatures and outlaws",
        ],
        TECHNOLOGY=[
            "Metalworking produces quality weapons and armor for military use",
            "Agricultural tools enable efficient farming supporting population growth",
            "Transportation relies on horses, carriages, and sailing ships",
            "Communication travels at speed of messengers on horseback or ship",
        ],
    )


def _get_default_npc_rules() -> NPCBehaviorRulesModel:
    """Return default NPC behavioral rules for fallback"""
    return NPCBehaviorRulesModel(
        COMBAT=[
            "Assess the threat level before committing to direct engagement",
            "Protect allies and maintain formation during group combat situations",
            "Use available terrain and cover to gain tactical advantages",
            "Disengage when outnumbered significantly or objectives are compromised",
        ],
        NEGOTIATION=[
            "Listen carefully to understand the full request before responding",
            "Seek mutually beneficial outcomes that advance personal goals",
            "Maintain honesty while strategically revealing only necessary information",
            "Walk away from deals requiring unethical or dangerous actions",
        ],
        EXPLORATION=[
            "Move cautiously in unknown areas watching for hidden dangers",
            "Document discoveries and share important findings with the party",
            "Investigate unusual phenomena from safe distance before approaching",
            "Conserve resources when venturing into uncharted territories",
        ],
        SOCIAL=[
            "Treat others with basic respect regardless of social status",
            "Remember names and details of important contacts for future reference",
            "Build trust through consistent actions over time",
            "Avoid revealing sensitive personal information to strangers",
        ],
        MORAL=[
            "Protect innocent civilians from harm when possible without grave risk",
            "Honor commitments made unless circumstances fundamentally change",
            "Refuse requests that cause unjustified suffering to others",
            "Act with integrity even when actions go unpunished",
        ],
        GENERAL=[
            "Prioritize actions that advance long-term personal objectives",
            "Consider consequences before taking irreversible actions",
            "Adapt strategies when circumstances change unexpectedly",
            "Maintain physical and mental readiness for challenges",
        ],
    )


# Import CharacterModel and AntagonistModel for type hints
from llm_rpg.prompts.response_models import CharacterModel, AntagonistModel


def _get_default_character() -> CharacterModel:
    """Return default character for fallback"""
    return CharacterModel(
        name="Adventurer",
        gender="male",
        occupation="warrior",
        age=25,
        biography="A seasoned fighter seeking glory and adventure.",
        deeper_pains="Lost family to bandits years ago",
        deeper_desires="Build a new life and protect the innocent",
        goal="Defeat the dark lord threatening the kingdom",
        physical="Strong and agile with above-average endurance",
        mental="Practical thinker with good common sense",
        communication="Direct speaker, struggles with diplomacy",
        strengths="Skilled in combat tactics and weapon mastery",
        weaknesses="Impulsive and distrustful of authority",
        money=100,
        inventory=["steel longsword", "chainmail vest", "healing potion"],
    )


def _get_default_antagonist() -> AntagonistModel:
    """Return default antagonist for fallback"""
    return AntagonistModel(
        name="Dark Lord Malakor",
        occupation="warlock king",
        biography="An ancient sorcerer who seeks to plunge the world into eternal darkness.",
        goal="Conquer all kingdoms and enslave humanity to serve his dark masters",
        strengths="Mastery of forbidden magic and vast wealth",
        weaknesses="Overconfident and underestimates mortal ingenuity",
        physical="Ageless appearance with unnaturally strong constitution",
        mental="Genius-level intellect but consumed by paranoia",
        communication="Charismatic manipulator who inspires terror",
    )


def _get_default_npc_character() -> CharacterModel:
    """Return default NPC character for fallback"""
    return CharacterModel(
        name="Villager",
        gender="male",
        occupation="merchant",
        age=30,
        biography="A local trader who knows everyone in town.",
        deeper_pains="Lost his shop to a fire last winter",
        deeper_desires="Restore his family's reputation and wealth",
        goal="Help the hero while protecting his own interests",
        physical="Average build with tired eyes from long nights",
        mental="Street-smart but not formally educated",
        communication="Talkative and persuasive when selling goods",
        strengths="Extensive knowledge of local rumors and contacts",
        weaknesses="Greedy and easily distracted by profit",
        money=50,
        inventory=["trade goods", "small dagger"],
    )


def _get_default_kingdoms(num_kingdoms: int = 3) -> KingdomsModel:
    """
    Provide default kingdoms when generation fails.

    NOTE: Used for testing only - not passed to generate_with_retry() in production.
    Kingdom generation is critical; app should crash if it fails after retries.
    """
    defaults = [
        {
            "name": "Aethermoor",
            "history": "Ancient kingdom founded by magical scholars seeking wild magic sources.",
            "type": "magic",
            "location": "Northern highlands near crystal mountain ranges.",
            "political_system": "Magocratic council rule",
            "national_wealth": "Moderate wealth from magic artifact trade.",
            "international": "Tense relations with technocratic southern kingdoms.",
        },
        {
            "name": "Ironhold",
            "history": "Militaristic state formed through conquest and iron-fisted governance.",
            "type": "militaristic",
            "location": "Central plateau fortress surrounded by defensive mountains.",
            "political_system": "Military dictator supremacy",
            "national_wealth": "Rich in metals but poor in agriculture.",
            "international": "Aggressive expansionist policies toward neighbors.",
        },
        {
            "name": "Merchants Bay",
            "history": "Trading hub established at the convergence of three major rivers.",
            "type": "diplomatic",
            "location": "Coastal delta region with natural harbor.",
            "political_system": "Merchant guild oligarchy",
            "national_wealth": "Extremely wealthy from international trade routes.",
            "international": "Neutral mediator in regional conflicts.",
        },
    ]

    selected = defaults[:num_kingdoms] if num_kingdoms <= len(defaults) else defaults

    return KingdomsModel(kingdoms=[KingdomData(**k) for k in selected])


def _get_default_towns(num_towns: int = 3):
    """
    Provide default towns when generation fails.

    NOTE: Used for testing only - not passed to generate_with_retry() in production.
    Town generation is critical; app should crash if it fails after retries.
    """
    from llm_rpg.prompts.response_models import TownData, TownsModel

    defaults = [
        {
            "name": "Whispergate",
            "history": "Founded by exiled scholars who hid forbidden knowledge beneath cobblestones.",
            "location": "Northern forest edge overlooking misty valleys.",
            "important_places": "Ancient library tower, whispering archway, scholar's retreat garden.",
        },
        {
            "name": "Ironcross",
            "history": "Built at junction of four trade routes by mercenary companies.",
            "location": "Central plains where major highways intersect.",
            "important_places": "Massive iron cross monument, mercenary guildhall, carriage repair yards.",
        },
        {
            "name": "Silvermere",
            "history": "Fishermen discovered healing springs attracting pilgrims from distant lands.",
            "location": "Lakeshore settlement beside crystal-clear silver waters.",
            "important_places": "Healing spring shrine, fishermen's cooperative, pilgrim hostel.",
        },
    ]

    selected = defaults[:num_towns] if num_towns <= len(defaults) else defaults

    return TownsModel(towns=[TownData(**t) for t in selected])
