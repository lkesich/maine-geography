from dataclasses import dataclass
from mainegeo import lookups
from functools import cache
from enum import Enum

def cached_class_attr(f):
    """
    @private
    """
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
        self._normalize_types()
        self._assign_missing_attributes()
    
    @cached_class_attr
    def _lookup(cls):
        return lookups.CountyData()
    
    def _normalize_types(self):
        if self.fips: self.fips = int(self.fips)
            
    def _assign_missing_attributes(self):
        attrs = (self.name, self.code, self.fips)
        if not all(attrs):
            l = self._lookup
            self.fips = self.fips or l.code_to_fips.get(self.code) or l.name_to_fips.get(self.name)
            self.code = self.code or l.fips_to_code.get(self.fips) or l.name_to_code.get(self.name)
            self.name = self.name or l.fips_to_name.get(self.fips) or l.code_to_name.get(self.code)