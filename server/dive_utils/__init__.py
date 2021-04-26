"""Utilities that are common to both the viame server and tasks package."""
import itertools
import re
from typing import Any, Dict, List, Union

from dive_utils.types import GirderModel

TRUTHY_META_VALUES = ['yes', '1', 1, 'true', 't', 'True', True]
NUMBERS_REGEX = re.compile(r'(\d+)')
NOT_NUMBERS_REGEX = re.compile(r'[^\d]+')


def asbool(value: Union[str, None, bool]) -> bool:
    """Convert freeform mongo metadata value into a boolean"""
    return str(value).lower() in TRUTHY_META_VALUES


def fromMeta(
    obj: Union[Dict[str, Any], GirderModel], key: str, default=None, required=False
) -> Any:
    """Safely get a property from girder metadata"""
    if not required:
        return obj.get("meta", {}).get(key, default)
    else:
        return obj["meta"][key]


def _maybeInt(input: str) -> Union[str, int]:
    try:
        return int(input)
    except ValueError:
        return input


def _strChunks(input: str) -> List[Union[int, str]]:
    chunks = NUMBERS_REGEX.split(input)
    return [_maybeInt(v) for v in chunks if v != '']


def strNumericCompare(input1: str, input2: str) -> float:
    """
    Convert a string to a float key for sorting
    Where its numerical components are weighted above
    its non-numerical components
    """
    if input1 == input2:
        return 0
    for a, b in itertools.zip_longest(
        _strChunks(input1), _strChunks(input2), fillvalue=None
    ):
        if a == b:
            continue
        if a is None:
            return -1
        if b is None:
            return 1
        if type(a) == int and type(b) == int:
            return a - b
        if type(a) == int:
            return -1
        if type(b) == int:
            return 1
        return 1 if a > b else -1
    return 0
