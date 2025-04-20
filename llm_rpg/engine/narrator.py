"""
Collection(?) of classes (?) to convert an outline in a dictionary/short description
into an appealing text to be shown to the human player
"""


import logging
logger = logging.getLogger(__name__)

from typing import Dict, Any
import json

from llm_rpg.templates.base_client import BaseClient
from llm_rpg.prompts.gameplay import (STORY_TELLER_SYS_PRT,
                                      gen_story_telling_msg)


class Narrator:
    def __init__(self, client: BaseClient, **kwargs):
        self.client = client
        # Keeping stats in case
        self.stats = {}

    def narrate(self, txt: Dict[str, Any]|str, **kwargs) -> str:

        if type(txt) not in [str, dict]:
            logger.error(f"Input must be a string or a dictionary, got {type(txt)}")
            raise ValueError(f"Input must be a string or a dictionary, got {type(txt)}")

        _msg = gen_story_telling_msg(txt)
        response = self.client.chat(_msg, **kwargs)

        if type(txt) == dict:
            key = json.dumps(txt, sort_keys=True)
        else:
            key = txt

        self.stats[key] = response['stats']
        logger.debug(f"Prompt tokens: {response['stats']['prompt_tokens']}")
        logger.debug(f"Eval   tokens: {response['stats']['eval_tokens']}")
        return response['message']

