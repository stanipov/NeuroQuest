from typing import List, Dict, Any
import logging
logger = logging.getLogger(__name__)

from llm_rpg.prompts.lore_generation import (kingdoms_traits,
                                             KINGDOM_DESC_STRUCT,
                                             TOWNS_DESC_STRUCT,
                                             CHAR_DESC_STRUCT,
                                             gen_world_msgs,
                                             gen_kingdom_msgs,
                                             gen_towns_msgs,
                                             gen_human_char_msgs)
from llm_rpg.utils.helpers import (parse_kingdoms_response,
                                   parse_towns,
                                   parse_world_desc,
                                   parse_character)
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


    def gen_towns(self, num_towns, **client_kw):
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
            towns_raw_response = self.client.chat(msg_towns_k, **client_kw)
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
        # defaults for expected fields for a human playable characters
        self.DEF_H_CHAR_FLDS = set(CHAR_DESC_STRUCT.keys())

    def gen_characters(self,
                      game_lore:Dict[str, str],
                      kind:str='human',**kwargs) -> Dict[str, Any]:
        """
        Creates a character

        :param kind: human, antagonist, npc
        :param kwargs:
            char_desc_struct -- a dictionary with mandatory fields to generate
            num_char -- number of characters to generate
        :return:
        """

        characters = None

        if kind == 'human':
            characters = self.__gen_playable_char(game_lore, **kwargs)
            logger.info(f'Generated {len(characters.keys())} characters')

        if not characters and characters != {}:
            logger.warning("Generation was not successful")
        else:
            self.characters.update(characters)

        return characters

    def __gen_playable_char(self, game_lore: Dict[str, str],**kwargs) -> Dict[str, str]:
        """
        Generates a string with character description. To be parsed
        :param kind: human, antagonist, npc
        :param kwargs: These are expected
            char_desc_struct -- a dictionary with mandatory fields to generate, if None, default is used
            num_chars -- number of characters to generate, defaults to 1
            kingdom_name -- kingdom name
            town_name -- town name
        :return:
        """

        char_description = kwargs.get('char_desc_struct', None)
        num_chars = kwargs.get('num_chars', 1)

        var2verify = ['kingdom_name', 'town_name']
        for varname in var2verify:
            var = kwargs.get(varname, '')
            if var and var == '':
                logger.error(f"Expected \"{varname}\" to be a string type, got \"{var}\"")
                raise ValueError(f"Expected \"{varname}\" to be a string type, got \"{var}\"")

        kingdom_name = kwargs.get('kingdom_name', '')
        town_name = kwargs.get('town_name', '')

        names2avoid = list(self.characters.keys())
        char_gen_msgs = gen_human_char_msgs(game_lore, kingdom_name, town_name,
                                            num_chars, char_description, names2avoid)
        raw_response = self.client.chat(char_gen_msgs)
        if char_description is None:
            expected_flds = self.DEF_H_CHAR_FLDS
        else:
            expected_flds = set(char_description.keys())

        char_desc_str = raw_response['message']
        characters = {}
        try:
            characters = parse_character(char_desc_str, expected_flds)
        except Exception as e:
            logger.warning(f"Error while parsing character generation response with error \"{e}\"")

        return characters