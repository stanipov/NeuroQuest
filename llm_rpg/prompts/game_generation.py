"""
Collection of prompts to generate the world and the lore
"""
from ..utils.helpers import dict_2_str

from typing import Dict, List, Set, Any
########################################################################################################################
# Set of default prompts
kingdoms_traits = """The world has many kingdoms. They can be very different:
1. magic, they rely on solving their problems on magic. Magicians are very respected
2. militaristic, they have very strong armies, excell in warfare, tactics. They can be very aggressive towards \
other parties.
3. diplomatic, these can trick anyone. They are very good in deception and plots against others. You never know \
what's happening till it's too late.
4. technology, they combine magic and technology, scientific inquiry is highly valued. These places \
are known for mass production and highly educated people. Their armies are strong and fearsome, but they \
are not interested in conquests, they want trade and earn money."""

world_desc = """This is Discworld similar to one of Terry Pratchett's one. \
This is a flat world. Sun orbits around the disc. There are long summers and \
long and harsh winters. The center region of the Discworld has no seas and oceans, \
it's dry and deserted. The outer part has seas and oceans. They make the climate mild.

The world is full of magic. There are natural sources of wild magic. Weird things \
happen there, e.g. a reverse pyramid. Humans domesticated magic, and these people \
are magicians. 

Light travels very slowly when meets a strong magical field. There is a special color \
for magic: octarin.

The world is populated by different fairy creatures, such as elves, goblins, trolls, \
dragons. 

Many gods rule over the world. They are lazy, self-centered, and do not care much about \
creatures living on the Discworld. Occasionally they intervene, but things never go well \
when the do it."""
########################################################################################################################
def gen_world_prompt(world_desc:str)-> List[Dict[str, str]]:
    """
    Returns a prompt to generate world description.

    :param world_desc: string describing some world peculiarities
    :return:
    """
    world_system_prompt = """Your job is to help create \
interesting fantasy worlds that players would \
love to play in.
Instructions:
- Only generate in plain text without formatting.
- Use simple clear language without being flowery.
- You must stay below 3-5 sentences for each description.
- You never respond with a markdown, only plain text as instructed."""

    world_prompt = f"""Generate a creative description of a unique fantasy world. Be poetic. \
These are world properties:
{world_desc}

Output content in the form:
World Name: <WORLD NAME>
World Description: <WORLD DESCRIPTION>"""

    return [
        {"role": "system", "content": world_system_prompt},
        {"role": "user", "content": world_prompt}
    ]


def gen_kindgom_gen_prompt(num_kingdoms:int,
                           kingdoms_traits:str,
                           world:Dict[str,str]) -> List[Dict[str, str]]:
    """
    Returns a prompt to generate kingdoms

    :param num_kingdoms: int number of kingdoms to generate
    :param kingdoms_traits: str traits/description of kingdoms
    :param world: world description
    :return:
    """
    system_prompt_k = """You are AI Game Master who plans and outlines RPG \
game mechanics and game worlds. Your job is to help to create \
interesting fantasy worlds that players would love to play in.

Your answers shall be very short and outline only important \
information. You follow following instructions:
- Only generate in plain text without formatting.
- Use simple clear language without being flowery.
- You must provide short answers.
- You strictly follow your instructions.
- You never add anything from yourself.
    """

    s = ""
    for i in range(num_kingdoms):
        s += f"""Kingdome {i + 1}: <kingdome name>
history: brief history of the kingdome, (1 sentence, 10 words)
type: one of the kingdom generic descriptions, one word
location: up to 1 sentence
political_system: up to five words
national_wealth: up to ten words
international: interaction with neighbors (include for each kingdom), up to one sentence, 10 words

    """

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
        {"role": "system", "content": system_prompt_k},
        {"role": "user", "content": kingdoms_prompt}]


def gen_towns_prompt(num_towns, world, kingdoms, kingdom_name):
    """
    Generates towns in a kingdom
    """
    system_prompt_towns = f"""You are AI Game Master who plans and outlines RPG \
game mechanics and game worlds. Your job is to help to create \
interesting fantasy worlds that players would love to play in.

Your answers shall be very short and outline only important \
information. You follow following instructions:
- Only generate in plain text without formatting.
- Use simple clear language without being flowery.
- You must provide short answers.
- You strictly follow your instructions.
- You never add anything from yourself.
"""

    lst_kings = [x for x in kingdoms if x != kingdom_name]
    t_templ = ""
    for i in range(num_towns):
        t_templ += f"""Town {i + 1}: <town name>
history: brief history of the town, (1 sentence, max 10 words)
location: up to 10 words
important_places: up to 1 sentence, max 10 words, avoid these names: {', '.join(lst_kings)}

"""
    town_prompt = f"""Use this information of about the world
World Name: {world['name']}
World Description: {world['description']}
and the kingdom: 
{dict_2_str(kingdoms[kingdom_name])}

to create {num_towns} different towns for a fantasy kingdom and world using this template:
{t_templ}"""

    return [
        {"role": "system", "content": system_prompt_towns},
        {"role": "user", "content":  gen_towns_prompt(num_towns, world, kingdoms, kingdom_name)}]