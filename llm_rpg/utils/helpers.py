from typing import Dict, List, Set, Union, Any

def input_not_ok(x, dtype, def_val) -> bool:
    """
    Checks if input is not OK
    :param x: variable to check
    :param dtype: type of the variable
    :param def_val: default value (e.g. [], {})
    :return: bool
    """
    return not x or (x != def_val and type(x) != dtype)

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


def parse2structure(raw_response:str, expected_fields: Set[str]) ->Dict[str,str]:
    """
    A generic function to parse a string designed to be structured, eg:
        name: entity name --> this is mandatory field! can be used as an ID or so
        gender: character's gender, male\female\
        occupation: pick one or two from warrior, researcher, magician, crook, theft, outcast
        biography: a brief biography, 1-2 sentences
        deeper_pains: describe deeper pains, 1 sentence up to 10 words
        deeper_desires: describe deeper desires, 1 sentence up to 10 words
    Note, the string expects to have a "name"
    :param raw_response:
    :param expected_fields:
    :return:
    """
    struct_ans = {}
    chars = "*#/"
    str_trans_map = str.maketrans('', '', chars)
    for kg in raw_response.split('\n\n'):

        if len(kg) > 1:
            items = kg.split('\n')
            _name = items[0].split(':')[-1].strip()

            if _name != '':
                # strip from leftovers of markdowns or wierd chars
                _name = _name.translate(str_trans_map).strip()
                struct_ans[_name] = {'name': _name}

                for x in items[1:]:
                    try:
                        fld, s = x.split(':')
                        fld = fld.replace('\'', '').lower().translate(str_trans_map)
                        if fld in expected_fields:
                            struct_ans[_name][fld] = s.strip()
                    except Exception as e:
                        pass

    return struct_ans


def parse_kingdoms_response(kingdoms_output: str, expected_fields: Set[str]) -> Dict[str, str]:
    return parse2structure(kingdoms_output, expected_fields)


def parse_towns(loc_response: str, expected_fields: Union[List[str], Set[str]]) -> Dict[str, Any]:
    return parse2structure(loc_response, expected_fields)


def parse_character(loc_response: str, expected_fields: Union[List[str], Set[str]]) -> Dict[str, Any]:
    return parse2structure(loc_response, expected_fields)

def parse_antagonist(loc_response: str, expected_fields: Union[List[str], Set[str]]) -> Dict[str, Any]:
    return parse2structure(loc_response, expected_fields)
