"""Functions for parsing Maine Secretary of State election reporting units.

The Maine SoS uses reporting units that provide the following challenges for parsing:
    1. Reporting units may be composed of one or several towns.
    2. Reporting units may include a non-reporting registration town.
    3. Reporting units may include an unspecified group of all townships that register at a
       particular town, or in a particular county.
    4. Delimiters, indicators of reporting vs. registration, and indicators of township aliases
       are not standard over time.

This module provides functions for parsing Maine election result strings into consistent objects, 
extracting reporting and registration towns, and standardizing the format of unspecified town groups.

Most functions in this module can be run on a delimited result string containing multiple towns,
or a list of multiple towns.
"""

__docformat__ = 'google'

__all__ = [
    'ResultString',
    'ReportingUnit'
]

import re
from dataclasses import dataclass
from functools import cached_property, cache
from typing import List, Type
from itertools import filterfalse

from utils.strings import replace_all, normalize_whitespace
from utils.core import chain_operations

from mainegeo.matching import TownDatabase
from mainegeo.entities import County
from mainegeo.townships import (
    clean_code,
    clean_codes,
    clean_town,
    is_unnamed_township,
    has_alias,
    extract_alias
)
from mainegeo.patterns import (
    KNOWN_TYPOS,
    AMBIGUOUS_GROUP_NAMES,
    DROP_CHARACTERS_PATTERN,
    STANDARD_DELIMITER,
    NONSTANDARD_DELIMITER_PATTERN,
    ORPHAN_PARENTHESIS_PATTERN,
    REGISTRATION_PATTERN,
    UNSPECIFIED_FLAG,
    STANDARD_FLAG,
    MULTI_COUNTY_PATTERN,
    MULTI_COUNTY_FORMAT,
    PLURAL,
    SINGULAR,
    PLURAL_PATTERN,
    SINGULAR_PATTERN,
    VALID_AMPERSANDS_PATTERN,
    FORMATTED_GROUP_PATTERN
)

def cached_class_attr(f):
    return classmethod(property(cache(f)))

@dataclass
class ResultString:
    raw_string: str

    @cached_property
    def normalized_string(self) -> str:
        """
        Result string with capitalization, whitespace and delimiters normalized.

        Typos found in the `mainegeo.patterns.KNOWN_TYPOS` and 
        `mainegeo.patterns.AMBIGUOUS_GROUP_NAMES` dicts are also fixed.

        Example:
            >>> result = ResultString('FORT KENT/BIG TWENTY TWP/   T15 R15 WELS')
            >>> result.normalized_string
            'FORT KENT, BIG TWENTY TWP, T15 R15 WELS'
            >>> result = ResultString('T12/R13 WELS/T9 R8 WELS')
            >>> result.normalized_string
            'T12 R13 WELS, T9 R8 WELS'
            >>> result = ResultString('T10 SD TWP (CHERRYFIELD, FRANKLIN & MILBRIDGE)')
            >>> result.normalized_string
            'T10 SD TWP (CHERRYFIELD, FRANKLIN, MILBRIDGE)'
        """
        initial_cleanup = [
            str.upper
            , self._fix_known_typos
            , self._rename_ambiguous_groups
            , self._drop_non_meaningful_chars
            , clean_codes
            , self._normalize_delimiters
            , normalize_whitespace
        ]
        return chain_operations(self.raw_string, initial_cleanup)
    
    @cached_property
    def registration_town_names(self) -> List[str]:
        """
        List of registration town names extracted from result string.

        Note:
            Splits strings by package-level STANDARD_DELIMITER.

        Example:
            >>> result = ResultString('MOUNT CHASE -- T5 R7 TWP')
            >>> result.registration_town_names
            ['MOUNT CHASE']
            >>> result = ResultString('T7 SD TWP (STEUBEN)')
            >>> result.registration_town_names
            ['STEUBEN']
            >>> result = ResultString('CROSS LAKE TWP (T17 R5)')
            >>> result.registration_town_names
            []
            >>> result = ResultString('ARGYLE TWP (ALTON, EDINBURG)')
            >>> result.registration_town_names
            ['ALTON', 'EDINBURG']
        """
        if self._registration_town_substring is None:
            return []
        else:
            reg_towns = self._registration_town_substring.split(STANDARD_DELIMITER)
            return list(map(clean_town, reg_towns))

    @cached_property
    def reporting_town_names(self) -> List[str]:
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
        if self._registration_town_substring is None:
            reporting_substr = self.normalized_string
        else:
            reporting_substr = re.sub(self._registration_town_substring, '', self.normalized_string)

        reporting = reporting_substr.split(STANDARD_DELIMITER)
        return list(map(clean_town, reporting))

    @cached_property
    def _registration_town_substring(self) -> str:
        """
        Registration town substring extracted based on SoS formatting identifiers.

        SoS formatting identifiers include parentheticals and double dashes (--).
        Parentheticals that are township aliases are ignored. 

        Note:
            Substring includes formatting indicators.

        Raises:
            ValueError: If result string contains multiple registration town substrings.

        Example:
            >>> result = ResultString('MOUNT CHASE -- T5 R7 TWP')
            >>> result._registration_town_substring
            'MOUNT CHASE --'
            >>> result = ResultString('T7 SD TWP (STEUBEN)')
            >>> result._registration_town_substring
            '(STEUBEN)'
            >>> result = ResultString('ARGYLE TWP (ALTON, EDINBURG)')
            >>> result._registration_town_substring
            '(ALTON, EDINBURG)'
        """
        flagged = REGISTRATION_PATTERN.findall(self.normalized_string)
        substrings = list(filterfalse(is_unnamed_township, flagged))
        
        if len(substrings) > 1:
            raise ValueError(f'Multiple registration town substrings found in result string: {self.normalized_string}')
        elif len(substrings) == 0:
            return None
        else:
            return substrings[0]

    @staticmethod
    def _fix_known_typos(result_str: str) -> str:
        """
        Fix known typos in-place in string.

        These typos are true misspellings, which are unique and unlikely to be repeated.
        They are stored in the KNOWN_TYPOS dict in the patterns module.

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
        processing. They are stored in the AMBIGUOUS_GROUP_NAMES dict in the patterns module.

        Args:
            result_str: Delimited result string with one or more towns or townships

        Example:
            >>> ResultString._rename_ambiguous_groups('MILLINOCKET -- PISCATAQUIS TWP')
            'MILLINOCKET -- PISCATAQUIS TWPS'
            >>> ResultString._rename_ambiguous_groups('PENOBSCOT TWPS')
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
    def _normalize_delimiters(result_str: str) -> str:
        """
        Replace all delimiters in result string with standard delimiter.

        Args:
            result_str: Delimited result string with one or more towns or townships
        """
        delimit = NONSTANDARD_DELIMITER_PATTERN.sub(STANDARD_DELIMITER, result_str)
        cleanup = ORPHAN_PARENTHESIS_PATTERN.sub('\g<result>', delimit)
        return cleanup

@dataclass
class ResultGeo:
    name: str
    county: County

@dataclass
class Municipality(ResultGeo):
    @cached_class_attr
    def towndb(cls):
        towndb = TownDatabase.build()
        return towndb

@dataclass
class NamedTownship(Municipality):
    @cached_property
    def matched_town(self):
        return self.towndb.match(self.name, self.county.fips)
    
    @property
    def canonical_name(self):
        if self.matched_town:
            return self.matched_town.name

    @property
    def consensus_name(self):
        return self.canonical_name or self.name

@dataclass
class UnnamedTownship(Municipality):
    @property
    def has_alias(self):
        return has_alias(self.name)
    
    @property
    def alias(self):
        return extract_alias(self.name)
    
    @property
    def code(self):
        return clean_code(self.name)
    
    @cached_property
    def matched_town(self):
        for name in (self.name, self.code, self.alias):
            match = self.towndb.match(name, self.county.fips)
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
        return FORMATTED_GROUP_PATTERN.match(self.name)

    @property
    def group_county(self) -> County:
        county_code = self._format_match.group('cty') or self.county.code
        return County(code=county_code)
    
    @property
    def group_registration_town(self) -> NamedTownship:
        reg_town_name = self._format_match.group('regtown') or self.county.code
        return NamedTownship(name=reg_town_name, county=self.county)
    
    @property
    def consensus_name(self):
        return self.name

@dataclass
class ReportingUnit:
    parsed_string: ResultString
    county: County

    @classmethod
    def from_strings(cls, result_str: str, county_code: str) -> "ReportingUnit":
        """
        Factory method to create a fully processed ReportingUnit.
        """
        unit = cls(
            parsed_string=ResultString(result_str),
            county=County(code=county_code)
        )
        return unit
    
    @property
    def raw_string(self) -> str:
        """
        Return original SoS name for this reporting unit.
        """
        return self.parsed_string.raw_string

    @property
    def formatted_string(self) -> str:
        """
        Return a formatted string representation of this reporting unit.
        """
        return ', '.join(self.reporting_town_standard_names)
    
    @property
    def reporting_town_standard_names(self):
        """
        List of reporting town names. Canonical name if match was found, else raw name.
        """
        return [town.consensus_name for town in self.reporting_towns]
    
    @property
    def registration_town_standard_names(self):
        """
        List of registration town names. Canonical name if match was found, else raw name.
        """
        return [town.consensus_name for town in self.registration_towns]

    @cached_property
    def registration_towns(self) -> List[NamedTownship]:
        """
        List of registration towns as NamedTownship objects.
        """
        objects = []
        for name in self.parsed_string.registration_town_names:
            regtown_object = NamedTownship(name, self.county)
            objects.append(regtown_object)
        return objects

    @cached_property
    def reporting_towns(self) -> List[ResultGeo]:
        """
        List of registration towns as ResultGeo child objects.
        """
        formatted_reporting_names = self._format_reporting_towns(
            self.parsed_string.reporting_town_names,
            self.parsed_string.registration_town_names,
            self.has_unspecified_group
        )
        objects = []
        for name in formatted_reporting_names:
            ResultClass = self._classify_fragment(name)
            reporting_object = ResultClass(name, self.county)
            objects.append(reporting_object)
        return objects
    
    @cached_property
    def has_unspecified_group(self) -> bool:
        """
        Return True if the result object includes an unspecified group, else False.

        Examples:
            >>> unit = ReportingUnit.from_strings('MEDWAY/TOWNSHIPS', 'PEN')
            >>> unit.has_unspecified_group
            True
            >>> unit = ReportingUnit.from_strings('ADAMSTOWN/LOWER CUPSUPTIC TWPS (RANGELEY)', 'OXF')
            >>> unit.has_unspecified_group
            False
            >>> unit = ReportingUnit.from_strings('MILLINOCKET PISCATAQUIS TWPS', 'PIS')
            >>> unit.has_unspecified_group
            True
            >>> unit = ReportingUnit.from_strings('MILLINOCKET/PEN TWPS', 'PEN')
            >>> unit.has_unspecified_group
            True
            >>> unit = ReportingUnit.from_strings('LEXINGTON & SPRING LAKE TWPS', 'SOM')
            >>> unit.has_unspecified_group
            False
        """
        reporting = self.parsed_string.reporting_town_names
        registration = self.parsed_string.registration_town_names
        group_name = ' '.join(filter(None, [*registration, *reporting]))

        if len(registration) > 1:
            return False
        elif len(reporting) in (1,2) and UNSPECIFIED_FLAG in reporting:
            return True
        elif len(reporting) == 1 and UNSPECIFIED_FLAG in reporting[0]:
            return True
        elif MULTI_COUNTY_PATTERN.match(group_name):
            return True
        else:
            return False

    @staticmethod
    def _format_reporting_towns(
            reporting_towns: List[str], 
            registration_towns: List[str], 
            has_unspecified_group: bool) -> List[str]:
        """
        Apply consistent format to towns and unspecified groups.

        Args:
            reporting_towns: List of one or more towns
            registration_towns: List of non-reporting registration towns (if any)
            has_unspecified_group: True if unit contains unspecified group, else False

        Returns:
            list: Reporting towns with standard formatting applied.

        Examples:
            >>> ReportingUnit._format_reporting_towns(['LEXINGTON', 'SPRING LAKE TWPS'], [], False)
            ['LEXINGTON', 'SPRING LAKE TWP']
            >>> ReportingUnit._format_reporting_towns(['FRANKLIN', 'TWPS'], [], True)
            ['FRANKLIN', 'UNSPECIFIED FRANKLIN TWPS']
            >>> ReportingUnit._format_reporting_towns(['PENOBSCOT TWPS'], ['MILLINOCKET'], True)
            ['UNSPECIFIED MILLINOCKET TWPS [PEN]']
        """
        reporting = [
            ReportingUnit._format_plural(town, has_unspecified_group)
            for town in reporting_towns
        ]
        
        if has_unspecified_group:
            return ReportingUnit._name_unspecified_group(reporting, registration_towns)
        else:
            return reporting

    @staticmethod    
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

    @staticmethod    
    def _format_unspecified_group(group_name: str) -> str:
        """
        Apply special format to unspecified groups that include a county.
        """
        return MULTI_COUNTY_PATTERN.sub(MULTI_COUNTY_FORMAT, group_name)
    
    @staticmethod
    def _name_unspecified_group(
            reporting_towns: List[str], 
            registration_towns: List[str]) -> List[str]:
        """
        Label unspecified groups with their reporting town and a standard 'unspecified' flag.
        """
        name_elements = [STANDARD_FLAG, *registration_towns, *reporting_towns]
        unformatted_group_name = ' '.join(filter(None, name_elements))
        group_name = ReportingUnit._format_unspecified_group(unformatted_group_name)
        return [group_name if UNSPECIFIED_FLAG in town else town for town in reporting_towns]
    
    @staticmethod
    def _classify_fragment(fragment_name: str) -> Type[ResultGeo]:
        """
        Return correct ResultGeo child class for a reporting towns string fragment.
        """
        if is_unnamed_township(fragment_name):
            return UnnamedTownship
        
        if UNSPECIFIED_FLAG in fragment_name:
            return UnspecifiedGroup
        
        if fragment_name:
            return NamedTownship