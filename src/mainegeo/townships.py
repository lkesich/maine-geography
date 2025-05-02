"""Town and township name standardization and parsing utilities.

This module provides functions for parsing and normalizing township names
and looking up their canonical names.

All functions in this module are intended to be run on a string containing a single 
town or township, unless specifically indicated otherwise. For help parsing multi-town 
election reporting units into single town strings, see `mainegeo.elections`.
"""

__docformat__ = 'google'

__all__ = [
    # Functions
    'is_unnamed_township',
    'clean_code',
    'clean_codes',
    'has_alias',
    'extract_alias',
    'clean_township',
    'strip_suffix',
    'strip_region',
    'normalize_suffix',
    'strip_town',
    'clean_town'
]

import re
from utils.strings import replace_all, squish, match_case, normalize_whitespace
from utils.core import chain_operations
from mainegeo.patterns import (
    UNNAMED_PATTERN, 
    UNNAMED_ELEMENTS_PATTERN,
    CLEAN_TOWNSHIP_PATTERN,
    NON_ALIAS_PATTERN,
    NON_ALIAS_CHARACTERS_PATTERN,
    GNIS_PATTERN,
    ABBREVIATIONS,
    SUFFIX_REPLACEMENTS,
    SUFFIX_PATTERN,
    LAST_REGION_PATTERN,
    VALID_AMPERSANDS_PATTERN,
    INVALID_PUNCTUATION_PATTERN
)

def is_unnamed_township(town: str) -> bool:
    """
    Check if a string contains an unnamed township.

    Args:
        town: A single town or township
        
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
    return UNNAMED_PATTERN.search(town) is not None

def clean_code(town: str) -> str:
    """
    Normalize punctuation and spacing of township code and drop text that is not part of the township code.

    Args:
        town: A single town or township

    Returns:
        Normalized township string, or unmodified string if input does not contain township
        
    Example:
        >>> clean_code('T4/R3 TWP')
        'T4 R3'
        >>> clean_code('T10SD')
        'T10 SD'
        >>> clean_code('CROSS LAKE TWP (T17 R5)')
        'T17 R5'
    """
    if is_unnamed_township(town) is False:
        return town
    else:
        elements = UNNAMED_ELEMENTS_PATTERN.findall(town)
        formatted_elements = [CLEAN_TOWNSHIP_PATTERN.sub('', e) for e in elements]
        return ' '.join(formatted_elements)

def clean_codes(towns: str) -> str:
    """
    Normalize punctation and spacing of township codes in-place.

    Args:
        towns: String with one or more towns or townships

    Returns:
        Input string with punctuation and spacing normalized for all township codes
        
    Example:
        >>> clean_codes('ASHLAND -- T12/R13, T9/R8')
        'ASHLAND -- T12 R13, T9 R8'
        >>> clean_codes('T4/R3 TWP')
        'T4 R3 TWP'
        >>> clean_codes('BARNARD TWP/EBEEMEE TWP (T5-R9 NWP)/T4R9 NWP TWP')
        'BARNARD TWP/EBEEMEE TWP (T5 R9 NWP)/T4 R9 NWP TWP'
    """
    townships = UNNAMED_PATTERN.findall(towns)
    cleaned = list(map(clean_code, townships))
    return replace_all(dict(zip(townships, cleaned)), towns)

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
    else:
        return len(NON_ALIAS_CHARACTERS_PATTERN.sub('', town)) > 0

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
        >>> extract_alias('PRENTISS TWP (T7 R3 NBPP)')
        'PRENTISS TWP'
    """
    if has_alias(town) is False:
        return None
    else:
        return squish(re.sub(NON_ALIAS_PATTERN, '', town))
    
def clean_township(town: str) -> str:
    """
    Normalize punctuation and spacing of township code and alias.

    Args:
        town: A single town or township

    Returns:
        Normalized township string, or unmodified string if input does not contain township
        
    Example:
        >>> clean_township('T4/R3 TWP')
        'T4 R3'
        >>> clean_township('T10SD')
        'T10 SD'
        >>> clean_township('CROSS LAKE TWP (T17 R5)')
        'CROSS LAKE TWP T17 R5'
    """
    if is_unnamed_township(town) is False:
        return town
    else:
        alias = extract_alias(town)
        code = clean_code(town)
        return ' '.join(filter(None, [alias, code]))
    
def strip_suffix(town: str) -> str:
    return SUFFIX_PATTERN.sub('', town)

def strip_region(town: str) -> str:
    return LAST_REGION_PATTERN.sub('', town)
    
def normalize_suffix(town: str) -> str:
    """
    Normalize variations in geotype suffix abbreviation and location.

    Does not alter pluralization.
    
    Args:
        town: A single town or township

    Returns:
        Town with normalized suffix

    Example:
        >>> normalize_suffix('City of Portland')
        'Portland'
        >>> normalize_suffix('MATINICUS ISLE PLANTATION')
        'MATINICUS ISLE PLT'
    """
    gnis_format = GNIS_PATTERN.match(town.upper())
    
    if gnis_format is None:
        town_name = town
    else:
        name = gnis_format.group('town')
        suffix = ABBREVIATIONS.get(gnis_format.group('geotype'))
        town_name = ' '.join(filter(None, [name, suffix]))

    normalized = replace_all(SUFFIX_REPLACEMENTS, town_name)
    return match_case(normalized, town, preserve_mixed_case=False)
    
def strip_town(town: str) -> str:
    """
    Strip invalid punctuation and whitespace from a town name substring.

    This function performs the following operations:
        1. Strip leading and trailing whitespace and squish internal whitespace
        1. Replace '&' characters that are recognized as part of a canonical town
            name with 'and'
        2. Strip all punctuation except '-' characters that are recognized as 
            part of a canonical town name

    Args:
        town: A single town or township

    Returns:
       str: Town name with punctuation stripped

    Example:
        >>> strip_town("Loud's Island")
        'Louds Island'
        >>> strip_town('Dover-Foxcroft ')
        'Dover-Foxcroft'
        >>> strip_town('Taunton & Raynham Academy Grant')
        'Taunton and Raynham Academy Grant'
    """
    town_name = normalize_whitespace(town)
    town_name = VALID_AMPERSANDS_PATTERN.sub('and', town_name)
    town_name = INVALID_PUNCTUATION_PATTERN.sub('', town_name)
    return match_case(town_name, town, preserve_mixed_case=False)

def clean_town(town: str) -> str:
    """
    Clean and format town name. 

    Operations performed:
        1. Strip or replace punctuation
        2. Normalize whitespace
        3. Abbreviate geotype suffixes
        4. Normalize township codes

    Args:
        town: A single town or township

    Returns:
       str: Town name with punctuation stripped and formatting applied

    Example:
        >>> clean_town('City of Portland')
        'Portland'
        >>> clean_town('T8/R11 TWP')
        'T8 R11'
        >>> clean_town('CROSS LAKE TWP (T17 R5)')
        'CROSS LAKE TWP T17 R5'
        >>> clean_town('King & Bartlett Township')
        'King and Bartlett Twp'
    """
    cleaning_functions = [
        strip_town
        , normalize_suffix
        , clean_township
        , normalize_whitespace
    ]
    return chain_operations(town, cleaning_functions)