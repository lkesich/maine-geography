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
    '_fix_known_typos',
    '_drop_non_meaningful_chars',
    '_drop_meaningful_chars',
    '_normalize_delimiters',
    'prepare_towns',
    'extract_registration_towns',
    'extract_reporting_towns',
    'has_unspecified_group',
    'format_reporting_towns',
    
    # Classes
    'ElectionResult'
]

import re
from dataclasses import dataclass, field
from functools import cached_property
from typing import List, Type
from itertools import filterfalse
from utils.strings import replace_all, normalize_whitespace
from utils.core import chain_operations
from mainegeo import townships
from mainegeo.patterns import (
    KNOWN_TYPOS,
    AMBIGUOUS_GROUP_NAMES,
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
    FORMATTED_GROUP_PATTERN,
    VALID_AMPERSANDS_PATTERN
)

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
    substrings = list(filterfalse(townships.is_unnamed_township, flagged))
    
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
        return list(map(townships.clean_town, reg_towns))
    
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
    return list(map(townships.clean_town, reporting))

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
        >>> has_unspecified_group(['ADAMSTOWN','LOWER CUPSUPTIC TWPS'], ['RANGELEY'])
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
    
def has_unspecified_group2(reporting_towns: List[str], registration_towns: List[str]) -> bool:
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
        >>> has_unspecified_group(['ADAMSTOWN','LOWER CUPSUPTIC TWPS'], ['RANGELEY'])
        False
        >>> has_unspecified_group(['LEXINGTON', 'SPRING LAKE TWPS'], [])
        False
    """
    if len(reporting_towns) > 2:
        return False
    elif len(registration_towns) > 1:
        return False
    elif UNSPECIFIED_FLAG in reporting_towns:
        return True
    elif len(reporting_towns) > 1:
        return False
    elif not any(UNSPECIFIED_FLAG in town for town in reporting_towns):
        return False
    else:
        return True

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
    
    if has_unspecified_group:
        return _name_unspecified_group(reporting, registration_towns)
    else:
        return reporting

@dataclass
class ResultString:
    raw: str

    @property
    def normalized(self) -> str:
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
            , self._fix_known_typos
            , self._rename_ambiguous_groups
            , self._drop_non_meaningful_chars
            , townships.clean_codes
            , self._normalize_delimiters
            , normalize_whitespace
        ]
        return chain_operations(self.raw, initial_cleanup)
    
    @staticmethod
    def _fix_known_typos(result_str: str) -> str:
        """
        Fix known typos in-place in string.

        These typos are true misspellings, which are unique and unlikely to be repeated.
        They are stored in the module-level KNOWN_TYPOS dictionary.

        Args:
            result_str: Delimited result string with one or more towns or townships
        """
        return replace_all(KNOWN_TYPOS, result_str)

    @staticmethod
    def _rename_ambiguous_groups(result_str: str) -> str:
        """
        Fix ambiguous unspecified group names in-place in string.

        These typos recur from time to time, but follow a general pattern. It simplifies
        unspecified group name detection significantly if they are corrected early in
        processing. They are stored in the module-level AMBIGUOUS_GROUP_NAMES dictionary.

        Args:
            result_str: Delimited result string with one or more towns or townships

        Example:
            >>> _rename_ambiguous_groups('MILLINOCKET -- PISCATAQUIS TWP')
            'MILLINOCKET -- PISCATAQUIS TWPS'
            >>> _rename_ambiguous_groups('PENOBSCOT TWPS')
            'MILLINOCKET PENOBSCOT TWPS'
        """
        return replace_all(AMBIGUOUS_GROUP_NAMES, result_str)

    @staticmethod
    def _drop_non_meaningful_chars(result_str: str) -> str:
        """
        Drop or replace special characters that don't communicate meaningful info.

        Args:
            result_str: Delimited result string with one or more towns or townships
        """
        result = VALID_AMPERSANDS_PATTERN.sub('AND', normalize_whitespace(result_str))
        return DROP_CHARACTERS_PATTERN.sub('', result)

    @staticmethod
    def _drop_meaningful_chars(result_str: str) -> str:
        """
        Drop characters that communicate town aliases & registration town relationships.
        
        Note:
            Use only after registration towns are identified.

        Args:
            result_str: Delimited result string with one or more towns or townships
        """
        return MEANINGFUL_CHARACTERS_PATTERN.sub('', result_str)

    @staticmethod
    def _normalize_delimiters(result_str: str) -> str:
        """
        Replace all delimiters in result string with standard delimiter.

        Args:
            result_str: Delimited result string with one or more towns or townships
        """
        return NONSTANDARD_DELIMITER_PATTERN.sub(STANDARD_DELIMITER, result_str)





from mainegeo.entities import County
from mainegeo.matching import TownDatabase
towndb = TownDatabase.build()

@dataclass
class ResultGeo:
    name: str
    county: County

@dataclass
class Town(ResultGeo):
    @cached_property
    def matched_town(self):
        return towndb.match(self.name, self.county.fips)
    
    @property
    def canonical_name(self):
        if self.matched_town:
            return self.matched_town.name

    @property
    def consensus_name(self):
        return self.canonical_name or self.name

@dataclass
class Township(ResultGeo):
    @property
    def has_alias(self):
        from mainegeo.townships import has_alias
        return has_alias(self.name)
    
    @property
    def alias(self):
        from mainegeo.townships import extract_alias
        return extract_alias(self.name)
    
    @property
    def code(self):
        from mainegeo.townships import clean_code
        return clean_code(self.name)
    
    @cached_property
    def matched_town(self):
        for name in (self.name, self.code, self.alias):
            match = towndb.match(name, self.county.fips)
            if match:
                return match
    
    @property
    def canonical_name(self):
        if self.matched_town:
            return self.matched_town.name

    @property
    def consensus_name(self):
        return self.canonical_name or self.name

@dataclass
class UnspecifiedGroup(ResultGeo):
    @cached_property
    def _format_match(self) -> re.Match:
        from mainegeo.patterns import FORMATTED_GROUP_PATTERN
        return FORMATTED_GROUP_PATTERN.match(self.name)

    @property
    def group_county(self) -> County:
        county_code = self._format_match.group('cty') or self.county.code
        return County(code=county_code)
    
    @property
    def group_registration_town(self) -> Town:
        reg_town_name = self._format_match.group('regtown') or self.county.code
        return Town(name=reg_town_name, county=self.county)
    
    @property
    def consensus_name(self):
        return self.name

@dataclass
class ReportingUnit:
    raw_string: str
    county: County
    reporting_towns: List[ResultGeo] = field(default_factory=list)
    registration_towns: List[ResultGeo] = field(default_factory=list)
    has_unspecified_group: bool = False

    @property
    def formatted_string(self) -> str:
        """
        Return a formatted string representation of this reporting unit.
        """
        parts = [obj.name for obj in self.reporting_towns]
        return ', '.join(parts)
    
    @classmethod
    def from_result_string(cls, result_string: str, county: County) -> "ReportingUnit":
        """
        Factory method to create a fully processed ReportingUnit.
        """
        from mainegeo.elections import (
            prepare_towns,
            extract_registration_towns,
            extract_reporting_towns,
            has_unspecified_group, 
            format_reporting_towns
        )
        
        prepared_result = prepare_towns(result_string)
        registration_names = extract_registration_towns(prepared_result)
        raw_reporting_names = extract_reporting_towns(prepared_result)
        has_group = has_unspecified_group(raw_reporting_names, registration_names)
        reporting_names = format_reporting_towns(
            raw_reporting_names, registration_names, has_group
        )
        
        unit = cls(
            raw_string=result_string,
            county=county,
            has_unspecified_group=has_group,
        )
        
        unit._create_objects_from_names(reporting_names, registration_names)
        #unit._standardize_names()
        
        return unit
                    
    def _create_objects_from_names(self, reporting_names: List[str], registration_names: List[str]):
        """
        Convert parsed name strings into ResultGeo objects.
        """
        for name in registration_names:
            regtown_object = Town(name, self.county)
            self.registration_towns.append(regtown_object)

        for name in reporting_names:
            ResultClass = self._classify_fragment(name)
            reporting_object = ResultClass(name, self.county)
            self.reporting_towns.append(reporting_object)

    def _classify_fragment(self, fragment_name: str) -> Type[ResultGeo]:
        """
        Return correct ResultGeo child class for a reporting towns string fragment.
        """
        from mainegeo.townships import is_unnamed_township
        if is_unnamed_township(fragment_name):
            return Township
        
        from mainegeo.patterns import UNSPECIFIED_FLAG
        if UNSPECIFIED_FLAG in fragment_name:
            return UnspecifiedGroup
        
        if fragment_name:
            return Town
