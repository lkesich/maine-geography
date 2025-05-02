from dataclasses import dataclass
from mainegeo import lookups
from enum import Enum
from functools import cache

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

    _lookup = None
    
    def __post_init__(self):
        self._assign_missing_attributes()
    
    @classmethod
    def _lazy_load_lookup(cls):
        cls._lookup = cls._lookup or lookups.CountyLookup()
        return cls._lookup
            
    def _assign_missing_attributes(self):
        attrs = (self.name, self.code, self.fips)
        if not all(attrs):
            lookup = self._lazy_load_lookup()
            self.fips = self.fips or lookup.code_to_fips.get(self.code) or lookup.name_to_fips.get(self.name)
            self.code = self.code or lookup.fips_to_code.get(self.fips) or lookup.name_to_code.get(self.name)
            self.name = self.name or lookup.fips_to_name.get(self.fips) or lookup.code_to_name.get(self.code)
