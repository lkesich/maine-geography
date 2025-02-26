"""Township name parsing utilities.

This module provides functions for parsing and normalizing township names
and looking up their canonical names.

All functions in this module are intended to be run on a string containing a single 
town or township. For help parsing multi-town election reporting units into single 
town strings, see `mainegeo.elections`.
"""

__docformat__ = 'google'

__all__ = [
    # Functions
    'is_unnamed_township',
    'clean_township_code',
    'has_alias',
    'extract_alias',
    'format_township',
    'format_town',
    'normalize_suffix',
    
    # Classes
    'Township'
]

import re
from typing import List
from utils.strings import replace_all, squish, match_case
from utils.core import chain_operations
from mainegeo.patterns import (
    UNNAMED_PATTERN, 
    UNNAMED_ELEMENTS_PATTERN,
    CLEAN_TOWNSHIP_PATTERN,
    NON_ALIAS_PATTERN,
    NON_ALIAS_CHARACTERS_PATTERN,
    GNIS_PATTERN,
    ABBREVIATIONS,
    SUFFIX_REPLACEMENTS
)

def is_unnamed_township(towns: str) -> bool:
    """
    Check if a string contains an unnamed township.

    Args:
        towns: One or more towns or townships
        
    Returns:
        True if input contains an unnamed township, else False
        
    Example:
        >>> is_unnamed_township('T5 R7')
        True
        >>> is_unnamed_township('CROSS LAKE TWP (T17 R5)')
        True
        >>> is_unnamed_township('CROSS LAKE TWP')
        False
    """
    if UNNAMED_PATTERN.search(towns) is None:
        return False
    else:
        return True

def clean_township_code(town: str) -> str:
    """
    Normalize punctuation and spacing of township code and drop text that is not part of the township code.

    Args:
        town: A single town or township

    Returns:
        Normalized township string, or unmodified string if input does not contain township
        
    Example:
        >>> clean_township_code('T4/R3 TWP')
        'T4 R3'
        >>> clean_township_code('T10SD')
        'T10 SD'
        >>> clean_township_code('CROSS LAKE TWP (T17 R5)')
        'T17 R5'
    """
    if is_unnamed_township(town) is False:
        return town
    else:
        elements = UNNAMED_ELEMENTS_PATTERN.findall(town)
        formatted_elements = [CLEAN_TOWNSHIP_PATTERN.sub('', e) for e in elements]
        return ' '.join(formatted_elements)

def has_alias(town: str) -> str:
    """
    Check if input has both an unnamed township and a township alias.

    Args:
        town: A single town or township

    Returns:
        True if town string contains a township code and alias, else False

    Example:
        >>> has_alias('CROSS LAKE TWP (T17 R5)')
        True
        >>> has_alias('EBEEMEE TWP')
        False
        >>> has_alias('PRENTISS TWP T7 R3 NBPP')
        True
        >>> has_alias('T7 R3 NBPP TWP')
        False
    """
    if is_unnamed_township(town) is False:
        return False
    elif len(NON_ALIAS_CHARACTERS_PATTERN.sub('', town)) > 0:
        return True
    else:
        return False

def extract_alias(town: str) -> str:
    """
    Extract the township alias from a string that contains both an alias and a code.

    Args:
        town: A single town or township

    Returns:
        Input string with punctuation and spacing normalized for all township codes

    Example:
        >>> extract_alias('CROSS LAKE TWP (T17 R5)')
        'CROSS LAKE TWP'
        >>> extract_alias('T3 Indian Purchase Twp')
        'Indian Purchase Twp'
    """
    if has_alias(town) is False:
        return None
    else:
        return squish(re.sub(NON_ALIAS_PATTERN, '', town))
    
def format_township(town: str) -> str:
    """
    Normalize punctuation and spacing of township code and alias.

    Args:
        town: A single town or township

    Returns:
        Normalized township string, or unmodified string if input does not contain township
        
    Example:
        >>> format_township('T4/R3 TWP')
        'T4 R3'
        >>> format_township('T10SD')
        'T10 SD'
        >>> format_township('CROSS LAKE TWP (T17 R5)')
        'CROSS LAKE TWP T17 R5'
    """
    if is_unnamed_township(town) is False:
        return town
    else:
        alias = extract_alias(town)
        code = clean_township_code(town)
        return ' '.join(filter(None, [alias, code]))
    
def normalize_suffix(town: str) -> str:
    """
    Normalize variations in geotype suffix abbreviation and location.
    
    Args:
        town: A single town or township

    Returns:
        Town with normalized suffix

    Note:
        Does not alter pluralization.

    Example:
        >>> normalize_suffix('City of Portland')
        'Portland'
        >>> normalize_suffix('MATINICUS ISLE PLANTATION')
        'MATINICUS ISLE PLT'
        >>> normalize_suffix('T8 R11 TWP')
        'T8 R11'
        >>> normalize_suffix('Township 6 North of Weld')
        'Township 6 North of Weld'
    """
    gnis_format = GNIS_PATTERN.match(town.upper())
    
    if gnis_format is None:
        town_name = town
    else:
        name = gnis_format.group('town')
        suffix = ABBREVIATIONS.get(gnis_format.group('geotype'))
        town_name = ' '.join(filter(None, [name, suffix]))

    normalized = replace_all(SUFFIX_REPLACEMENTS, town_name)
    return match_case(normalized, town)

def format_town(town: str) -> str:
    order = [
        normalize_suffix,
        format_township,
    ]
    return chain_operations(town, order)
    
class Township:
    def __init__(self, township):
        self.is_unnamed = is_unnamed_township(township)
        self.has_alias = has_alias(township)
        self.code = clean_township_code(township)
        self.alias = extract_alias(township)
        self.fullname = ' '.join(filter(None, [self.alias, self.code]))

