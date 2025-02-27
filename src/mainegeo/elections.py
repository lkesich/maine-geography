"""Functions for parsing Maine Secretary of State election reporting units.

The Maine SoS uses reporting units that provide the following challenges for parsing:
    1. Reporting units may be composed of one or several towns.
    2. Reporting units may include a non-reporting registration town.
    3. Reporting units may include an unspecified group of all townships that register at a
       particular town, or in a particular county.
    4. Delimiters, indicators of reporting vs. registration, and indicators of township aliases
       are not standard over time.

This module provides functions for parsing Maine election result reporting unit strings into 
reporting and registration towns, and standardizing the format of unspecified town groups.

Most functions in this module can be run on a delimited result string containing multiple towns,
or a list of multiple towns.
"""

__docformat__ = 'google'

__all__ = [
    # Functions
    'fix_known_typos',
    'drop_non_meaningful_chars',
    'drop_meaningful_chars',
    'normalize_delimiters',
    'prepare_towns',
    'extract_registration_towns',
    'extract_reporting_towns',
    'has_unspecified_group',
    'format_reporting_towns',
    
    # Classes
    'Election'
]

import re
from typing import List
from itertools import filterfalse
from utils.strings import replace_all, squish, normalize_whitespace
from utils.core import chain_operations
from mainegeo.townships import (
    clean_township_code,
    is_unnamed_township,
    format_town
)
from mainegeo.patterns import (
    KNOWN_TYPOS,
    UNNAMED_PATTERN,
    DROP_CHARACTERS_PATTERN,
    MEANINGFUL_CHARACTERS_PATTERN,
    STANDARD_DELIMITER,
    NONSTANDARD_DELIMITER_PATTERN,
    REGISTRATION_PATTERN,
    UNSPECIFIED_FLAG,
    STANDARD_FLAG,
    MULTI_COUNTY_PATTERN,
    MULTI_COUNTY_FORMAT,
    PLURAL,
    SINGULAR,
    PLURAL_PATTERN,
    SINGULAR_PATTERN,
    FORMATTED_GROUP_PATTERN
)

def fix_known_typos(result_str: str) -> str:
    """
    Fix known typos in-place in string.

    These typos are unique and unlikely to be repeated. They are stored in 
    the module-level KNOWN_TYPOS dictionary.

    Args:
        result_str: Delimited result string with one or more towns or townships
    """
    return replace_all(KNOWN_TYPOS, result_str)

def drop_non_meaningful_chars(result_str: str) -> str:
    """
    Drop special characters that don't communicate meaningful info.

    Args:
        result_str: Delimited result string with one or more towns or townships
    """
    return DROP_CHARACTERS_PATTERN.sub('', result_str)

def drop_meaningful_chars(result_str: str) -> str:
    """
    Drop characters that communicate town aliases & registration town relationships.
    
    Note:
        Use only after registration towns are identified.

    Args:
        result_str: Delimited result string with one or more towns or townships
    """
    return MEANINGFUL_CHARACTERS_PATTERN.sub('', result_str)

def normalize_delimiters(result_str: str) -> str:
    """
    Replace all delimiters in result string with standard delimiter.

    Args:
        result_str: Delimited result string with one or more towns or townships
    """
    return NONSTANDARD_DELIMITER_PATTERN.sub(STANDARD_DELIMITER, result_str)

def extract_townships(result_str: str) -> List[str]:
    """
    Get all unnamed townships in a string.

    Args:
        result_str: Delimited result string with one or more towns or townships
        
    Returns:
        A list of all recognized unnamed townships, unmodified
        
    Example:
        >>> extract_townships('T5 R7, T5 R8, T6 R8 TWPS (MOUNT CHASE)')
        ['T5 R7', 'T5 R8', 'T6 R8']
        >>> extract_townships('BARNARD TWP/EBEEMEE TWP (T5-R9 NWP)/T4-R9 NWP TWP')
        ['T5-R9 NWP', 'T4-R9 NWP']
    """
    return UNNAMED_PATTERN.findall(result_str)

def clean_township_codes(result_str: str) -> str:
    """
    Normalize punctation and spacing of township codes in-place.

    Args:
        result_str: Delimited result string with one or more towns or townships

    Returns:
        Input string with punctuation and spacing normalized for all township codes
        
    Example:
        >>> clean_township_codes('ASHLAND -- T12/R13, T9/R8')
        'ASHLAND -- T12 R13, T9 R8'
        >>> clean_township_codes('T4/R3 TWP')
        'T4 R3 TWP'
        >>> clean_township_codes('BARNARD TWP/EBEEMEE TWP (T5-R9 NWP)')
        'BARNARD TWP/EBEEMEE TWP (T5 R9 NWP)'
    """
    townships = extract_townships(result_str)
    cleaned = list(map(clean_township_code, townships))
    return replace_all(dict(zip(townships, cleaned)), result_str)

def prepare_towns(result_str: str) -> str:
    """
    Perform inital normalizations on election result string.

    Args:
        result_str: Delimited result string with one or more towns or townships

    Returns:
        str: Result string with known typos fixed and normalized capitalization, 
        whitespace, and delimiters

    Example:
        >>> prepare_towns('FORT KENT/BIG TWENTY TWP/   T15 R15 WELS')
        'FORT KENT, BIG TWENTY TWP, T15 R15 WELS'
        >>> prepare_towns('T12/R13 WELS/T9 R8 WELS')
        'T12 R13 WELS, T9 R8 WELS'
        >>> prepare_towns('T10 SD TWP (CHERRYFIELD, FRANKLIN & MILBRIDGE)')
        'T10 SD TWP (CHERRYFIELD, FRANKLIN, MILBRIDGE)'
    """
    initial_cleanup = [
        str.upper
        , fix_known_typos
        , drop_non_meaningful_chars
        , squish
        , clean_township_codes
        , normalize_delimiters
        , normalize_whitespace
    ]
    return chain_operations(result_str, initial_cleanup)

def clean_town(town: str) -> str:
    """
    Strip punctuation and unnecessary whitespace from a town name substring. 

    Args:
        town: A single town or township

    Returns:
       str: Town name with punctuation stripped
    """
    post_split_operations = [
        drop_meaningful_chars
        , squish
        , format_town
    ]
    return chain_operations(town, post_split_operations)

def _find_registration_towns(result_str: str) -> str:
    """
    Extract registration town substring based on SoS formatting identifiers.

    SoS formatting identifiers include parentheticals and double dashes (--).

    Note:
        Ignores parentheticals that are township aliases.

    Args:
        result_str: Delimited result string with one or more towns or townships

    Returns:
        str: A substring that contains the registration town(s) and formatting identifer

    Raises:
        ValueError: If result string contains multiple registration town substrings.

    Example:
        >>> _find_registration_towns('MOUNT CHASE -- T5 R7 TWP')
        'MOUNT CHASE --'
        >>> _find_registration_towns('T7 SD TWP (STEUBEN)')
        '(STEUBEN)'
        >>> _find_registration_towns('ARGYLE TWP (ALTON, EDINBURG)')
        '(ALTON, EDINBURG)'
    """
    flagged = REGISTRATION_PATTERN.findall(result_str)
    substrings = list(filterfalse(is_unnamed_township, flagged))
    
    if len(substrings) > 1:
        raise ValueError(f'Multiple registration town substrings found in result string: {result_str}')
    elif len(substrings) == 0:
        return None
    else:
        return substrings[0]

def extract_registration_towns(result_str: str) -> List[str]:
    """
    Extract list of registration town names from result string.

    Note:
        Splits by module-level standard delimiter.

    Args:
        result_str: Delimited result string with one or more towns or townships

    Returns:
        List: Registration towns with formatting identifiers stripped

    Example:
        >>> extract_registration_towns('MOUNT CHASE -- T5 R7 TWP')
        ['MOUNT CHASE']
        >>> extract_registration_towns('T7 SD TWP (STEUBEN)')
        ['STEUBEN']
        >>> extract_registration_towns('ARGYLE TWP (ALTON, EDINBURG)')
        ['ALTON', 'EDINBURG']
        >>> extract_registration_towns('CROSS LAKE TWP (T17 R5)')
        []
    """
    reg_town_substr = _find_registration_towns(result_str)
    if reg_town_substr is None:
        return []
    else:
        reg_towns = reg_town_substr.split(STANDARD_DELIMITER)
        return list(map(clean_town, reg_towns))
    
def extract_reporting_towns(result_str: str) -> List[str]:
    """
    Extract list of reporting town names from result string.

    Note:
        Drops parentheses around township alias, but does not remove alias.

    Args:
        result_str: Delimited result string with one or more towns or townships

    Returns:
        List: Reporting towns with formatting identifiers stripped

    Example:
        >>> extract_reporting_towns('MOUNT CHASE--T5 R7 TWP')
        ['T5 R7']
        >>> extract_reporting_towns('HERSEYTOWN, SOLDIERTOWN TWPS (MEDWAY)')
        ['HERSEYTOWN', 'SOLDIERTOWN TWPS']
        >>> extract_reporting_towns('ARGYLE TWP (ALTON, EDINBURG)')
        ['ARGYLE TWP']
        >>> extract_reporting_towns('BARNARD TWP, EBEEMEE TWP (T5 R9 NWP), T4 R9 NWP TWP')
        ['BARNARD TWP', 'EBEEMEE TWP T5 R9 NWP', 'T4 R9 NWP']
    """
    reg_town_substr = _find_registration_towns(result_str)
    if reg_town_substr is None:
        reporting_substr = result_str
    else:
        reporting_substr = re.sub(reg_town_substr, '', result_str)

    reporting = reporting_substr.split(STANDARD_DELIMITER)
    return list(map(clean_town, reporting))

def has_unspecified_group(reporting_towns: List[str], registration_towns: List[str]) -> bool:
    """
    Check if a result string includes an unspecified group.

    Args:
        reporting_towns: List of one or more towns
        registration_towns: List of non-reporting registration towns (if any)

    Returns:
        True if the result string includes an unspecified group, else false

    Examples:
        >>> has_unspecified_group(['TWPS'], ['BROWNVILLE'])
        True
        >>> has_unspecified_group(['JACKMAN TWPS'], [])
        True
        >>> has_unspecified_group(['MILLINOCKET PISCATAQUIS TWPS'], [])
        True
        >>> has_unspecified_group(['PENOBSCOT TWP'], ['MILLINOCKET'])
        True
        >>> has_unspecified_group(['ASHLAND','LOWER CUPSUPTIC TWPS'], ['RANGELEY'])
        False
        >>> has_unspecified_group(['LEXINGTON', 'SPRING LAKE TWPS'], [])
        False
    """
    def _result_string():
        return ' '.join(filter(None, [*registration_towns, *reporting_towns]))

    if len(registration_towns) > 1 or len(reporting_towns) > 2:
        return False
    elif len(registration_towns) > 0 and len(reporting_towns) > 1:
        return False
    elif UNSPECIFIED_FLAG in reporting_towns:
        return True
    elif MULTI_COUNTY_PATTERN.match(_result_string()) is not None:
        return True
    elif len(reporting_towns) > 1 or len(registration_towns) > 0:
        return False
    elif any(UNSPECIFIED_FLAG in town for town in reporting_towns):
        return True
    else:
        return False

def _format_plural(town: str, has_unspecified_group: bool) -> str:
    """
    Correct errors of pluralization in town or group names.

    After this function is used, the presence or absence of a plural in a town name
    reliably indicates whether it is an unspecified group.
    """  
    if has_unspecified_group:
        return SINGULAR_PATTERN.sub(PLURAL, town)
    else:
        return PLURAL_PATTERN.sub(SINGULAR, town)
    
def _format_unspecified_group(group_name: str) -> str:
    """
    Apply special format to unspecified groups that include a county.
    """  
    return MULTI_COUNTY_PATTERN.sub(MULTI_COUNTY_FORMAT, group_name)

def _name_unspecified_group(
        reporting_towns: List[str], 
        registration_towns: List[str]) -> List[str]:
    """
    Label unspecified groups with their reporting town and a standard 'unspecified' flag.
    """
    name_elements = [STANDARD_FLAG, *registration_towns, *reporting_towns]
    group_name = _format_unspecified_group(' '.join(filter(None, name_elements)))    
    return [group_name if UNSPECIFIED_FLAG in town else town for town in reporting_towns]
    
def format_reporting_towns(
        reporting_towns: List[str], 
        registration_towns: List[str], 
        has_unspecified_group:bool) -> List[str]:
    """
    Apply consistent format to towns and unspecified groups.

    Args:
        reporting_towns: List of one or more towns
        registration_towns: List of non-reporting registration towns (if any)

    Returns:
        list: Reporting towns with standard formatting applied.

    Examples:
        >>> format_reporting_towns(['LEXINGTON', 'SPRING LAKE TWPS'], [], False)
        ['LEXINGTON', 'SPRING LAKE TWP']
        >>> format_reporting_towns(['FRANKLIN', 'TWPS'], [], True)
        ['FRANKLIN', 'UNSPECIFIED FRANKLIN TWPS']
        >>> format_reporting_towns(['PENOBSCOT TWP'], ['MILLINOCKET'], True)
        ['UNSPECIFIED MILLINOCKET TWPS [PEN]']
    """
    reporting = [_format_plural(town, has_unspecified_group) for town in reporting_towns]
    
    if has_unspecified_group is False:
        return reporting
    else:
        return _name_unspecified_group(reporting, registration_towns)

class ElectionResult:
    def __init__(self, result_str):
        if not isinstance(result_str, str):
            raise TypeError("Reporting unit must be a single string (e.g. 'BERRY/CATHANCE/MARION TWPS'")
        else:
            _result = prepare_towns(result_str)
            _registration = extract_registration_towns(_result)
            _reporting = extract_reporting_towns(_result)
            _has_unspecified_group = has_unspecified_group(_reporting, _registration)
            
            self.reporting_towns = format_reporting_towns(_reporting, _registration, _has_unspecified_group)
            self.registration_towns = _registration
            self.has_unspecified_group = _has_unspecified_group

            self.unspecified_group_name = None
            self.unspecified_group_reporting_town = None
            self.unspecified_group_county = None

            if self.has_unspecified_group:
                self._assign_unspecified_group_attributes()

    def _assign_unspecified_group_attributes(self) -> str:
        _group_name = [town for town in self.reporting_towns if UNSPECIFIED_FLAG in town][0]
        match = FORMATTED_GROUP_PATTERN.match(_group_name)
        self.unspecified_group_reporting_town = match.group('regtown')
        
        if match.group('cty') is not None:
            self.unspecified_group_county = match.group('cty')

        self.unspecified_group_name = _group_name