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
from dataclasses import dataclass, asdict
from functools import cached_property
from typing import List, Type
from itertools import filterfalse

from utils.strings import replace_all, normalize_whitespace
from utils.core import chain_operations

from mainegeo.matching import get_town_database
from mainegeo.entities import County, Cousub
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
    AMBIGUOUS_GROUPS,
    DROP_CHARACTERS_PATTERN,
    STANDARD_DELIMITER,
    NONSTANDARD_DELIMITER_PATTERN,
    ORPHAN_PARENTHESIS_PATTERN,
    REGISTRATION_PATTERN,
    UNSPECIFIED_FLAG,
    STANDARD_FLAG,
    MULTI_COUNTY_PATTERN,
    MULTI_COUNTY_FORMAT,
    MULTI_COUNTY_REGISTRATION_TOWNS,
    PLURAL,
    SINGULAR,
    PLURAL_PATTERN,
    SINGULAR_PATTERN,
    VALID_AMPERSANDS_PATTERN,
    FORMATTED_GROUP_PATTERN
)

@dataclass
class ResultString:
    """
    A string containing one or more geographies from raw election results.
    
    This dataclass performs initial normalization and parsing operations on a raw 
    election result string. It owns operations that are fully agnostic to what
    the underlying geographies in the string represent.
    
    Args:
        raw_string: The raw string representation of the reporting unit
    
    `ResultString` operations normalize variations in meaningful formatting (including 
    whitespace, delimiters, and other punctuation) so that two types of parsing can occur:
    
        1. The splitting of result strings into a list of tokens, each
            one representing a single geography.
        2. The separation of tokens representing reporting geographies from tokens 
            representing non-reporting registration towns.
            
    Consider the following raw election result strings:
        * 'T12/R13 & T9/R8 WELS (ASHLAND)'
        * 'SHERMAN (AND BENEDICTA & SILVER RIDGE TWP) '
        * 'BERRY/CATHANCE/MARION TWPS (EAST MACHIAS)'
        * 'BARNARD TWP, EBEEMEE TWP (T5 R9 NWP), T4 R9 NWP TWP'
        * 'MOUNT CHASE -- T5 R7 TWP'
        * 'ISLAND FALLS -- T4-R3 TWP'
        * 'DOVER-FOXCROFT'

    These examples display huge variation in how formatting is used to convey information.
    
    **Parentheses** are used in three different ways in these examples:
        * In `T12/R13 & T9/R8 WELS (ASHLAND)`, parentheses convey that Ashland
            is a non-reporting registration town.
        * In `EBEEMEE TWP (T5 R9 NWP)`, parentheses convey that T5 R9 NWP is 
            an alias of EBEEMEE TWP.
        * In `SHERMAN (AND BENEDICTA & SILVER RIDGE TWP)`, parentheses convey that
            this reporting unit includes all of SHERMAN, BENEDICTA, and SILVER RIDGE,
            and that all three voted in SHERMAN.
    
    **Ampersands, commas, and forward slashes** are all used interchangeably to delimit 
    geographies within a string:
        * `BARNARD TWP, EBEEMEE TWP (T5 R9 NWP), T4 R9 NWP TWP` is delimited with commas (`,`).
        * `BERRY/CATHANCE/MARION TWPS (EAST MACHIAS)` is delimited with forward slashes (`/`).
        * `SHERMAN (AND BENEDICTA & SILVER RIDGE TWP) ` contains two different 
            delimiters: the substring `AND` and the ampersand character (`&`).
        
    **Forward slashes** are sometimes used as delimiters, but in `T12/R13` and
    `T9/R8 WELS` they are used to separate township and range designators. Each of 
    `T12/R13` and `T9/R8 WELS` is a single township, correctly written as `T12 R13` 
    and `T9 R8 WELS`.
    
    **Hyphens and parentheses** are used interchangeably to indicate 
    a non-reporting registration town:
        * In `MOUNT CHASE -- T5 R7 TWP`, MOUNT CHASE is the registration town and 
            T5 R7 TWP is the reporting town. MOUNT CHASE is not included in the vote totals 
            for this reporting unit. 
        * In `BERRY/CATHANCE/MARION TWPS (EAST MACHIAS)`, EAST MACHIAS is the registration
            town and BERRY TWP, CATHANCE TWP, and MARION TWP are all reporting towns.
            EAST MACHIAS is not included in the vote totals for this reporting unit.
            
    However, both characters are also used in other ways (see above).
        
    **Single hyphens** occur in the canonical names of towns, such as 
    DOVER-FOXCROFT, and are sometimes used non-canonically to separate township
    and range designators, as in the case of `T4-R3 TWP` (correctly written as T4 R3).
    
    **Ampersands** also occur in the canonical names of some townships,
    e.g. King & Bartlett Twp.
    
    Examples:
        **Example 1**
            >>> raw_string = 'T12/R13 & T9/R8 WELS (ASHLAND)'
            
            Variations present:
                * Ampersand (`&`) is used as a token boundary
                * parentheses (`()`) indicate a non-reporting registration town
                * Forward slash (`/`), a character that sometimes serves as a token boundary,
                is used non-canonically to separate the township and range designators in a 
                township name
            
            >>> result = ResultString(raw_string)
            >>> result.normalized_string
            'T12 R13, T9 R8 WELS (ASHLAND)'
            >>> result.reporting_town_names
            ['T12 R13', 'T9 R8 WELS']
            >>> result.registration_town_names
            ['ASHLAND']
 
        **Example 2**
            >>> raw_string = 'SHERMAN (AND BENEDICTA & SILVER RIDGE TWP) '
            
            Variations present:
                * Ampersand (`&`) and the substring `AND` are both used as token boundaries
                * Parentheses (`()`) used to group part of the reporting unit
                * Trailing whitespace
                
            >>> result = ResultString(raw_string)
            >>> result.normalized_string
            'SHERMAN, BENEDICTA, SILVER RIDGE TWP'
            >>> result.reporting_town_names
            ['SHERMAN', 'BENEDICTA', 'SILVER RIDGE TWP']
            >>> result.registration_town_names
            []
            
        Example 3:
            >>> raw_string = 'BERRY/CATHANCE/MARION TWPS (EAST MACHIAS)'
            
            Variations present:
                * Forward slash (`/`) used as token boundary
                * Parentheses (`()`) used to indicate non-reporting registration town
                
            >>> result = ResultString(raw_string)
            >>> result.normalized_string
            'BERRY, CATHANCE, MARION TWPS (EAST MACHIAS)'
            >>> result.reporting_town_names
            ['BERRY', 'CATHANCE', 'MARION TWPS']
            >>> result.registration_town_names
            ['EAST MACHIAS']
            
            Note that the plural 'TWPS' is left unaltered. ResultString operations are 
            not concerned with what real-world geography or geographies a token represents 
            (e.g. whether MARION TWPS is a variation of MARION TWP or group of townships 
            that vote at MARION).
        
        Example 4:
            >>> raw_string = 'BARNARD TWP, EBEEMEE TWP (T5 R9 NWP), T4 R9 NWP TWP'
            
            Variations present:
                * Parentheses (`()`) used to indicate township alias, not registration
                town

            >>> result = ResultString(raw_string)
            >>> result.normalized_string
            'BARNARD TWP, EBEEMEE TWP (T5 R9 NWP), T4 R9 NWP TWP'
            >>> result.reporting_town_names
            ['BARNARD TWP', 'EBEEMEE TWP (T5 R9 NWP)', 'T4 R9 NWP TWP']
            >>> result.registration_town_names
            []
            
        Example 5:
            >>> raw_string = 'MOUNT CHASE -- T5 R7 TWP'
            
            Variations present:
                * Double hyphen (`--`) used to indicate non-reporting registration
                town
        
            >>> result = ResultString(raw_string)
            >>> result.normalized_string
            'MOUNT CHASE--T5 R7 TWP'
            >>> result.reporting_town_names
            ['T5 R7']
            >>> result.registration_town_names
            ['MOUNT CHASE']
        
        Example 6:
            >>> raw_string = 'ISLAND FALLS -- T4-R3 TWP'
            
            Variations present:
                * Double hyphen (`--`) used to indicate non-reporting registration
                town
                * Hyphen, (`-`), a character that sometimes serves as a token boundary,
                is used non-canonically to separate the township and range designators 
                in a township name

            >>> result = ResultString(raw_string)
            >>> result.normalized_string
            'ISLAND FALLS--T4 R3 TWP'
            >>> result.reporting_town_names
            ['T4 R3']
            >>> result.registration_town_names
            ['ISLAND FALLS']
            
        Example 7:
            >>> raw_string = 'DOVER-FOXCROFT'
            
            Variations present:
                * Hyphen, (`-`), a character that sometimes indicates a registration town,
                is used in the canonical name for a town
        
            >>> result = ResultString('DOVER-FOXCROFT')
            >>> result.normalized_string
            'DOVER-FOXCROFT'
            >>> result.reporting_town_names
            ['DOVER-FOXCROFT']
            >>> result.registration_town_names
            []
    """
    raw_string: str
    
    @cached_property
    def exists(self) -> bool:
        if self.raw_string is None:
            return False
        elif len(self.raw_string) > 5:
            return True
        elif re.search(r'\w', self.raw_string):
            return True
        else:
            return False
        
    @cached_property
    def normalized_string(self) -> str:
        """
        Result string with capitalization, whitespace and delimiters normalized.

        Errors entered in `mainegeo.lookups.Overrides.known_typos` and 
        `mainegeo.lookups.Overrides.ambiguous_groups` are also repaired.

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
            , ResultString._fix_known_typos
            , ResultString._rename_ambiguous_groups
            , ResultString._drop_non_meaningful_chars
            , clean_codes
            , ResultString._normalize_delimiters
            , normalize_whitespace
        ]
        if self.exists:
            return chain_operations(self.raw_string, initial_cleanup)
    
    @cached_property
    def registration_town_names(self) -> List[str]:
        """
        List of registration town names extracted from result string.

        Note:
            Splits strings by package-level `STANDARD_DELIMITER`.

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
            >>> ResultString('MOUNT CHASE--T5 R7 TWP').reporting_town_names
            ['T5 R7']
            
            >>> ResultString('HERSEYTOWN, SOLDIERTOWN TWPS (MEDWAY)').reporting_town_names
            ['HERSEYTOWN', 'SOLDIERTOWN TWPS']
            
            >>> ResultString('ARGYLE TWP (ALTON, EDINBURG)').reporting_town_names
            ['ARGYLE TWP']
            
            >>> ResultString('BARNARD TWP, EBEEMEE TWP (T5 R9 NWP), T4 R9 NWP TWP').reporting_town_names
            ['BARNARD TWP', 'EBEEMEE TWP T5 R9 NWP', 'T4 R9 NWP']
            
            >>> ResultString('BERRY/CATHANCE/MARIONTWPS (EAST MACHIAS)').reporting_town_names
            ['BERRY', 'CATHANCE', 'MARION TWPS']
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

        Examples:
            >>> result = ResultString('MOUNT CHASE -- T5 R7 TWP')
            >>> result._registration_town_substring
            'MOUNT CHASE--'
            
            >>> result = ResultString('T7 SD TWP (STEUBEN)')
            >>> result._registration_town_substring
            '(STEUBEN)'
            
            >>> result = ResultString('ARGYLE TWP (ALTON, EDINBURG)')
            >>> result._registration_town_substring
            '(ALTON, EDINBURG)'
        """
        if self.exists:
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
        processing. They are stored in `lookups.Overrides.ambiguous_groups`.

        Args:
            result_str: Delimited result string with one or more towns or townships

        Example:
            >>> ResultString._rename_ambiguous_groups('MILLINOCKET -- PISCATAQUIS TWP')
            'MILLINOCKET -- PISCATAQUIS TWPS'
            
            >>> ResultString._rename_ambiguous_groups('PENOBSCOT TWPS')
            'MILLINOCKET PENOBSCOT TWPS'
        """
        return replace_all(AMBIGUOUS_GROUPS, result_str)

    @staticmethod
    def _drop_non_meaningful_chars(result_str: str) -> str:
        """
        Drop or replace special characters that don't communicate meaningful info.

        Non-meaningful characters include all punctuation characters not found in
        `mainegeo.patterns.MEANINGFUL_CHARACTERS`.

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
        cleanup = ORPHAN_PARENTHESIS_PATTERN.sub(r'\g<result>', delimit)
        return cleanup

@dataclass
class ResultGeo:
    name: str
    county: County
    strict: bool = False
    
    @classmethod
    def from_strings(cls, name: str, county_code: str, strict: bool = False) -> "ResultGeo":
        return cls(
            name = name,
            county = County(code=county_code),
            strict = strict
        )

@dataclass
class Municipality(ResultGeo):
    @cached_property
    def matched_town(self):
        return get_town_database().match(
            self.name,
            self.county.fips,
            cleaned = True,
            strict = self.strict
        )
    
    @property
    def is_matched(self):
        return self.matched_town is not None
    
    @property
    def canonical_name(self):
        if self.matched_town:
            return self.matched_town.name

    @property
    def consensus_name(self):
        return self.canonical_name or self.name
    
    @cached_property
    def matched_geocode(self) -> str:
        if self.matched_town:
            return self.matched_town.geocode
        
    @cached_property
    def matched_cousub(self) -> Cousub:
        return self.matched_town.cousub if self.matched_town else Cousub()
        
    @cached_property
    def matched_county(self) -> County:
        return self.matched_town.county if self.matched_town else County()
    
    def to_dict(self) -> dict[str]:
        return {
            'name': self.consensus_name,
            'canonical_name': self.canonical_name,
            'raw_name': self.name,
            'county': asdict(self.matched_county),
            'cousub': asdict(self.matched_cousub),
            'geocode': self.matched_geocode,
            'is_matched': self.is_matched
        }

@dataclass
class NamedTownship(Municipality):
    pass
    
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

@dataclass
class UnspecifiedGroup(ResultGeo):
    @cached_property
    def _format_match(self) -> re.Match:
        return FORMATTED_GROUP_PATTERN.match(self.name)
    
    @property
    def is_matched(self):
        return self._format_match and self.group_registration_town.is_matched

    @property
    def group_county(self) -> County:
        county_code = self._format_match.group('cty') or self.county.code
        return County(code = county_code)
    
    @property
    def group_registration_town(self) -> NamedTownship:
        reg_town_name = self._format_match.group('regtown')
        return NamedTownship(
            name = reg_town_name,
            county = self.county,
            strict = self.strict
        )
    
    @property
    def canonical_name(self):
        regtown = self.group_registration_town.consensus_name
        
        if regtown.upper() in MULTI_COUNTY_REGISTRATION_TOWNS:
            county = f' {self.group_county.name} County '
        else:
            county = ' '
            
        formatted = f'{STANDARD_FLAG}{county}{UNSPECIFIED_FLAG}'
        return formatted.title()
    
    @property
    def consensus_name(self):
        return self.canonical_name or self.name
    
    def to_dict(self):
        return {
            'name': self.consensus_name,
            'canonical_name': self.canonical_name,
            'raw_name': self.name,
            'county': asdict(self.group_county),
            'group_registration_town': self.group_registration_town.to_dict(),
            'is_matched': self.is_matched
        }

@dataclass
class ReportingUnit:
    """ A collection of towns and unspecified groups parsed from a `ResultString`.
        
    This class performs normalization operations on individual fragments of a 
    delimited string, coerces them into objects representing different geography
    types, and attempts to match them to known Maine geographies. It provides several
    options for representing the fully parsed unit as a string or dictionary.

    Args:
        result_string: A `ResultString` object
        county: A `County` object
        strict: True if exception should be raised when a match fails
    """
    result_string: ResultString
    county: County
    strict: bool = False

    @classmethod
    def from_strings(
        cls,
        result_str: str,
        county_code: str,
        strict: bool = False
    ) -> "ReportingUnit":
        """ Factory method to create a fully processed ReportingUnit.
        
        Examples:
            >>> result = ReportingUnit.from_strings('PRENTISS TWP (WEBSTER PLT)', 'PEN')
            >>> result.formatted_string
            'Prentiss Twp T7 R3 NBPP [Webster Plt]'
            >>> result.reporting_town_names
            ['Prentiss Twp T7 R3 NBPP']
            >>> result.registration_town_names
            ['Webster Plt']
            >>> result.unspecified_groups
            []
            
            >>> result = ReportingUnit.from_strings('MEDWAY -- GRINDSTONE/SOLDIERTOWN TWPS', 'PEN')
            >>> result.formatted_string
            'Grindstone Twp [Medway], Soldiertown Twp T2 R7 WELS [Medway]'
            >>> result.reporting_town_names
            ['Grindstone Twp', 'Soldiertown Twp T2 R7 WELS']
            >>> result.registration_town_names
            ['Medway']
            
            >>> result = ReportingUnit.from_strings('FRANKLIN/T9 T10 SD TWPS', 'HAN')
            >>> result.formatted_string
            'Franklin, T9 SD BPP, T10 SD BPP'
            >>> result.reporting_town_names
            ['Franklin', 'T9 SD BPP', 'T10 SD BPP']
            >>> result.registration_town_names
            []
            
            >>> result = ReportingUnit.from_strings('MILLINOCKET/PISCATAQUIS TWPS', 'PEN')
            >>> result.formatted_string
            'Millinocket, Unspecified Piscataquis County Twps [Millinocket]'
            >>> result.reporting_town_names
            ['Millinocket', 'Unspecified Piscataquis County Twps']
            >>> result.registration_town_names
            ['Millinocket']
            >>> len(result.unspecified_groups)
            1
            
            >>> result = ReportingUnit.from_strings('MEDWAY TOWNSHIPS', 'PEN')
            >>> result.formatted_string
            'Unspecified Twps [Medway]'
            >>> result.reporting_town_names
            ['Unspecified Twps']
            >>> result.registration_town_names
            ['Medway']
            >>> len(result.unspecified_groups)
            1
            """
        unit = cls(
            result_string = ResultString(result_str),
            county = County(code = county_code),
            strict = strict
        )
        return unit
    
    @property
    def raw_string(self) -> str:
        """
        Original SoS name for this reporting unit.
        
        Examples:
            >>> unit = ReportingUnit.from_strings('WEBSTER PLT -- PRENTISS TWP', 'PEN')
            >>> unit.raw_string
            'WEBSTER PLT -- PRENTISS TWP'
        """
        return self.result_string.raw_string

    @cached_property
    def formatted_string(self) -> str:
        """
        A formatted string representation of this reporting unit.
        
        Examples:
            >>> args = ('T12/R13 & T9/R8 WELS (ASHLAND)', 'ARO')
            >>> ReportingUnit.from_strings(*args).formatted_string
            'T12 R13 WELS [Ashland], T9 R8 WELS [Ashland]'
            
            >>> args = ('GRINDSTONE/HERSEYTOWN/SOLDIERTOWN TWP', 'PEN')
            >>> ReportingUnit.from_strings(*args).formatted_string
            'Grindstone Twp, Herseytown Twp, Soldiertown Twp T2 R7 WELS'
            
            >>> args = ('SHERMAN (AND BENEDICTA & SILVER RIDGE TWPS) ', 'ARO')
            >>> ReportingUnit.from_strings(*args).formatted_string
            'Sherman, Benedicta Twp, Silver Ridge Twp'
            
            >>> args = ('JACKMAN TWPS', 'SOM')
            >>> ReportingUnit.from_strings(*args).formatted_string
            'Unspecified Twps [Jackman]'
            
            >>> args = ('MILLINOCKET/PISCATAQUIS TWPS', 'PEN')
            >>> ReportingUnit.from_strings(*args).formatted_string
            'Millinocket, Unspecified Piscataquis County Twps [Millinocket]'
        """
        reporting = [
            town + f' [{self.registration_string}]'
            if
                len(self.registration_town_names) > 0
                and town not in self.registration_town_names
            else town
            for town in self.reporting_town_names
        ]
        return STANDARD_DELIMITER.join(reporting)
    
    @cached_property
    def reporting_string(self) -> str:
        """
        A formatted string representation of reporting towns in this unit.

        Examples:
            >>> args = ('WEBSTER PLT -- PRENTISS TWP', 'PEN')
            >>> ReportingUnit.from_strings(*args).reporting_string
            'Prentiss Twp T7 R3 NBPP'
            
            >>> args = ('T12/R13 & T9/R8 WELS (ASHLAND)', 'ARO')
            >>> ReportingUnit.from_strings(*args).reporting_string
            'T12 R13 WELS, T9 R8 WELS'
            
            >>> args = ('JACKMAN TWPS', 'SOM')
            >>> ReportingUnit.from_strings(*args).reporting_string
            'Unspecified Twps'
            
            >>> args = ('MILLINOCKET/PISCATAQUIS TWPS', 'PEN')
            >>> ReportingUnit.from_strings(*args).reporting_string
            'Millinocket, Unspecified Piscataquis County Twps'
        """
        return STANDARD_DELIMITER.join(self.reporting_town_names)
    
    @cached_property
    def registration_string(self) -> str:
        """
        A formatted string representation of registration towns in this unit.
        
        Examples:
            >>> args = ('WEBSTER PLT -- PRENTISS TWP', 'PEN')
            >>> ReportingUnit.from_strings(*args).registration_string
            'Webster Plt'
            
            >>> args = ('WYMAN TWP (CARRABASSETT VALLEY & EUSTIS)', 'FRA')
            >>> ReportingUnit.from_strings(*args).registration_string
            'Carrabassett Valley, Eustis'
            
            >>> args = ('JACKMAN TWPS', 'SOM')
            >>> ReportingUnit.from_strings(*args).registration_string
            'Jackman'
            
            >>> args = ('MILLINOCKET/PISCATAQUIS TWPS', 'PEN')
            >>> ReportingUnit.from_strings(*args).registration_string
            'Millinocket'
        """
        return STANDARD_DELIMITER.join(self.registration_town_names)
                
    @cached_property
    def reporting_town_names(self) -> list[str]:
        """
        List of reporting town names. Canonical name if match was found, else raw name.
        """
        return [town.consensus_name for town in self.reporting_towns]
    
    @cached_property
    def registration_town_names(self) -> list[str]:
        """
        List of registration town names. Canonical name if match was found, else raw name.
        """
        return [town.consensus_name for town in self.registration_towns]

    @cached_property
    def registration_towns(self) -> List[NamedTownship]:
        """
        List of registration towns as `NamedTownship` objects.
        """
        towns = []
        for name in self.result_string.registration_town_names:
            regtown = NamedTownship(name, self.county, strict = self.strict)
            towns.append(regtown)
        
        for group in self.unspecified_groups:
            towns.append(group.group_registration_town)
        
        return towns

    @cached_property
    def reporting_towns(self) -> List[ResultGeo]:
        """
        List of reporting towns, townships and groups as `ResultGeo` child objects.
        """
        towns = []
        
        if self.result_string.exists:
            formatted_reporting_names = ReportingUnit._format_reporting_towns(
                self.result_string.reporting_town_names,
                self.result_string.registration_town_names,
                self.has_unspecified_group
            )
            for name in formatted_reporting_names:
                ResultClass = ReportingUnit._classify_fragment(name)
                reporting_town = ResultClass(name, self.county, strict = self.strict)
                towns.append(reporting_town)
        
        return towns
    
    @cached_property
    def specified_reporting_towns(self) -> List[Municipality]:
        """
        List of reporting units that are not unspecified groups.
        
        Examples:
            >>> unit = ReportingUnit.from_strings('WYMAN TWP/SPRING LAKE TWP', 'FRA')
            >>> [town.name for town in unit.specified_reporting_towns]
            ['WYMAN TWP', 'SPRING LAKE TWP']
            
            >>> unit = ReportingUnit.from_strings('WYMAN TWP (CARRABASSETT VALLEY)', 'FRA')
            >>> [town.name for town in unit.specified_reporting_towns]
            ['WYMAN TWP']

            >>> unit = ReportingUnit.from_strings('MILLINOCKET/TWPS', 'PEN')
            >>> [town.name for town in unit.specified_reporting_towns]
            ['MILLINOCKET']
            
            >>> unit = ReportingUnit.from_strings('MILLINOCKET TWPS', 'PEN')
            >>> [town.name for town in unit.specified_reporting_towns]
            []
        """
        return [t for t in self.reporting_towns if type(t) != UnspecifiedGroup]
    
    @cached_property
    def unspecified_groups(self) -> List[ResultGeo]:
        """
        List of reporting units that are unspecified groups.
        
        Examples:
            >>> unit = ReportingUnit.from_strings('MILLINOCKET/TWPS', 'PEN')
            >>> groups = unit.unspecified_groups
            >>> [group.name for group in groups]
            ['UNSPECIFIED MILLINOCKET TWPS']
            >>> [group.canonical_name for group in groups]
            ['Unspecified Penobscot County Twps']
            >>> [group.group_registration_town.canonical_name for group in groups]
            ['Millinocket']
        """
        return [t for t in self.reporting_towns if type(t) == UnspecifiedGroup]
    
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
        reporting = self.result_string.reporting_town_names
        registration = self.result_string.registration_town_names
        group_name = ' '.join(filter(None, [*registration, *reporting]))

        if len(registration) > 1:
            return False
        elif len(reporting) in (1, 2) and UNSPECIFIED_FLAG in reporting:
            return True
        elif len(reporting) == 1 and UNSPECIFIED_FLAG in reporting[0]:
            return True
        elif MULTI_COUNTY_PATTERN.match(group_name):
            return True
        else:
            return False
        
    def to_dict(self) -> dict[str]:
        return {
            'raw_str': self.raw_string,
            'formatted_str': self.formatted_string,
            'reporting_str': self.reporting_string,
            'registration_str': self.registration_string,
            'reporting': {
                'specified': [town.to_dict() for town in self.specified_reporting_towns],
                'unspecified': [group.to_dict() for group in self.unspecified_groups]
            },
            'registration': [town.to_dict() for town in self.registration_towns]
        }

    @staticmethod
    def _format_reporting_towns(
            reporting_town_names: List[str], 
            registration_town_names: List[str], 
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
            for town in reporting_town_names
        ]
        
        if has_unspecified_group:
            return ReportingUnit._name_unspecified_group(reporting, registration_town_names)
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
            reporting_town_names: List[str], 
            registration_town_names: List[str]) -> List[str]:
        """
        Label unspecified groups with their reporting town and a standard 'unspecified' flag.
        """
        name_elements = [
            STANDARD_FLAG,
            *registration_town_names,
            *reporting_town_names
        ]
        unformatted = ' '.join(filter(None, name_elements))
        group_name = ReportingUnit._format_unspecified_group(unformatted)
        return [
            group_name if UNSPECIFIED_FLAG in town else town
            for town in reporting_town_names
        ]
    
    @staticmethod
    def _classify_fragment(fragment_name: str) -> Type[ResultGeo]:
        """
        Return correct ResultGeo child class for a reporting towns string fragment.
        """
        if is_unnamed_township(fragment_name):
            return UnnamedTownship
        elif UNSPECIFIED_FLAG in fragment_name:
            return UnspecifiedGroup
        else:
            return NamedTownship