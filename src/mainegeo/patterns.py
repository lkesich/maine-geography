"""Regex patterns and helpers for parsing Maine election results and place names.
"""
import re
from mainegeo.lookups import CountyLookup, TownshipLookup
from string import Template
from typing import List

# Lazy loading lookup tables
COUNTIES = CountyLookup()
TOWNSHIPS = TownshipLookup()

# Base character sets for patterns
ALPHA = "A-Za-z"
ALNUM = ALPHA + "0-9"
FUZZY = f"[^{ALNUM},]{{0,3}}"
PUNCTUATION = f'[^ {ALNUM}]'

## Townships
# Constants
REGIONS = ["ED","MD","ND","SD","TS","BKP","BPP","EKR","NWP","WKR","NBKP","NBPP","WBKP","WELS"]

# Building blocks
REGION = f"(?:{'|'.join(REGIONS)})"
RANGE = f"(?:R.?[\\d]{{1,2}})"
TOWNSHIP_STANDARD = "(?:T.?[\\d]{1,2})"
TOWNSHIP_ALTERNATE = f"(?<![{ALNUM}])T[ABCDX](?![{ALPHA}])"
TOWNSHIP = f"(?:{TOWNSHIP_STANDARD}|{TOWNSHIP_ALTERNATE})"
UNNAMED = f"((?:{TOWNSHIP})(?:{FUZZY}{RANGE})?(?:{FUZZY}{REGION}){{0,2}})"

# Patterns
UNNAMED_PATTERN = re.compile(UNNAMED)
UNNAMED_ELEMENTS = f"(?:{'|'.join([TOWNSHIP, RANGE, REGION])})"
UNNAMED_ELEMENTS_PATTERN = re.compile(UNNAMED_ELEMENTS)
LAST_REGION_PATTERN = re.compile(f" {REGION}$")

## Result parsing
# Building blocks
LEADING_ZERO = '(?<=[^\\d])0(?=\\d)'
NOT_REPORTING = f'(?!AND|&)'
PARENTHETICAL = f'\\({NOT_REPORTING}[^\\(]+\\)'
PRECEDES_DASH = f'^[^-]+--'
STANDARD_DELIMITER = ","
NONSTANDARD_DELIMITERS = ["&", "/", "(AND "]
DROP_CHARACTERS = [".", "=", "*", "'", "~"]
MEANINGFUL_CHARACTERS = ["(", ")", "--"]

# Patterns
REGISTRATION_PATTERN = re.compile(f'{PARENTHETICAL}|{PRECEDES_DASH}')
CLEAN_TOWNSHIP_PATTERN = re.compile(f"[^{ALNUM}]|{LEADING_ZERO}")
NON_ALIAS_CHARACTERS_PATTERN = re.compile(f'(?i){UNNAMED}|[^{ALNUM}]|twps?')
NON_ALIAS_PATTERN = re.compile(f'(?i){UNNAMED}(?: twp)?|{PUNCTUATION}')
DROP_CHARACTERS_PATTERN = re.compile('|'.join(map(re.escape, DROP_CHARACTERS)))
MEANINGFUL_CHARACTERS_PATTERN = re.compile('|'.join(map(re.escape, MEANINGFUL_CHARACTERS)))
NONSTANDARD_DELIMITER_PATTERN = re.compile('|'.join(map(re.escape, NONSTANDARD_DELIMITERS)), re.IGNORECASE)

## Name standardization
# Constants
GNIS_GEOTYPES = ["CITY", "PLANTATION", "TOWNSHIP", "TOWN"]
ABBREVIATIONS = {
    "PLANTATION": "PLT",
    "TOWNSHIP": "TWP",
    "VOTING DISTRICT": "VOTING DIST"
}
CONTAINS_FALSE_SUFFIX = ['INDIAN TOWNSHIP']

# Factory functions
def _generate_valid_punctuation_regex(char:str, template:Template) -> List[str]:
    pattern = re.compile(f'(?P<leading>\\w+ ?)(?P<char>{char})(?P<trailing> ?\\w+)')
    valid_contexts = [pattern.match(town) for town in TOWNSHIPS.town]
    return [
        template.substitute(
            leading=m.group('leading'), char=m.group('char'), trailing=m.group('trailing')
        ) for m in valid_contexts
        if m is not None
    ]

def _generate_false_suffix_regex() -> str:
    leading = map(lambda x: re.sub(ALL_SUFFIXES, '', x), CONTAINS_FALSE_SUFFIX)
    return '|'.join(map(str.strip, leading))

# Templates
VALID_AMPERSANDS_TEMPLATE = Template('(?:(?<=$leading)($char)(?=$trailing))')
VALID_HYPHENS_TEMPLATE = Template('$leading$char(?=$trailing)')

# Building blocks
GNIS_NAME = f"(?i)(?P<geotype>{'|'.join(GNIS_GEOTYPES)}) of (?P<town>.+)"
SUFFIX_REPLACEMENTS = {
    f'(?i)(?<![A-Z]){full}(?=S?$)': abbr
    for full, abbr in ABBREVIATIONS.items()
}
VALID_AMPERSANDS = _generate_valid_punctuation_regex('&', VALID_AMPERSANDS_TEMPLATE)
VALID_HYPHENS = _generate_valid_punctuation_regex('-', VALID_HYPHENS_TEMPLATE)
ALL_SUFFIXES = '|'.join([*ABBREVIATIONS.keys(), *ABBREVIATIONS.values()])
PRECEDES_FALSE_SUFFIX = _generate_false_suffix_regex()

# Patterns
GNIS_PATTERN = re.compile(GNIS_NAME)
SUFFIX_PATTERN = re.compile(f"(?i)(?<!{PRECEDES_FALSE_SUFFIX}) ({ALL_SUFFIXES})S?$")
VALID_AMPERSANDS_PATTERN = re.compile('(?i)' +'|'.join(VALID_AMPERSANDS))
INVALID_PUNCTUATION_PATTERN = re.compile(f"(?i){PUNCTUATION}(?<!{'|'.join(VALID_HYPHENS)})")

## Unspecified groups
# Constants
UNSPECIFIED_FLAG = 'TWPS'
STANDARD_FLAG = 'UNSPECIFIED'
MULTI_COUNTY_REGISTRATION_TOWNS = set(['MILLINOCKET'])

# Building blocks
PLURAL = UNSPECIFIED_FLAG
SINGULAR = re.sub('S\\b', '', UNSPECIFIED_FLAG)
UNSPECIFIED_REGTOWN = f"(?P<regtown>{'|'.join(MULTI_COUNTY_REGISTRATION_TOWNS)})"
UNSPECIFIED_COUNTY = f"(?P<cty>{'|'.join(COUNTIES.sos_county)})"
SOS_FLAG = f"(?P<sos_flag>{UNSPECIFIED_FLAG}?)"

# Patterns
PLURAL_PATTERN = re.compile(f'\\b{PLURAL}\\b')
SINGULAR_PATTERN = re.compile(f'\\b{SINGULAR}\\b')
MULTI_COUNTY_PATTERN = re.compile(f"(?i){UNSPECIFIED_REGTOWN} {UNSPECIFIED_COUNTY}\\w* {SOS_FLAG}")
MULTI_COUNTY_FORMAT = r"\g<regtown> \g<sos_flag> [\g<cty>]"
FORMATTED_GROUP_PATTERN = re.compile(f'{STANDARD_FLAG} (?P<regtown>\\w+.*) {UNSPECIFIED_FLAG}( \\[{UNSPECIFIED_COUNTY}\\])?')

## Other
# Known typos in election result files
KNOWN_TYPOS = {
    'MARIONTWP' : 'MARION TWP',
    'CONNER' : 'CONNOR',
    'EDUMUNDS' : 'EDMUNDS',
    'ELLIOTSVILLE' : 'ELLIOTTSVILLE',
    'ORNVEILLE' : 'ORNEVILLE',
    'SILIVER RIDGE TWP': 'SILVER RIDGE TWP',
    'FRANKLIN/T9 T10 SD': 'FRANKLIN/T9 SD/T10 SD',
    '^PENOBSCOT TWPS$': 'MILLINOCKET PENOBSCOT TWPS',
    '^PISCATAQUIS TWPS$': 'MILLINOCKET PISCATAQUIS TWPS',
    'PLEASANT POINT VOTING DISTRICT RICT': 'PLEASANT POINT VOTING DISTRICT'
}
