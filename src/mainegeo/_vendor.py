"""
Vendored subset of `utils.core` and `utils.strings`, copied from
https://github.com/lkesich/utilities (utils==0.0.6) so that `mainegeo`
does not depend on an unpublished package when built for distribution.

Vendored: 2026-08-03, from utils==0.0.6
"""

__docformat__ = 'google'

from typing import List, Callable, Any
from functools import reduce
from itertools import chain
from collections import defaultdict
import re

def chain_operations(arg, order_of_operations: List[Callable]):
    """Apply multiple functions to an argument in sequence.

    This function is an implementation of functools.reduce. It allows functions
    from different classes to be applied to a variable in a specified order,
    without naming the variable each time.
    
    Args:
        arg: Item to apply functions to
        order_of_operations: List of functions to apply in order
        
    Returns:
        Item with all operations applied
        
    Examples:
        >>> chain_operations(' abc ', [str.upper, str.strip])
        'ABC'
    """
    return reduce(lambda x, f: f(x), order_of_operations, arg)

def create_surrogate_key(fields: list, delimiter = '_', spare: list = []) -> str:
    """Create surrogate primary key from a list of fields.

    Args:
        fields: List of elements to include
        delimiter: String delimiter. Defaults to `_`
        spare: Any punctuation characters that should not be removed
    
    Returns:
        Surrogate primary key

    Examples:
        >>> create_surrogate_key([12, 'a.b', None, 'c d'])
        '12_ab_cd'
        >>> create_surrogate_key([12, 'a.b', None, 'c d'], '~')
        '12~ab~cd'
        >>> create_surrogate_key(['a.b', '2022-01-01'], '_', ['-'])
        'ab_2022-01-01'
    """
    spared = ''.join(map(re.escape, spare))
    clean_elements = lambda e: re.sub(f'[^a-zA-Z0-9{spared}]', '', str(e))
    elements = map(clean_elements, list(filter(None, fields)))
    id_string = f'{delimiter}'.join(list(elements))
    return id_string

def flatten_nested_list(items: List[Any|List[Any]]) -> List:
    """Flatten lists with nested elements of arbitrary depths.

    Args:
        items: List to flatten
    
    Returns:
        Flattened list

    Examples:
        >>> flatten_nested_list(['a', ['b'], 'c'])
        ['a', 'b', 'c']
        >>> flatten_nested_list([1, [2], [[3], [4]]])
        [1, 2, 3, 4]
    """
    return list(
        chain.from_iterable(
            [item] if not isinstance(item, list)
            else flatten_nested_list(item)
            for item in items
            )
        )

def invert_list_of_dicts(dictionaries: list[dict]):
    """Efficiently convert a list of dictionaries into a dictionary of lists.
    
    Args:
        dictionaries: A list of dictionaries
        
    Returns:
        A dictionary with one item for each unique key
        
    Examples:
        >>> invert_list_of_dicts([{'a': 1, 'b': 2}, {'a': 3, 'b': 4}])
        {'a': [1, 3], 'b': [2, 4]}
        >>> invert_list_of_dicts([{'a': 1, 'b': 2}, {'a': 3, 'c': 4}])
        {'a': [1, 3], 'b': [2], 'c': [4]}
    """
    result = defaultdict(list)
    for dictionary in dictionaries:
        for key, value in dictionary.items():
            result[key].append(value)
    return dict(result)


def replace_all(replacements: dict, text: str, flags = 0) -> str:
    """Perform multiple replacements in a text string.
    
    Args:
        replacements: Dictionary mapping patterns (string or regex) to replacements
        text: String to perform replacements on
        flags: re flags
        
    Returns:
        String with all replacements applied
        
    Examples:
        >>> replace_all({'a': 'd', 'b': 'e'}, 'abc')
        'dec'
        >>> replace_all({'a': 'd', 'b': 'e'}, 'ABC', re.I)
        'deC'
        >>> replace_all({r'\\d+': '#'}, 'a1')
        'a#'
    """
    if len(replacements) > 0:
        for (old_pattern, new_pattern) in replacements.items():
            text = re.sub(old_pattern, new_pattern, text, flags = flags)
    return text

def find(pattern: re.Pattern | str, text: str) -> str:
    """Get first matching substring from a string.
        
    Returns:
        First match for pattern in text

    Examples:
        >>> find(r'\\d+', 'a 1 b 2')
        '1'
        >>> find(re.compile(r'\\d+'), 'a 1 b 2')
        '1'
    """
    if not isinstance(text, str):
        raise TypeError('Input text must be a string')
    elif not isinstance(pattern, re.Pattern | str):
        raise TypeError('Pattern must be a string or re.compile object')
    else:
        match = re.search(pattern, text)
        return match.group(0) if match is not None else None

def squish(text: str) -> str:
    """Normalize whitespace in a string.
    
    Trim whitespace at the start and end of a text string; replace all internal
    whitespace with a single space.
    
    Args:
        text: String to normalize
        
    Returns:
        String with normalized whitespace
        
    Examples:
        >>> squish("  hello   world  ")
        'hello world'
    """
    return re.sub(r'\s+', ' ', text.strip())

def normalize_whitespace(text: str) -> str:
    """Normalize whitespace and punctuation spacing in text.
    
    This function performs several whitespace normalization operations:
      1. Trims whitespace from start and end of string
      2. Applies `squish` to replace all internal whitespace with a single space
      3. Removes unnecessary whitespace around punctuation using `replace_all`
      4. Adds whitespace around punctuation when necessary using `replace_all`
    
    Args:
        text: String to standardize
    
    Returns:
        String with normalized whitespace
    
    Note:
        See the function implementation for punctuation spacing rules.
    
    Examples:
        >>> normalize_whitespace(" a ,b c( 1 ) ")
        'a, b c (1)'
        >>> normalize_whitespace(" [a ],[ b] , [c] ")
        '[a], [b], [c]'
    """
    # Characters that should not have leading whitespace
    _REMOVE_LEADING_SPACE = ['.', ',', ':', ';', ')', ']', '!', '?', '/', '-']
    # Characters that should not have trailing whitespace
    _REMOVE_TRAILING_SPACE = ['(', '[', '/', '-']
    # Characters that should have leading whitespace
    _ADD_LEADING_SPACE = ['&', '(']
    # Characters that should have trailing whitespace
    _ADD_TRAILING_SPACE = ['&', ')', ',', '.', ':', ';', '!', '?']

    replacements = {
        rf"(?<=[^\s])([{''.join(map(re.escape, _ADD_LEADING_SPACE))}])": r" \g<1>"
        , rf"([{''.join(map(re.escape, _ADD_TRAILING_SPACE))}])(?=[^\s])": r"\g<1> "
        , rf"\s([{''.join(map(re.escape,_REMOVE_LEADING_SPACE))}])": r"\g<1>"
        , rf"([{''.join(map(re.escape,_REMOVE_TRAILING_SPACE))}])\s": r"\g<1>"
    }
    return replace_all(replacements, squish(text))

def check_case(text: str) -> str:
    """Check if a string is upper, lower, or mixed case.

    Args:
        text: String to check
        
    Returns:
        'upper', 'lower', or 'mixed'
        
    Raises:
        TypeError: If input is not a string

    Examples:
        >>> check_case('of Mice and Men')
        'mixed'
        >>> check_case('of mice and men')
        'lower'
    """
    if type(text) != str:
        raise TypeError('Input must be a string')
    elif text.isupper():
        return 'upper'
    elif text.islower():
        return 'lower'
    else:
        return 'mixed'

def proper_case(text: str) -> str:
    """Apply proper case to a string.

    The rules for proper case are as follows:
      1. Apply title case (all words in string capitalized)
      2. Lowercase conjunctions and other words that are commonly lowercase
      3. Capitalize the first word in the string, even if it is commonly lowercase

    Args:
        text: String to proper case
        
    Returns:
        Proper cased string
        
    Raises:
        TypeError: If input is not a string

    Examples:
        >>> proper_case('of mice and men')
        'Of Mice and Men'
    """
    _ALWAYS_LOWERCASE = ['of', 'and', 'for']
    title = text.title()
    
    for word in _ALWAYS_LOWERCASE:
        title = re.sub(rf'(?i)(?<=\s){word}\b', word, title)
    return title

def match_case(
        text: str, 
        match_reference: str, 
        preserve_mixed_case: bool=True) -> str:
    """Align the case of string with the case of comparison string.
    
    Args:
        text: String to normalize case
        match_reference: String to reference for case
        preserve_mixed_case: True if mixed case `text` with mixed case 
            `match_reference` should be returned unaltered, False if 
            `text` should be forced to proper case
        
    Returns:
        String with matched case applied
        
    Raises:
        TypeError: If input is not a string

    Examples:
        >>> match_case('AbCd', 'a')
        'abcd'
        >>> match_case('LePage', 'aB')
        'LePage'
        >>> match_case('LePage', 'aB', preserve_mixed_case=False)
        'Lepage'
    """
    if {type(text), type(match_reference)} != {str}:
        raise TypeError('Both inputs must be strings')
    elif preserve_mixed_case and check_case(text) == check_case(match_reference):
        return text
    elif match_reference.isupper():
        return text.upper()
    elif match_reference.islower():
        return text.lower()
    else:
        return proper_case(text)