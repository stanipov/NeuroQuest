"""
Collection of prompts to generate the world and the lore
"""
from ..utils.helpers import dict_2_str
import logging
logger = logging.getLogger(__name__)

from typing import Dict, List, Set, Any, Optional


########################################################################################################################
# default descriptions
# instructions to generate a kingdom
# these will be transferred to the LLMs
KINGDOM_DESC_STRUCT= {
    "history": "brief history of the kingdom, (1 sentence, 10 words)",
    "type": "one of the kingdom generic descriptions, one word",
    "location": "up to 1 sentence",
    "political_system": "up to five words",
    "national_wealth": "up to ten words",
    "international": "interaction with neighbors (include for each kingdom), up to one sentence, 10 words",
}

# instructions to generate a town in a kingdom
TOWNS_DESC_STRUCT = {
    "history": "brief history of the town, (1 sentence, max 10 words)",
    "location": "geographical location of the town in the kingdom, up to 10 words",
    "important_places": "important places in the town, up to 1 sentence, max 10 words",
}

# Instructions to generate a character
# If you want to change it, follow these rules:
# - never add "name" field, it will break internals
# - "goal" field with the relevant description must be present, as its absence will break internals
CHAR_DESC_STRUCT = {
    "gender": "character's gender, pick from: male",
    "occupation": "pick one or two from warrior, researcher, magician, crook, theft, outcast",
    "age": "pick between 20 to 35",
    "biography": "a brief biography, 1-2 sentences",
    "deeper_pains": "describe deeper pains, 1 sentence up to 10 words",
    "deeper_desires": "describe deeper desires, 1 sentence up to 10 words",
    "goal": "describe character's goal in the game, 1 sentence up to 10 words. Character's goal must be something epic and significant",
    "strengths": "1 sentence up to 10 words",
    "weaknesses": "1 sentence up to 10 words",
    "inventory": """describe items the character has, up to 7 items, single string. Follow these rules for forming inventory:
- Inventory must be in a reasonable agreement with character's goals, occupation, and biography. 
- If the player is a warrior, it shall include armor (never leather!!!) and a weapon
- If a player is a magician, the inventory must include relevant magical items
- All inventory elements must fit the goal of the character"""
}

# Instructions to generate human player's antagonist
# If you want to change it, follow these rules:
# - never add "name" field, it will break internals
# - "goal" field with the relevant description must be present, as its absence will break internals
ANTAGONIST_DESC = {
    "occupation": "antagonist's position in the kingdom (ruler, magician, etc.)",
    "biography": "a brief biography, 1-2 sentences",
    "goal": "antagonist's goal in the game. It must be in a clear \
    contradiction to goal of the human player, you must clearly write it.",
    "strengths": "1 sentence up to 10 words",
    "weaknesses": "1 sentence up to 10 words"
}

# Generic traits/descriptions of kingdoms. The LLM will pick randomly some of these
kingdoms_traits = """The world has many kingdoms. They can be very different:
1. magic, they rely on solving their problems on magic. Magicians are very respected
2. militaristic, they have very strong armies, excell in warfare, tactics. They can be very aggressive towards \
other parties.
3. diplomatic, these can trick anyone. They are very good in deception and plots against others. You never know \
what's happening till it's too late.
4. technology, they combine magic and technology, scientific inquiry is highly valued. These places \
are known for mass production and highly educated people. Their armies are strong and fearsome, but they \
are not interested in conquests, they want trade and earn money."""

# World descriptions
# Inspired by Terry Pratchett
world_desc_discworld = """This is Discworld similar to one of Terry Pratchett's one. \
This is a flat world. Sun orbits around the disc. There are long summers and \
long and harsh winters. The center region of the Discworld has no seas and oceans, \
it's dry and deserted. The outer part has seas and oceans. They make the climate mild.

The world is full of magic. There are natural sources of wild magic. Weird things \
happen there, e.g. a reverse pyramid. Humans domesticated magic, and these people \
are magicians. 

Light travels very slowly when meets a strong magical field. There is a special color \
for magic: octarine.

The world is populated by different fairy creatures, such as elves, goblins, trolls, \
dragons. 

Many gods rule over the world. They are lazy, self-centered, and do not care much about \
creatures living on the Discworld. Occasionally they intervene, but things never go well \
when the do it."""

# Something grim, work in progress
world_desc_grim = """- This is fantasy world where magic is strong.
- The world is inherently unfriendly place.
- Climate is good in the South, but more northern regions are harsher.
- The world has long winters and summers, which change relatively fast.
- Many creatures are indifferent to humans, but some are very unfriendly.
- The world is populated with humans, elves, trolls, goblins, dragons.
- Gods are present, but they are lazy, self-centered, arrogant, and cruel. The gods are not very powerful.
- There several large continents, but people have very vague knowledge of other continents."""
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

# A system prompt to generate a literary text based on an outline
STORY_TELLER_SYS_PRT = """You are an author narrating events based on the provided prompt below. \
Each section of events should be narrated in the third person limited perspective. \
The language should be straightforward and to the point."""
########################################################################################################################
def gen_world_msgs(world_desc:str) -> List[Dict[str, str]]:
    """
    Returns a prompt to generate world description.

    :param world_desc: string describing some world peculiarities
    :return:
    """

    global LORE_GEN_SYS_PRT
    world_prompt = f"""Generate a creative description of a unique fantasy world. Be poetic. \
These are world properties:
{world_desc}

Output content in the form:
World Name: <WORLD NAME>
World Description: <WORLD DESCRIPTION>"""

    return [
        {"role": "system", "content": LORE_GEN_SYS_PRT},
        {"role": "user", "content": world_prompt}
    ]


def gen_kingdom_msgs(num_kingdoms:int,
                     kingdoms_traits:str,
                     world:Dict[str,str]) -> List[Dict[str, str]]:
    """
    Returns a prompt to generate kingdoms

    :param num_kingdoms: int number of kingdoms to generate
    :param kingdoms_traits: str traits/description of kingdoms
    :param world: world description
    :return:
    """
    global LORE_GEN_SYS_PRT

    if num_kingdoms < 1:
        logger.warning(f"Expected \"num_kingdoms\">=1, got {num_kingdoms}. Set \"num_kingdoms\"=1!")
        num_kingdoms = 1

    s = ""
    for i in range(num_kingdoms):
        s += f"""Kingdom {i + 1}: <kingdom name>\n"""
        for fld, val in KINGDOM_DESC_STRUCT.items():
            s += f"{fld}: {val}\n"
        s += '\n'

    kingdoms_prompt = f"""Create a brief outline of {num_kingdoms} different kingdoms \
for a fantasy world. This is the actual world:
World Name: {world['name']}
World Description: {world['description']}

Follow these kingdom generic descriptions:
{kingdoms_traits}
For each kingdom choose randomly several traits from the above and mix them. \
Never add anything from yourself, just what is asked. \
Avoid "Here are the three kingdoms:" and etc.

It is very important that your output strictly follows this template:
{s}"""

    return [
        {"role": "system", "content": LORE_GEN_SYS_PRT},
        {"role": "user", "content": kingdoms_prompt}]


def gen_towns_msgs(num_towns, world, kingdoms, kingdom_name) -> List[Dict[str, Any]]:
    """
    Generates towns in a kingdom
    """

    global LORE_GEN_SYS_PRT

    lst_kings = [x for x in kingdoms if x != kingdom_name]

    if num_towns < 1:
        logger.warning(f"Expected \"num_towns\">=1, got {num_towns}. Set \"num_towns\"=1!")
        num_towns = 1

    t_templ = ""
    for i in range(num_towns):
        t_templ += f"""Town {i + 1}: <town name>\n"""
        for fld, val in TOWNS_DESC_STRUCT.items():
            t_templ += f"{fld}: {val}\n"
        t_templ += f"avoid these names: {', '.join(lst_kings)}\n"
        t_templ += '\n'

    town_prompt = f"""Use this information of about the world
World Name: {world['name']}
World Description: {world['description']}
and the kingdom: 
{dict_2_str(kingdoms[kingdom_name])}

to create {num_towns} different towns for a fantasy kingdom and world using this template:
{t_templ}"""

    return [{"role": "system", "content": LORE_GEN_SYS_PRT},
            {"role": "user", "content":  town_prompt}]


def gen_human_char_msgs(game_lore: Dict[str, Any],
                        kingdom_name: str,
                        town_name: str,
                        num_chars: int,
                        char_description: Optional[Dict[str, str] | None] = None,
                        avoid_names: List[str] = []) -> List[Dict[str, Any]]:
    """
    Generates messages to create player's character
    :param num_chars: number of characters to generate
    :param avoid_names: list (if any) names banned from usage
    :param kingdom_name: dictionary with description of the kingdom
                    where the human character is created
    :param town_name: town
    :param char_description: optional, a dictionary with character description.
    :return:
    """
    global  LORE_GEN_SYS_PRT, CHAR_DESC_STRUCT
    if not char_description or (char_description != {} and type(char_description) != dict):
        char_description = CHAR_DESC_STRUCT
        logger.info(f"Using default description")

    # a character must have own goal in the game
    if 'goal' not in char_description:
        char_description.update({'goal':CHAR_DESC_STRUCT['goal']})

    if num_chars < 1:
        logger.warning(f"Expected \"num_chars\">=1, got {num_chars}. Set \"num_chars\"=1!")
        num_chars = 1

    char_str = ""
    for i in range(num_chars):
        char_str += f"name{i + 1}: character's name\n"
        for fld, val in char_description.items():
            char_str += f"{fld}: {val}\n"
        char_str += '\n'

    char_instruct = f"""Create {num_chars} characters based on the world, kingdom \
and town the character is in. Describe the character's appearance and \
profession, as well as their deeper pains and desires.

World Name: {game_lore['world']['name']}
World Description: {game_lore['world']['description']}

The kingdom: {dict_2_str(game_lore['kingdoms'][kingdom_name])}

The town: {dict_2_str(game_lore['towns'][kingdom_name][town_name])}

Your response must follow these instructions:
{char_str}
"""

    if avoid_names and avoid_names != []:
        char_instruct += f"You may not to use these names: {', '.join(avoid_names)}"

    return [{'role': 'system', 'content': LORE_GEN_SYS_PRT},
            {'role': 'user', 'content': char_instruct}]


def gen_antagonist_msgs(game_lore: Dict[str, Any],
                        player_desc: Dict[str, str],
                        kingdom_name: str,
                        num_chars: int = 1,
                        antag_desc=None) -> List[Dict[str, Any]]:
    global ANTAGONIST_DESC, LORE_GEN_SYS_PRT

    if not antag_desc or (antag_desc != {} and type(antag_desc) != dict):
        antag_desc = ANTAGONIST_DESC
        logger.info(f"Using default description")

    char_str = ""
    for i in range(max(num_chars, 1)):
        char_str += f"name{i + 1}: character's name\n"
        for fld, val in antag_desc.items():
            if fld == 'goal' and 'goal' in player_desc:
                char_str += f"{fld}: {val}. The player's goal: {player_desc['goal']}\n"
            else:
                char_str += f"{fld}: {val}\n"
        char_str += '\n'

    antag_char_prompt = f"""Create an antagonist to a human character based on the world description:
World Name: {game_lore['world']['name']}
World Description: {game_lore['world']['description']}

The human player: 
{dict_2_str(player_desc)}

The antagonist is a ruler or a significant person of {kingdom_name}. This is description of the kingdom:
{dict_2_str(game_lore["kingdoms"][kingdom_name])}

Create your response based on these guidelines:
{char_str}
"""

    return [
        {'role': 'system', 'content': LORE_GEN_SYS_PRT},
        {'role': 'user', 'content': antag_char_prompt}
    ]


def gen_condition_end_game(game_lore: Dict[str, Any],
                           player_desc: Dict[str, str],
                           antagonist_desc: Dict[str, str],
                           human_loc: str,
                           antag_loc: str,
                           num_conditions: int,
                           condition: str) -> List[Dict[str, str]]:
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
World Name: {game_lore['world']['name']}
World Description: {game_lore['world']['description']}

Players kingdom:
{game_lore['kingdoms'][human_loc]}

Antagonist's kingdom:
{game_lore['kingdoms'][antag_loc]}

Provide only a numbered list without any additional words"""

    return [{'role': 'system', 'content': LORE_GEN_SYS_PRT},
            {'role': 'user', 'content': conditions_prt}]

def gen_story_telling_msg(txt: Dict[str, Any]|str) -> List[Dict[str, str]]:
    """
    Generates messages to rewrite an outline to an appealing text to show to the human player
    :param txt: dictionary or a text to rewrite
    :return: List[Dict[str, Str]]
    """
    global STORY_TELLER_SYS_PRT

    task = f"""Rewrite the following outline into a concise, coherent, and engaging literary text:
{txt}"""
    if hasattr(txt, 'keys'):
        task += f"\nYou must include information from these fields in your response: {txt.keys()}."
    task += "\nWrite 5 sentences maximum."

    return [{'role': 'system', 'content': STORY_TELLER_SYS_PRT},
            {'role': 'user', 'content': task}]