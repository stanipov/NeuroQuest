from abc import ABC, abstractmethod
from typing import List, Dict, Any, Union


class BaseGameMemory(ABC):
    def __init__(self, *args, **kwargs) -> Any:
        """ Anything needed to init """
        raise NotImplementedError()


    def create_inventory(self, *args, **kwargs):
        """
        Creates inventory and items tables.
        Inventory:
            character: str: Player/NPC name
            item: str: item name, e.g. "axe", etc.
            money: int: funds of the character
            -- primary keys: character, item
        Items:
            item: str: name of the item
            description: str: item description
            type: str: type of item, e.g. weapon/armor/...
            action: str: how the item works
            strength: str: effect of the item
            -- primary key: item

        :param args:
        :param kwargs:
        :return:
        """
        raise NotImplementedError()


    def create_game_state(self, *args, **kwargs):
        """
        Created game table. It stores responses of human, NPC, and the game:
        Schema:
            turn: int: >=0; turn number
            ai: str: AI response. Human and NPCs respond to this message. At turn=0, this will be the
                    entry point of the game
            human: str: human response to the AI
            <npc_1_name>: str: response of NPC_1 (it will be an actual name)
            ...
            <npc_N_name>: str: response of NPC_N (it will be an actual name)
            -- primary key: turn

        :param args:
        :param kwargs:
        :return:
        """
        raise NotImplementedError()


    def gen_context(self, *args, **kwargs):
        """
        Generates context for AI/NPC response/actions. This is a generic function.
        It can be only last N turns, or can be the RAG-like search. Details shall be decided
        upon creation of respective class

        :param args:
        :param kwargs:
        :return:
        """
        raise NotImplementedError()


