"""
Collection of helper tools needed for the game.
- ObjectDescriptor --> describes objects, their type, strength, action, etc.
TODO: InventoryChange --> detects changes into inventory

# - ObjectDetector --> detects all objects/tools used by the human and the AI player

"""


import logging
logger = logging.getLogger(__name__)

from typing import Dict, List, Any

from llm_rpg.templates.base_client import BaseClient
from llm_rpg.prompts.gameplay import (STORY_TELLER_SYS_PRT,
                                      gen_story_telling_msg)
from llm_rpg.prompts.lore_generation import (gen_obj_est_msgs, OBJECT_DESC)
from llm_rpg.utils.helpers import parse2structure


class ObjectDescriptor:
    def __init__(self, client: BaseClient) -> None:
        global OBJECT_DESC
        self.client = client
        self.obj_expected_flds = list(OBJECT_DESC.keys())
        self.stats = {}


    def __gen_rollback(self, obj: str) -> Dict[str, str]:
        rollback = {}
        rollback['name'] = obj
        for fld in self.obj_expected_flds:
            rollback[fld] = ''
        return rollback

    def describe(self, obj: str, **kwargs) -> Dict[str, str]:
        msgs = gen_obj_est_msgs(obj)
        response = self.client.chat(msgs, **kwargs)
        self.stats[obj] = response['stats']

        # parse the response
        response_dict = {}
        try:
            response_dict = parse2structure(response['message'], self.obj_expected_flds)
        except Exception as e:
            logger.warning(f"Could not parse response for \"{obj}\" with \"{e}\" error! Using the rollback!")
            response_dict = self.__gen_rollback(obj)

        return response_dict


