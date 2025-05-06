from dataclasses import dataclass
from mainegeo import lookups
from enum import Enum
from functools import cache, cached_property
from typing import Optional, List
from mainegeo.townships import (
    clean_code,
    clean_town,
    strip_suffix,
    strip_region
)

def cached_class_attr(f):
    return classmethod(property(cache(f)))

class NameType(Enum):
    HISTORICAL = "historical"
    VARIANT = "variant"
    TRIBAL = "tribal"
    VOTING = "voting"
    ISLAND = "island"
    CANONICAL = "canonical"

class TownType(Enum):
    TOWN = "Town"
    CITY = "City"
    PLANTATION = "Plantation"
    RESERVATION = "Reservation"
    UNORGANIZED = "Unorganized Township"
    ISLAND = "Island Group"

@dataclass
class Cousub:
    geocode: str|int = None
    name: str = None
    basename: str = None
    geoclass: str = None

@dataclass
class County:
    name: str = None
    code: str = None
    fips: int = None
    
    def __post_init__(self):
        self._assign_missing_attributes()
    
    @cached_class_attr
    def lookup(cls):
        return lookups.CountyLookup()
            
    def _assign_missing_attributes(self):
        attrs = (self.name, self.code, self.fips)
        if not all(attrs):
            self.fips = self.fips or self.lookup.code_to_fips.get(self.code) or self.lookup.name_to_fips.get(self.name)
            self.code = self.code or self.lookup.fips_to_code.get(self.fips) or self.lookup.name_to_code.get(self.name)
            self.name = self.name or self.lookup.fips_to_name.get(self.fips) or self.lookup.code_to_name.get(self.code)

@dataclass(frozen=True)
class TownAlias:
    """ A lightweight frozen container holding the minimum elements required for matching.
    """
    name: str
    county_fips: Optional[int] = None

@dataclass
class TownReference:
    name: str
    geocode: str
    gnis_id: int
    town_type: str
    county: County
    cousub: Cousub
    aliases: List[str]
    _processed: Optional[bool] = False

    def __post_init__(self):
        if not self._processed:
            self._clean_aliases()
            self._infer_aliases()
            self._processed = True

    def _clean_aliases(self):
        aliases = sum(self.aliases, [])
        aliases = map(str.upper, filter(None, aliases))
        self.aliases = list(set(aliases))
        
    def _infer_aliases(self):
        aliases = self.aliases
        aliases.extend(list(map(clean_code, aliases)))
        aliases.extend(list(map(clean_town, aliases)))
        aliases.extend(list(map(strip_suffix, aliases)))
        aliases.extend(list(map(strip_region, aliases)))
        aliases.extend(list(map(strip_region, aliases))) # 2x
        self.aliases = list(set(aliases))
        self.aliases.sort()