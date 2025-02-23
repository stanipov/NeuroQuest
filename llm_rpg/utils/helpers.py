from typing import Dict, List, Set, Union, Any
import logging
from sys import stdout

def dict_2_str(d: Dict[str, str]) -> str:
    """
    Prints a simple dict to a string
    """
    s = []
    for key in d:
        s.append(f"{key}: {d[key]}")
    return '\n'.join(s)


def parse_world_desc(world_output: str) -> Dict[str, str]:
    """
    Parses world description
    """
    return {
        "name": world_output.split('\n')[0].strip()
        .replace('World Name: ', ''),
        "description": '\n'.join(world_output.split('\n')[1:])
        .replace('World Description:', '').strip()
    }


def parse_kingdoms_response(kingdoms_output: str, expected_fields: Set[str]) -> Dict[str, str]:
    kingdoms = {}

    for kg in kingdoms_output.split('\n\n'):
        if len(kg) > 1:
            items = kg.split('\n')
            _name = items[0].split(':')[-1].strip()

            if _name != '':
                kingdoms[_name] = {
                    'name': _name,
                }

                for x in items[1:]:
                    try:
                        fld, s = x.split(':')
                        fld = fld.replace('\'', '')
                        if fld in expected_fields:
                            kingdoms[_name][fld] = s.strip()
                    except Exception as e:
                        pass

    return kingdoms


def parse_towns(loc_response: str, expected_fields: Union[List[str], Set[str]]) -> Dict[str, Any]:
    """
    Parses the town locations for a kingdom
    """
    locations = {}
    for item in loc_response.split('\n\n'):
        if len(item) > 1:
            loc_items = item.split('\n')
            _name = loc_items[0].split(':')[-1].strip()

            if _name != '':
                locations[_name] = {
                    'name': _name
                }

                for x in loc_items[1:]:
                    try:
                        fld, s = x.split(':')
                        fld = fld.replace('\'', '')
                        if fld in expected_fields:
                            locations[_name][fld] = s.strip()
                    except Exception as e:
                        pass

    return locations


def set_logger(level=logging.INFO,
               fmt:str="[%(asctime)s] [%(name)8s] [%(levelname)-8s] %(message)s"):
    """ Sets up a stdout logger """

    logFormatter = logging.Formatter(
        fmt=fmt
    )

    logger = logging.getLogger()
    logger.setLevel(level)

    # Remove any existing handlers to prevent duplicates in Jupyter
    if logger.hasHandlers():
        logger.handlers.clear()

    # Create a StreamHandler that prints to sys.stdout (needed for Jupyter)
    handler = logging.StreamHandler(stdout)
    handler.setLevel(level)
    handler.setFormatter(logFormatter)

    # Add the handler to the logger
    logger.addHandler(handler)

    return logger