"""
Classes/methods to work with memory
"""

from itertools import cycle
from typing import List, Dict


class MsgHistory:
    def __init__(self, starting_point: str, roles: List[str]):
        """
        Message history. The starting role will always be the first
        in the "roles" list because ordering of messages is important
        and these messages will be used as context and memory.

        The history is organized in lists of dictionaries:
        [
            [{'role': 'r1', 'message': msg1}, {'role': 'r2', 'message': msg2}],
            ...

            ...
            [{'role': 'r1', 'message': msg1}, {'role': 'r2', 'message': msg2}]
        ]
        roles: ['r1', 'r2'], and ordering is important.

        The class tracks the next role and will raise value error in case of the mismatch.
        This ensures 1) correct ordering 2) new list of message groups will be created automatically
        and correctly
        """

        self.__roles = cycle(roles)
        self.__roles_set = set(roles)
        self.__num_roles = len(roles)
        self.__history = [[{'role': next(self.__roles),
                            'message': starting_point}]]
        self.__next_fld = next(self.__roles)


    def add(self, msg: str, role: str) -> None:
        """
        Adds a message to the latest list of messages. If the
        target list is full, it will append and start with this role.
        :param msg: Textual message to save
        :param role: A role attributed to the message
        :return: None
        """
        if role not in self.__roles_set:
            raise ValueError(f"Got unexpected role \"{role}\"")

        if len(self.__history[-1]) >= self.__num_roles:
            self.__history.append([])

        if role != self.__next_fld:
            raise ValueError(f"Expected \"{self.__next_fld}\", got \"{role}\"")
        else:
            self.__history[-1].append({'role': role,
                                       'message': msg})
            self.__next_fld = next(self.__roles)

    def get_last_n(self, n) -> List[List[Dict[str, str]]]:
        return self.__history[-n:]

    def get_all_history(self) -> List[List[Dict[str, str]]]:
        return self.__history

    def get_num_msgs(self) -> int:
        return len(self.__history)

    def get_nex_role(self) -> List[str]:
        return self.__next_fld

