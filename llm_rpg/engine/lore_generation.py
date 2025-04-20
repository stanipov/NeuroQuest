"""
Collection of tools to generate a game lore using some basic inputs

There are currently 2 major classes:
1. GenerateWorld -- generates world and conditions to lose/win
2. GenerateCharacter -- generates characters (player/npc and player's opponent)

These classes provide tools to generate the respective lore part. They are governed
 by LoreGeneratorGvt which instantiates both of these and calls with proper arguments.
"""


import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

from llm_rpg.prompts.lore_generation import (world_desc_grim,
                                             kingdoms_traits,
                                             KINGDOM_DESC_STRUCT,
                                             TOWNS_DESC_STRUCT,
                                             CHAR_DESC_STRUCT,
                                             ANTAGONIST_DESC,
                                             gen_world_msgs,
                                             gen_kingdom_msgs,
                                             gen_towns_msgs,
                                             gen_human_char_msgs,
                                             gen_antagonist_msgs,
                                             gen_condition_end_game)
from llm_rpg.engine.tools import ObjectDescriptor

from llm_rpg.utils.helpers import (parse_kingdoms_response,
                                   parse_towns,
                                   parse_world_desc,
                                   parse_character,
                                   parse_antagonist,
                                   input_not_ok)

from llm_rpg.templates.base_client import BaseClient

import random
from time import sleep


class LoreGeneratorGvt:
    def __init__(self, client: BaseClient, **kwargs):
        """
        Governor that generates game lore. The game lore is generated as a plan/brief outline
        as it is intended for feeding into an LLM. A separate component will generate a human-readable
        text.

        :param client: the LLM client
        :param kwargs: any arguments needed in the future
        """
        global world_desc_grim
        self.client = client
        self.lore = {}
        self.game_gen_params = {}
        # LUT for inventory items
        self.lore['inventory_lut'] = {}

        # API calls delay in seconds
        # needed for rate limitations
        if "api_delay" in kwargs:
            self.api_delay = kwargs.pop('api_delay')
        else:
            self.api_delay = 0

        self.world_generator = GenerateWorld(self.client)
        self.char_gen = GenerateCharacter(self.client)
        self.ObjDesc = ObjectDescriptor(client)

        # defaults
        self.WORLD_DESC = world_desc_grim


    def generate_world(self, world_desc: str='',
                       **client_kwargs):
        if input_not_ok(world_desc, str, ''):
            world_desc = self.WORLD_DESC
        self.world_generator.gen_world(world_desc, **client_kwargs)
        self.lore.update(self.world_generator.game_lore)
        self.game_gen_params.update(self.world_generator.game_gen_params)


    def generate_kingdoms(self, num_kingdoms:int,
                          kingdom_types:str|None=None,
                          **client_kw):
        self.world_generator.gen_kingdoms(num_kingdoms, kingdom_types, **client_kw)
        self.lore.update(self.world_generator.game_lore)
        self.game_gen_params.update(self.world_generator.game_gen_params)


    def generate_towns(self, num_towns,
                       **client_kw):
        self.world_generator.gen_towns(num_towns, **client_kw)
        self.lore.update(self.world_generator.game_lore)
        self.game_gen_params.update(self.world_generator.game_gen_params)


    def generate_human_player(self, **client_kw):
        # random choice of starting location
        kingdom_name = random.choice(list(self.lore['kingdoms'].keys()))
        town_name = random.choice(list(self.lore['towns'][kingdom_name].keys()))
        #print(f"Kingdom: {kingdom_name}")
        #print(f"Town:    {town_name}")

        ans = self.char_gen.gen_characters(self.lore, "human",
                                           num_chars=1,
                                           kingdom_name=kingdom_name,
                                           town_name=town_name,
                                           **client_kw)
        _key = list(ans.keys())[0]
        self.lore['human_player'] = ans[_key]

        if 'start_location' not in self.lore:
            self.lore['start_location'] = {}

        self.lore['start_location']['human'] = {
            'kingdom': kingdom_name,
            'town': town_name
        }
        self.game_gen_params.update(self.char_gen.char_gen_params)


    def generate_antagonist(self, same_location:bool=True):
        if same_location:
            kingdom_name = self.lore['start_location']['human']['kingdom']
        else:
            max_iter = 10
            cnt = 0
            kingdom_name = random.choice(list(self.lore['kingdoms'].keys()))
            while kingdom_name == self.lore['start_location']['human']['kingdom'] and cnt < max_iter:
                kingdom_name = random.choice(list(self.lore['kingdoms'].keys()))
                cnt += 1

        ans = self.char_gen.gen_characters(self.lore, 'enemy',
                                           player_desc=self.lore['human_player'],
                                           kingdom_name=kingdom_name)
        _key = list(ans.keys())[0]
        self.lore['antagonist'] = ans[_key]

        if 'start_location' not in self.lore:
            self.lore['start_location'] = {}

        self.lore['start_location']['antagonist'] = {
            'kingdom': kingdom_name,
            'town': ""}
        self.game_gen_params.update(self.char_gen.char_gen_params)


    def generate_end_game_conditions(self, num_conditions:int=3):
        self.world_generator.gen_end_game_conditions(player_desc=self.lore['human_player'],
                                                     player_loc=self.lore['start_location']['human']['kingdom'],
                                                     antag_desc=self.lore['antagonist'],
                                                     antag_loc=self.lore['start_location']['antagonist']['kingdom'],
                                                     num_conditions=num_conditions)
        self.lore.update(self.world_generator.game_lore)
        self.game_gen_params.update(self.world_generator.game_gen_params)


    def describe_inventories(self, temperature=0.25):
        """
        TODO: this is a wrapper method which will call a method that describes items (?)
        Describes inventory elements of each item in inventories (human, NPCs, antagonist, etc.)
        :param temperature:
        :return:
        """
        if 'human_player' in self.lore:
            logger.info(f"Describing inventory items for the human player")
            inv_items = [x.strip() for x in self.lore['human_player']['inventory'].split(', ')]
            ans = self.__describe_items(inv_items, temperature)
            self.lore['inventory_lut'].update(ans)
            self.lore['human_player']['inventory'] = list(ans.keys())

        if "npc" in self.lore:
            logger.info(f"Describing inventory items fot NPCs")
            for npc in self.lore['npc']:
                logger.info(f"NPC: {npc}")
                inv_items = [x.strip() for x in self.lore['npc'][npc]['inventory'].split(', ')]
                ans = self.__describe_items(inv_items, temperature)
                self.lore['inventory_lut'].update(ans)
                self.lore['npc'][npc]['inventory'] = list(ans.keys())

        if "antagonist" in self.lore:
            if 'inventory' in self.lore["antagonist"]:
                logger.info(f"Describing inventory items for the antagonist")
                inv_items = [x.strip() for x in self.lore['antagonist']['inventory'].split(', ')]
                ans = self.__describe_items(inv_items, temperature)
                self.lore['inventory_lut'].update(ans)
                self.lore['antagonist']['inventory'] = list(ans.keys())

        logger.info(f"Done")


    def __describe_items(self, items, temperature=0.25):
        ans = {}
        for item in items:
            _t = self.ObjDesc.describe(item, temperature=temperature)
            ans[_t['name']] = _t
            sleep(self.api_delay)
        return ans


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

        :param world_desc:
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

        global kingdoms_traits
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


    def gen_towns(self,
                  num_towns,
                  **client_kw):
        """
        Generates towns for each kingdom. Provide number of towns.
        TBD: a single number for all kingdoms or introduce some variability. Issue with variability
        is that for small numbers random choices do not look that random

        :param num_towns:
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


    def gen_end_game_conditions(self,
                                player_desc:Dict[str, str],
                                player_loc:str,
                                antag_desc:Dict[str, str],
                                antag_loc:str,
                                num_conditions:int) -> None:
        """
        Generates conditions to win and loose the game given the description of the human player and its antagonist
        :param antag_loc: location (starting) of the antagonist/enemy
        :param player_loc: starting location of the human player
        :param player_desc: description of the human player
        :param antag_desc: description of the antagonist/enemy
        :param num_conditions: number of conditions
        :return:
        """

        kinds = ["win", "loose"]

        self.game_lore["end_game"] = {}
        for kind in kinds:
            logger.info(f"Generating {num_conditions} conditions to {kind}")
            try:
                cond_gen_msgs = gen_condition_end_game(self.game_lore, player_desc, antag_desc, player_loc, antag_loc,
                                                   num_conditions, kind)
                raw_response = self.client.chat(cond_gen_msgs)
                self.game_lore["end_game"][kind] = raw_response["message"]
            except Exception as e:
                logger.error(f"Could not generate conditions to \"{kind}\" with \"{e}\" error")
                raise ValueError(f"Could not generate conditions to \"{kind}\" with \"{e}\" error")
        logger.info("Done")


class GenerateCharacter:
    global CHAR_DESC_STRUCT, ANTAGONIST_DESC
    def __init__(self, client: BaseClient, **kwargs):
        global CHAR_DESC_STRUCT, ANTAGONIST_DESC
        self.client = client

        # stores all characters generated (human, antagonist, npcs, etc)
        self.characters = {}
        # store this data for possible debugging and logging
        self.char_gen_params = {}
        # a mapping between names and kinds (human, npc, etc.)
        self.characters_kinds = {}

        # defaults for expected fields for a human playable characters
        self.DEF_H_CHAR_FLDS = set(CHAR_DESC_STRUCT.keys())
        # defaults for the antagonist creation
        self.DEF_A_CHAR_FLDS = set(ANTAGONIST_DESC.keys())


    def gen_characters(self,
                      game_lore:Dict[str, str],
                      kind:str='human',
                      **kwargs) -> Dict[str, Any]:
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
        if kind == 'antagonist' or kind == 'enemy':
            characters = self.__gen_antagonist(game_lore, **kwargs)

        if not characters and characters != {}:
            logger.warning("Generation was not successful")
        else:
            self.characters.update(characters)
            # update the mapping
            for key in characters:
                self.characters_kinds[key] = kind

        return characters

    def __gen_playable_char(self, game_lore: Dict[str, str],**kwargs) -> Dict[str, str]:
        """
        Generates a string with character description. To be parsed
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
        self.char_gen_params['characters'] = char_gen_msgs

        # pop the non-llm-client related kwargs:
        for _item in ['char_desc_struct', 'num_chars', 'kingdom_name', 'town_name']:
            try:
                _ = kwargs.pop(_item)
            except Exception as E:
                pass

        try:
            raw_response = self.client.chat(char_gen_msgs, **kwargs)
        except Exception as e:
            logger.error(f"Failed to receive LLM response\"{e}\"")
            raise ValueError(f"Failed to receive LLM response\"{e}\"")

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


    def __gen_antagonist(self, game_lore: Dict[str, str],**kwargs) -> Dict[str, str]:
        """

        :param game_lore: Dict with all generated game lore
        :param kwargs:
            player_desc: a dictionary with description of the human player
            kingdom_name: kingdom where the antagonist acts/starts/etc
            antag_desc: a dictionary with instructions, if not provided, default will be used
         :return: messages (aka list of dictionaries)

        """
        human_desc = kwargs.get('player_desc', None)
        k_name = kwargs.get("kingdom_name", None)
        antag_desc = kwargs.get("antag_desc", None)

        if input_not_ok(human_desc, dict, {}):
            logger.error(f"Description of a human player can't be empty or None")
            raise ValueError(f"Description of a human player can't be empty or None")

        if input_not_ok(k_name, str, ''):
            logger.error(f"Kingdom name can't be empty or None")
            raise ValueError(f"Kingdom name can't be empty or None")

        if input_not_ok(antag_desc, dict, {}):
            logger.info(f"Using default for antagonist description")
            antag_desc = ANTAGONIST_DESC
            expected_flds = self.DEF_A_CHAR_FLDS
        else:
            expected_flds = set(antag_desc.keys)

        msgs2gen = gen_antagonist_msgs(game_lore, human_desc, k_name,1, antag_desc)
        self.char_gen_params['antagonists'] = msgs2gen

        # pop the non-llm-client related kwargs:
        for _item in ['player_desc', 'kingdom_name', 'antag_desc']:
            try:
                _ = kwargs.pop(_item)
            except Exception as E:
                pass

        try:
            raw_response = self.client.chat(msgs2gen, **kwargs)
        except Exception as e:
            logger.error(f"Failed to receive LLM response\"{e}\"")
            raise ValueError(f"Failed to receive LLM response\"{e}\"")

        ans = {}
        try:
            ans = parse_antagonist(raw_response['message'], expected_flds)
        except Exception as e:
            logger.warning(f"Could not part the LLm response with \"{e}\"")

        return ans