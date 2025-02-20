__docformat__ = 'google'

__all__ = [
    'geo_function_1'
]

import typing
from utils import strings

def geo_function_1(town: str) -> str:
    """Clean town name
    
    Args:
        town: town name
        
    Returns:
        Clean town
    """
    return strings.normalize_whitespace(town)