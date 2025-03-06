from typing import List, Dict, Any
import logging
logger = logging.getLogger(__name__)

from llm_rpg.prompts.lore_generation import (kingdoms_traits,
                                             KINGDOM_DESC_STRUCT,
                                             TOWNS_DESC_STRUCT,
                                             gen_world_msgs,
                                             gen_kingdom_msgs,
                                             gen_towns_msgs)
from llm_rpg.utils.helpers import (parse_kingdoms_response,
                                   parse_towns,
                                   parse_world_desc)
from llm_rpg.templates.base_client import BaseClient


class GenerateWorld:
    def __init__(self, client: BaseClient, **kwargs):
        """Init the class. Not sure what shall be here"""
        self.client = client
        self.game_lore = {}
        self.game_gen_params = {}
        # defaults
        self.expected_flds_kingdoms_def = set(KINGDOM_DESC_STRUCT.keys())
        self.expected_flds_towns_def = set(TOWNS_DESC_STRUCT.keys())


    def gen_world(self, world_desc: str, **client_kw):
        """
        Generates the world description. Provide world description

        :param client_kw:
        :return:
        """
        msg_world_gen = gen_world_msgs(world_desc)
        raw_world_response = self.client.chat(msg_world_gen, **client_kw)
        world_ai = parse_world_desc(raw_world_response['message'])
        logger.info(f"Created world: {world_ai['name']}")
        logger.debug(f"Prompt tokens: {raw_world_response['stats']['prompt_tokens']}")
        logger.debug(f"Eval tokens: {raw_world_response['stats']['eval_tokens']}")
        self.game_lore['world'] = world_ai
        self.game_gen_params['model'] = self.client.model_name
        self.game_gen_params['world'] = msg_world_gen


    def gen_kingdoms(self, num_kingdoms:int, kingdom_types:str|None=None, **client_kw):
        """
        Generates kingdoms in the world. Provide number of kingdoms, their types
        """

        if kingdom_types is None:
            kingdom_types = kingdoms_traits
        if kingdom_types is not None and kingdom_types == "":
            kingdom_types = kingdoms_traits

        kingdoms_msg = gen_kingdom_msgs(num_kingdoms, kingdom_types, self.game_lore['world'])
        kingdoms_raw_response = self.client.chat(kingdoms_msg, **client_kw)
        kingdoms_ai = parse_kingdoms_response(kingdoms_raw_response['message'], self.expected_flds_kingdoms_def)
        logger.info(f"Created kingdoms: {list(kingdoms_ai.keys())}")
        logger.debug(f"Prompt tokens: {kingdoms_raw_response['stats']['prompt_tokens']}")
        logger.debug(f"Eval tokens: {kingdoms_raw_response['stats']['eval_tokens']}")
        self.game_lore['kingdoms'] = kingdoms_ai
        self.game_gen_params['kingdoms'] = kingdoms_msg


    def gen_towns(self, num_towns, **clinet_kw):
        """
        Generates towns for each kingdom. Provide number of towns.
        TBD: a single number for all kingdoms or introduce some variability. Issue with variability
        is that for small numbers random choices do not look that random

        :param num_towns:
        :param world:
        :param kingdoms:
        :return:
        """

        self.game_lore['towns'] = {}
        self.game_gen_params['towns'] = {}

        for kingdom in self.game_lore['kingdoms']:
            logger.info(f"Generating {num_towns} towns for {kingdom}")
            msg_towns_k = gen_towns_msgs(num_towns, self.game_lore['world'], self.game_lore['kingdoms'], kingdom)
            towns_raw_response = self.client.chat(msg_towns_k, **clinet_kw)
            logger.debug(f"Prompt tokens: {towns_raw_response['stats']['prompt_tokens']}")
            logger.debug(f"Eval tokens: {towns_raw_response['stats']['eval_tokens']}")
            towns = parse_towns(towns_raw_response['message'], self.expected_flds_towns_def)
            self.game_lore['towns'][kingdom] = towns
            self.game_gen_params['towns'][kingdom] = msg_towns_k


class GenerateCharacter:
    def __init__(self, client: BaseClient, **kwargs):
        self.client = client
        # stores all characters generated (human, antagonist, npcs, etc)
        self.characters = {}

    def gen_character(self, kind:str='human', **kwargs) -> Dict[str, Any]:
        """
        Creates a character

        :param kind: human, antagonist, npc
        :param kwargs:
        :return:
        """
        raw_response = self.__gen_character_raw()
        self.characters[kind] = self.__parse_char_response(raw_response, **kwargs)
        return self.characters[kind]

    def __gen_character_raw(self, kind:str='human', **kwargs) -> str:
        """
        Generates a string with character description. To be parsed
        :param kind: human, antagonist, npc
        :param kwargs:
        :return:
        """
        return ""

    def __parse_char_response(self, response:str, **kwargs) -> Dict[str, Any]:
        """
        Parses the raw response into a dictionary

        :param response:
        :param kwargs:
        :return:
        """
        return {}

