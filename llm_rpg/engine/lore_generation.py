from llm_rpg.prompts.lore_generation import (kingdoms_traits,
                                             world_desc_discworld,
                                             world_desc_grim,
                                             gen_world_msgs,
                                             gen_kingdom_msgs,
                                             gen_towns_msgs)
from llm_rpg.utils.helpers import (dict_2_str,
                                   parse_kingdoms_response,
                                   parse_towns,
                                   parse_world_desc)
from llm_rpg.templates.base_client import BaseClient
from typing import Dict, List, Set, Any, Union


class GenerateWorld:
    def __init__(self, client: BaseClient, **kwargs):
        """Init the class. Not sure what shall be here"""
        pass

    def gen_world(self, **kwargs):
        """
        Generates the world description. Provide world description

        :param kwargs:
        :return:
        """
        return

    def gen_kingdoms(self, num_kingdoms:int, kingdom_traits:str, **kwargs):
        """ Generates kingdoms in the world. Provide number of kingdoms, their traits
        """
        return

    def gen_towns(self, num_towns, world, kingdoms):
        """
        Generates towns for each kingdom. Provide number of towns.
        TBD: a single number for all kingdoms or introduce some variability. Issue with variability
        is that for small numbers random choices do not look that random

        :param num_towns:
        :param world:
        :param kingdoms:
        :return:
        """
        return






