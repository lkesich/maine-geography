__docformat__ = 'google'

__all__ = [
    'has_unnamed_township'
]

from typing import List
from utils.strings import replace_all, squish, find
import re

# Regex helpers
alpha = "A-Za-z"
alnum = alpha + "0-9"
fuzzy = f"[^{alnum},]{{0,3}}"

# Township patterns
regions = ["ED","MD","ND","SD","TS","BKP","BPP","EKR","NWP","WKR","NBKP","NBPP","WBKP","WELS"]
region_pattern = f"(?:{'|'.join(regions)})"

township_standard = "T.?[\\d]{1,2}"
township_alternate = f"(?<![{alnum}])T[ABCDX](?![{alpha}])"
township_pattern = f"(?:{township_standard}|{township_alternate})"

range_pattern = f"(?:R.?[\\d]{{1,2}})"

unnamed_elements = [township_pattern, range_pattern, region_pattern]

unnamed = f"((?:{township_pattern})(?:{fuzzy}{range_pattern})?(?:{fuzzy}{region_pattern}){{0,2}})"
unnamed_re = re.compile(unnamed)


def has_unnamed_township(towns: str) -> bool:
    """
    Check if a string contains an unnamed township.

    Args:
        towns: One or more towns or townships
        
    Returns:
        True if input contains an unnamed township, else False
        
    Example:
        >>> has_unnamed_township('T5 R7')
        True
        >>> has_unnamed_township('CROSS LAKE TWP (T17 R5)')
        True
        >>> has_unnamed_township('CROSS LAKE TWP')
        False
    """
    if unnamed_re.search(towns) is None:
        return False
    else:
        return True
    
def extract_townships(towns: str) -> List[str]:
    """
    Get all unnamed townships in a string.

    Args:
        towns: One or more towns or townships
        
    Returns:
        A list of all recognized unnamed townships, unmodified
        
    Example:
        >>> extract_townships('T5 R7, T5 R8, T6 R8 TWPS (MOUNT CHASE)')
        ['T5 R7', 'T5 R8', 'T6 R8']
        >>> extract_townships('BARNARD TWP/EBEEMEE TWP (T5-R9 NWP)/T4-R9 NWP TWP')
        ['T5-R9 NWP', 'T4-R9 NWP']
    """
    return unnamed_re.findall(towns)

def extract_township(towns: str) -> str:
    """
    Get first unnamed township present in a string.

    Args:
        towns: One or more towns or townships

    Returns:
        A string with the first unnamed township found, unmodified
        
    Example:
        >>> extract_township('T5 R7, T5 R8, T6 R8 TWPS (MOUNT CHASE)')
        'T5 R7'
        >>> extract_township('BARNARD TWP/EBEEMEE TWP (T5-R9 NWP)/T4-R9 NWP TWP')
        'T5-R9 NWP'
    """
    return find(unnamed_re, towns)
    
def clean_township(town: str) -> str:
    """
    Normalize punctuation and spacing of township code and drop text that is not part of the township code.

    Args:
        township: A single town or township

    Returns:
        Normalized township string, or unmodified string if input does not contain township
        
    Example:
        >>> clean_township('T4/R3 TWP')
        'T4 R3'
        >>> clean_township('T10SD')
        'T10 SD'
        >>> clean_township('CROSS LAKE TWP (T17 R5)')
        'T17 R5'
    """
    if has_unnamed_township(town) is False:
        return town
    else:
        elements = re.findall('|'.join(unnamed_elements), town)
        leading_zero = '(?<=[^\\d])0'
        removals = f"[^{alnum}]|{leading_zero}"
        formatted_elements = [re.sub(removals, '', e) for e in elements]
        return ' '.join(formatted_elements)

def clean_townships(towns: str) -> str:
    """
    Normalize punctation and spacing of township codes in-place.

    Args:
        towns: One or more towns or townships

    Returns:
        Input string with punctuation and spacing normalized for all township codes
        
    Example:
        >>> clean_townships('ASHLAND -- T12/R13, T9/R8')
        'ASHLAND -- T12 R13, T9 R8'
        >>> clean_townships('T4/R3 TWP')
        'T4 R3 TWP'
    """
    townships = extract_townships(towns)
    cleaned = list(map(clean_township, townships))
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
    if has_unnamed_township(town) is False:
        return False
 
    removals = f'(?i)[^{alnum}]|twps?'
    alias_characters = re.sub(removals, '', unnamed_re.sub('', town))

    if len(alias_characters) > 0:
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
        >>> extract_alias('T7 R3 NBPP TWP')
        None
    """
    if has_alias(town) is False:
        return None
    else:
        alias = re.sub(f'[^ {alnum}]', '', unnamed_re.sub('', town))
        return squish(alias)

class Township:
    def __init__(self, township):
        self.is_unnamed = has_unnamed_township(township)
        self.has_alias = has_alias(township)
        self.code = clean_township(township)
        self.alias = extract_alias(township)