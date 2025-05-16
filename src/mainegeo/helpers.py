"""This module generates or loads a database of Maine town names and their
aliases, and provides a function for matching.
"""

__docformat__ = 'google'

__all__ = [
    'Helpers1',
    'Helpers2',
    'TownshipPatterns'
]

import pandas as pd
from importlib import resources
from functools import cache, cached_property
import re
from mainegeo.lookups import CountyData, TownshipData
from string import Template
from typing import List

def cached_class_attr(f):
    return classmethod(property(cache(f)))

class Helpers1:
    """Constants and patterns for township name parsing.
    
    This class provides documentation and organization for township-related
    constants without creating instances. All attributes are class-level.
    """
    @cached_property
    def COUNTIES(self) -> CountyData:
        return CountyData()
    
    @cached_property
    def TOWNSHIPS(self) -> TownshipData:
        return TownshipData()

    @cached_property
    def REGIONS(self) -> List[str]:
        """Valid region codes that can appear in township names.
        
        These are two- to four-letter codes like 'WELS' (West of the 
        Easterly Line of the State) or 'BPP' (Bingham's Penobscot Purchase).
        """
        return ["ED","MD","ND","SD","TS","BKP","BPP","EKR","NWP","WKR","NBKP","NBPP","WBKP","WELS"]
    
    @cached_property
    def GNIS_GEOTYPES(self) -> List[str]:
        """Geographic Names Information System (GNIS) """
        return ["CITY", "PLANTATION", "TOWNSHIP", "TOWN"]

class Helpers2:
    """Constants and patterns for township name parsing.
    
    This class provides documentation and organization for township-related
    constants without creating instances. All attributes are class-level.
    """
    
    REGIONS = ["ED","MD","ND","SD","TS","BKP","BPP","EKR","NWP","WKR","NBKP","NBPP","WBKP","WELS"]
    """ Valid region codes that can appear in township names.
    
    These are two- to four-letter codes like 'WELS' (West of the
    Easterly Line of the State) or 'BPP' (Bingham's Penobscot Purchase)."""
    
    GNIS_GEOTYPES = ["CITY", "PLANTATION", "TOWNSHIP", "TOWN"]
    """Geographic Names Information System (GNIS)"""

    ABBREVIATIONS = {
        "PLANTATION": "PLT",
        "TOWNSHIP": "TWP",
        "VOTING DISTRICT": "VOTING DIST",
        "RESERVATION": "RES"
    }
    """Add docstring"""

class TownshipPatterns:
    """Constants and patterns for township name parsing.
    
    This class provides documentation and organization for township-related
    constants without creating instances. All attributes are class-level.
    """
    
    REGIONS: List[str] = ["ED","MD","ND","SD","TS","BKP","BPP","EKR","NWP","WKR","NBKP","NBPP","WBKP","WELS"]
    """ Valid region codes that can appear in township names.
    
    These are two- to four-letter codes like 'WELS' (West of the
    Easterly Line of the State) or 'BPP' (Bingham's Penobscot Purchase)."""

    REGION: str = f"(?:{'|'.join(REGIONS)})"
    """ Regex building block representing a region designator.
    
    Township names can contain zero, one, or two regions.
    """

    RANGE: str = f"(?:R.?[\\d]{{1,2}})"
    """ Regex building block representing a range designator.

    Ranges are counted from the easterly line toward the west,
    numbered 1-19 (e.g., R1, R19).
    """

    FUZZY: str = f"[^,\\w]{{0,3}}"
    PUNCTUATION: str = f'[^ \\w]'

    TOWNSHIP_STANDARD: str = "(?:T.?\\d{1,2})"
    TOWNSHIP_ALTERNATE: str = f"(?<!\\w)T[ABCDX](?![a-z])"
    TOWNSHIP: str = f"(?:{TOWNSHIP_STANDARD}|{TOWNSHIP_ALTERNATE})"
    """ Regex building block representing a township designator.
    
    Townships are designated by:
        - Numbers 1-19 from south to north (e.g., T1, T19)
        - Occasional letter designations (TA, TB, TC, TD, TX)
    """

    UNNAMED: str = f"((?:{TOWNSHIP})(?:{FUZZY}{RANGE})?(?:{FUZZY}{REGION}){{0,2}})"
    """ Uncompiled string representing a full unnamed township name."""

    UNNAMED_ELEMENTS: str = f"(?:{'|'.join([TOWNSHIP, RANGE, REGION])})"
    """Add docstring"""

    UNNAMED_PATTERN: re.Pattern = re.compile(UNNAMED, re.I)
    """Add docstring
    
    Used in `mainegeo.townships.is_unnamed_township` and `mainegeo.townships.clean_codes`."""

    UNNAMED_ELEMENTS_PATTERN: re.Pattern = re.compile(UNNAMED_ELEMENTS, re.I)
    """Pattern for finding unnamed township name elements regardless of formatting.
    
    Used in `mainegeo.townships.clean_code`."""

    LAST_REGION_PATTERN: re.Pattern = re.compile(f" {REGION}$", re.I)
    """Add docstring
    
    Used in `mainegeo.townships.strip_region`."""
    
    @cached_property
    def TOWNSHIP_(self) -> str:
        """ Regex building block representing a township designator.
    
        Townships are designated by:
            - Numbers 1-19 from south to north (e.g., T1, T19)
            - Occasional letter designations (TA, TB, TC, TD, TX)
        """
        TOWNSHIP_STANDARD = "(?:T.?\\d{1,2})"
        TOWNSHIP_ALTERNATE = f"(?<!\\w)T[ABCDX](?![a-z])"
        return f"(?:{TOWNSHIP_STANDARD}|{TOWNSHIP_ALTERNATE})"