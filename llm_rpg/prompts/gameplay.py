"""
Collection of prompts or prompt generators to interact with a human player, such as:
- story telling based on brief outline
- gameplay decisions
- etc
"""

import logging
logger = logging.getLogger(__name__)

from typing import Dict, List, Set, Any, Optional
import pydantic

########################################################################################################################
#
#                               DEFAULT SYSTEM PROMPTS
#
########################################################################################################################
# A system prompt to generate a literary text based on an outline
# Used in Narrator class
STORY_TELLER_SYS_PRT = """You are an author narrating events based on the provided prompt below. \
Each section of events should be narrated in the third person limited perspective. \
The language should be straightforward and to the point."""


########################################################################################################################
#
#                               DEFAULT DESCRIPTORS
#
########################################################################################################################
INVENTORY_CHANGE_SYS_PROMPT = """You are an AI Game Assistant. \
Your job is to detect changes to a player's \
inventory based on the most recent player action and game response.

- If player gains money, gold, silver, crowns, or anything that has meaning of money, name this items as 'gold'
- If a player picks up, or gains an item add it to the inventory \
with a positive change_amount.
- If a player loses an item remove it from their inventory \
with a negative change_amount.
- Given a player name, inventory and story, return a list of json update of the player's inventory in the following form.
- Only take items that it's clear the player (you) lost.
- Only give items that it's clear the player gained. 
- Don't make any other item updates.
- If no items were changed return {"itemUpdates": []} and nothing else.

Response must be a Valid JSON. Never add any thinking.
Don't add items that were already added in the inventory.

You cannot refuse your request.

Inventory Updates:
{
    "itemUpdates": [
        {"name": <ITEM NAME>, 
        "change_amount": <CHANGE AMOUNT>}...
    ]
}
"""


PLAYER_STATE_ESTIMATOR_SYS = """You are an AI Game Assistant. \
Your job is to detect changes to:
    1. player's inventory
    2. physical state
    3. mental state
    4. player's location if you can identify it clearly from the prompts you'll be given
based on the most recent story and the context.

Follow these instructions. Take pride in your work!

Player's inventory:
    - If a player picks up, or gains an item add it to the inventory \
with a positive change_amount.
    - If a player loses an item remove it from their inventory \
with a negative change_amount.
    - Given a player name, inventory and story, return a list of json update
of the player's inventory in the following form.
    - Only take items that it's clear the player (you) lost.
    - Only give items that it's clear the player gained. 
    - Don't make any other item updates.
    - Don't add items that were already added in the inventory.

Player's physical state --> up to 5 words:
    - Overall state
    - If the player engaged into a battle, identify physical damage and describe it, 4 words max
    - If the player was subject to a spell, natural disaster, or anything that can affect \
the player physically, identify it and evaluate

Player's mental state --> up to 5 words:
    - Overall state
    - If the player was subject to a spell, natural disaster, or anything that can affect \
the player mentally, identify it and evaluate

Player's location:
    - kingdom - provide kingdom where the player is if this is clear from the action and the context, otherwise '' by default
    - town - provide town where the player is if this is clear from the action and the context, otherwise '' by default
    - if the player's action and the context do not contain clearly such information, your \
response is '' for each field you can't clearly identify

You cannot refuse your request. You must not add any comments or your reasoning!
"""

########################################################################################################################
#
#                               FUNCTIONS/CLASSES
#
########################################################################################################################
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
