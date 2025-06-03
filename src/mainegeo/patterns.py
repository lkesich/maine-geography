"""Regex patterns and helpers for parsing Maine election results and place names.
"""

__docformat__ = 'google'

import re
from mainegeo.lookups import CountyData, TownshipData
from typing import List, Dict

# Lazy loading lookup tables
COUNTIES: CountyData = CountyData()
TOWNSHIPS: TownshipData = TownshipData()

# Base character sets for patterns
FUZZY = f"[^,\\w]{{0,3}}"
"""@private"""

PUNCTUATION = f'[^\\s\\w]'
"""@private"""

## Other
KNOWN_TYPOS: Dict[str, str] = {
    'MARIONTWP' : 'MARION TWP',
    'PISCATAQUS': 'PISCATAQUIS',
    'ORNVEILLE': 'ORNEVILLE',
    'EDUMUNDS': 'EDMUNDS',
    'SILIVER RIDGE': 'SILVER RIDGE',
    'FRANKLIN/T9 T10 SD': 'FRANKLIN/T9 SD/T10 SD',
    'PLEASANT POINT VOTING DISTRICT RICT': 'PLEASANT POINT VOTING DISTRICT'
}
"""Errors and replacements for known typos in election results files.

These errors represent one-off typos rather than confusion about how the
town name should be spelled. Misspellings that are the result of confusion
and might reoccur in the future are logged as aliases in 
`mainegeo.matching.TownDatabase`.

Used in `mainegeo.elections.ResultString.normalized_string`.
"""

AMBIGUOUS_GROUP_NAMES: Dict[str, str] = {
    '^PENOBSCOT TWPS$': 'MILLINOCKET PENOBSCOT TWPS',
    '^PISCATAQUIS TWPS$': 'MILLINOCKET PISCATAQUIS TWPS',
    'PEN(?:OBSCOT)? TWP$': 'PENOBSCOT TWPS',
    'PIS(?:CATAQUIS)? TWP$': 'PISCATAQUIS TWPS',
}
"""Errors and replacements for ambiguously-named unspecified groups.

These typos follow patterns, but it simplifies unspecified group name 
detection significantly if they are corrected early in processing.

Corrections in this dictionary include:
    * SoS staff sometimes omit the registration town name for Millinocket
    groups. Groups of Penobscot or Piscataquis townships with no other
    label are safely assumed to register at Millinocket.

    * On one occasion, SoS staff did not pluralize the group name (e.g. 
    'MILLINOCKET -- PENOBSCOT TWP'). The intent in this case is clear.
    
Used in `mainegeo.elections.ResultString.normalized_string`."""


## Townships
# Constants
REGIONS: List[str] = ["ED","MD","ND","SD","TS","BKP","BPP","EKR","NWP","WKR","NBKP","NBPP","WBKP","WELS"]
"""Valid region codes that can appear in township names.
    
These are two- to four-letter codes like 'WELS' (West of the
Easterly Line of the State) or 'BPP' (Bingham's Penobscot Purchase).

Township names can contain zero, one, or two regions."""

# Building blocks
REGION: str = f"(?:(?<![a-z])(?:{'|'.join(REGIONS)})(?![a-z]))"
""" Uncompiled regex building block representing a region designator."""

RANGE: str = f"(?:R.?[\\d]{{1,2}})"
""" Uncompiled regex building block representing a range designator.

Ranges are counted from the easterly line toward the west,
numbered 1-19 (e.g., R1, R19)."""

TOWNSHIP_STANDARD: str = "(?:T.?\\d{1,2})"
TOWNSHIP_ALTERNATE: str = f"(?<!\\w)T[ABCDX](?![a-z])"
TOWNSHIP: str = f"(?:{TOWNSHIP_STANDARD}|{TOWNSHIP_ALTERNATE})"
""" Uncompiled regex building block representing a township designator.

Townships are designated by:
    - Numbers 1-19 from south to north (e.g., T1, T19)
    - Occasional letter designations (TA, TB, TC, TD, TX)"""

UNNAMED: str = f"((?:{TOWNSHIP})(?:{FUZZY}{RANGE})?(?:{FUZZY}{REGION}){{0,2}})"
UNNAMED_ELEMENTS: str = f"(?:{'|'.join([TOWNSHIP, RANGE, REGION])})"

# Patterns
UNNAMED_PATTERN: re.Pattern = re.compile(UNNAMED, re.I)
"""Compiled regex matching a full unnamed township name, with tolerance for formatting variation.

Used in `mainegeo.townships.is_unnamed_township` and `mainegeo.townships.clean_codes`."""

UNNAMED_ELEMENTS_PATTERN: re.Pattern = re.compile(UNNAMED_ELEMENTS, re.I)
"""Compiled regex matching any unnamed township name element.

Used in `mainegeo.townships.clean_code`."""

LAST_REGION_PATTERN: re.Pattern = re.compile(f" {REGION}$", re.I)
"""Compiled regex matching the last region code in an unnamed township name.

Used in `mainegeo.townships.strip_region`."""

## Result parsing
# Building blocks
LEADING_ZERO: str = '(?<=[^\\d])0(?=\\d)'
NOT_REPORTING: str = f'(?!AND|&)'
PARENTHETICAL: str = f'\\({NOT_REPORTING}[^\\(]+\\)'
PRECEDES_DASH: str = f'^[^-]+--'

STANDARD_DELIMITER: str = ","
"""Preferred delimiter character; all other delimiters will be replaced by this."""

NONSTANDARD_DELIMITERS: str = ["&", "/", "(AND "]
"""Substrings that are sometimes used by the SoS to delimit reporting towns."""

MEANINGFUL_CHARACTERS: List[str] = ["(", ")", "-", "&", "/", ","]
"""Punctuation characters used by the SoS to communicate info about a reporting unit.

Examples:
    * BENEDICTA/SILVER RIDGE TWPS: forward slashes delimit towns.
    * T15 R6 TWP (EAGLE LAKE): parentheses indicate registration town
    * BLAINE -- E TWP: double hyphens indicate registration town

These characters should not be stripped until this info has been parsed out."""

# Patterns
REGISTRATION_PATTERN: re.Pattern = re.compile(f'{PARENTHETICAL}|{PRECEDES_DASH}', re.I)
"""Compiled regex matching a substring of non-reporting registration towns.

Used in `mainegeo.elections.ResultString`.
"""

CLEAN_TOWNSHIP_PATTERN: re.Pattern = re.compile(f"[^\\w]|{LEADING_ZERO}")
"""Compiled regex matching non-word characters and leading zeroes.

Used in `mainegeo.townships.clean_code`."""

NON_ALIAS_PATTERN: re.Pattern = re.compile(
    f'{UNNAMED}(?: twps?)?|{PUNCTUATION}',
    re.I
    )
"""Compiled regex matching substrings that are not an unnamed township code or punctuation.

Used in `mainegeo.townships.has_alias` and `mainegeo.townships.extract_alias`."""

DROP_CHARACTERS_PATTERN: re.Pattern = re.compile(
    f"[^\\w\\s{''.join(map(re.escape, MEANINGFUL_CHARACTERS))}]"
    )
"""Matches all characters except word characters, whitespace, and meaningful punctuation.

Meaningful punctuation characters are those used by the SoS to communicate information
about a reporting unit (e.g. forward slashes to separate reporting towns). The full list
of meanginful characters is defined in `mainegeo.patterns.MEANINGFUL_CHARACTERS`.

Used in `mainegeo.elections.ResultString._drop_non_meaningful_characters`."""

NONSTANDARD_DELIMITER_PATTERN: re.Pattern = re.compile(
    '|'.join(map(re.escape, NONSTANDARD_DELIMITERS)),
    re.I
    )
""" Compiled regex matching non-standard result string delimiters used occasionally by the SoS.

Used in `mainegeo.elections.ResultString`."""

ORPHAN_PARENTHESIS_PATTERN: re.Pattern = re.compile(
    f'^(?P<result>[^(]+)(?P<orphan_parenthesis>[)])$'
    )
"""Compiled regex matching the orphaned closing parenthesis left after delimiter normalization.

Capture groups:
    * result
    * orphan_parenthesis

Used in `mainegeo.elections.ResultString`."""

## Name standardization
# Constants
GNIS_GEOTYPES: List[str] = ["CITY", "PLANTATION", "TOWNSHIP", "TOWN"]
"""Geotypes used by the Geographic Names Information System (GNIS)."""

ABBREVIATIONS: Dict[str, str] = {
    "PLANTATION": "PLT",
    "TOWNSHIP": "TWP",
    "VOTING DISTRICT": "VOTING DIST",
    "RESERVATION": "RES"
}
"""Geotype suffixes used by the Maine SoS and their abbreviations."""

JUNIOR_SUFFIXES: List[str] = ['GORE', 'GRANT', 'ISLAND']
"""Geotypes which may precede another geotype suffix or be used alone.

For example, Moxie Gore and Moxie Gore Twp have subtly different meanings,
but refer to the same place and are often used interchangeably by the SoS."""

DIRECTIONS: List[str] = ['NORTH', 'SOUTH', 'EAST', 'WEST']
"""Direction words which may modify place names."""

CONTAINS_FALSE_SUFFIX: List[str] = ['INDIAN TOWNSHIP']
"""Canonical place names that contain a word that is normally a suffix.

For example: Indian Township is the name of a town, not a township.
These false suffixes should be treated differently than true 
suffixes during processing."""

# Factory functions
def generate_valid_punctuation(char: str, template: str) -> str:
    pattern = re.compile(f'(?P<leading>\\w+ ?){char}(?P<trailing> ?\\w+)')
    matches = map(pattern.match, TOWNSHIPS.town)
    valid_contexts = [match.expand(template) for match in matches if match]
    return '|'.join(valid_contexts)

def generate_false_suffix() -> str:
    leading = map(lambda x: re.sub(ALL_SUFFIXES, '', x), CONTAINS_FALSE_SUFFIX)
    return '|'.join(map(str.strip, leading))

# Templates
AMPERSANDS_TEMPLATE: str = '(?:(?<=\g<leading>)&(?=\g<trailing>))'
HYPHENS_TEMPLATE: str = '\g<leading>-(?=\g<trailing>)'

# Building blocks
GNIS_NAME = f"(?P<geotype>{'|'.join(GNIS_GEOTYPES)}) of (?P<town>.+)"
SUFFIX_REPLACEMENTS: Dict[str, str] = {
    f'(?i)(?<![A-Z]){full}(?=S?$)': abbr for full, abbr in ABBREVIATIONS.items()
}
ALL_SUFFIXES: str = '|'.join([*ABBREVIATIONS.keys(), *ABBREVIATIONS.values()])
PRECEDES_FALSE_SUFFIX = generate_false_suffix()
JUNIOR_SUFFIX: str = f"\\b({'|'.join(JUNIOR_SUFFIXES)})"
VALID_AMPERSANDS: str = generate_valid_punctuation('&', AMPERSANDS_TEMPLATE)
VALID_HYPHENS: str = generate_valid_punctuation('-', HYPHENS_TEMPLATE)

# Patterns
GNIS_PATTERN: re.Pattern = re.compile(GNIS_NAME, re.I)
"""Matches place names with Geographic Names Information System (GNIS) formatting.

Capture groups:
    * geotype
    * town

Used in `mainegeo.townships.normalize_suffix`."""

SUFFIX_PATTERN: re.Pattern = re.compile(
    f"(?<!{PRECEDES_FALSE_SUFFIX}) ({ALL_SUFFIXES})S?$", re.I
    )
"""Matches all valid suffixes and suffix abbreviations.

Used in `mainegeo.townships.strip_suffix`."""

VALID_AMPERSANDS_PATTERN: re.Pattern = re.compile(VALID_AMPERSANDS, re.I)
"""Matches ampersands that are part of canonical town names and should
not be interpreted as SoS result string formatting.

Used in `mainegeo.townships.strip_town` (a helper for `mainegeo.townships.clean_town`)."""

INVALID_PUNCTUATION_PATTERN: re.Pattern = re.compile(
    f"{PUNCTUATION}(?<!{VALID_HYPHENS})", re.I
    )
"""Matches all punctuation except hyphens that are part of canonical town names.

Used in `mainegeo.townships.strip_town` (a helper for `mainegeo.townships.clean_town`)."""

ENDSWITH_JUNIOR_SUFFIX_PATTERN: re.Pattern = re.compile(f".+{JUNIOR_SUFFIX}$", re.I)
"""Matches town name that ends with a junior suffix (gore, grant, island, etc).

Junior suffixes are listed in `mainegeo.patterns.JUNIOR_SUFFIXES`.

Used in `mainegeo.townships.toggle_suffix`."""

CONTAINS_JUNIOR_SUFFIX_PATTERN: re.Pattern = re.compile(f".+{JUNIOR_SUFFIX} TWP$", re.I)
"""Matches town name that contains a junior suffix (gore, grant, island, etc).

Junior suffixes are listed in `mainegeo.patterns.JUNIOR_SUFFIXES`.

Used in `mainegeo.townships.toggle_suffix`."""


## Unspecified groups
# Constants
UNSPECIFIED_FLAG: str = 'TWPS'
"""Substring that indicates an unspecified group may be present in a raw election result.

Used in multiple functions in `mainegeo.elections`. Most important use is in
`mainegeo.elections.ReportingUnit.has_unspecified_group`, which uses it in 
combination with other context clues by to detect unspecified groups."""

STANDARD_FLAG: str = 'UNSPECIFIED'
"""Substring that will be applied to unspecified groups during formatting.

Chosen to avoid overlap with words that may occur naturally in election 
result strings."""

MULTI_COUNTY_REGISTRATION_TOWNS: List[str] = ['MILLINOCKET']
"""Towns that host unspecified township groups from multiple counties.

As of 2025, the only town that is typically reported this way is Millinocket,
e.g. Millinocket Penobscot Twps and Millinocket Piscataquis Twps."""

# Building blocks
PLURAL = UNSPECIFIED_FLAG
SINGULAR = re.sub('S\\b', '', UNSPECIFIED_FLAG)
UNSPECIFIED_REGTOWN = f"(?P<regtown>{'|'.join(MULTI_COUNTY_REGISTRATION_TOWNS)})"
UNSPECIFIED_COUNTY = f"(?P<cty>{'|'.join(COUNTIES.sos_county)})"
SOS_FLAG = f"(?P<sos_flag>{UNSPECIFIED_FLAG})"

# Patterns
PLURAL_PATTERN: re.Pattern = re.compile(f'\\b{PLURAL}\\b')
SINGULAR_PATTERN: re.Pattern = re.compile(f'\\b{SINGULAR}\\b')
MULTI_COUNTY_PATTERN: re.Pattern = re.compile(
    f"(?i){UNSPECIFIED_REGTOWN} {UNSPECIFIED_COUNTY}\\w* {SOS_FLAG}", re.I
)
"""Matches raw, unformatted unspecified groups that contain a county.

Capture groups:
    * regtown
    * cty
    * sos_flag
"""

MULTI_COUNTY_FORMAT: str = r"\g<regtown> \g<sos_flag> [\g<cty>]"
"""Standardized format to apply to all multi-county unspecified groups."""

FORMATTED_GROUP_PATTERN: re.Pattern = re.compile(
    f'{STANDARD_FLAG} (?P<regtown>.+) {UNSPECIFIED_FLAG}( \\[{UNSPECIFIED_COUNTY}\\])?',
    re.I
)
"""Matches all formatted unspecified groups, including multi-county groups."""