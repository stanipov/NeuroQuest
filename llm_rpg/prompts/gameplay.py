"""
Collection of prompts or prompt generators to interact with a human player, such as:
- story telling based on brief outline
- gameplay decisions
- etc
"""

import logging
logger = logging.getLogger(__name__)

from typing import Dict, List, Set, Any, Optional

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
