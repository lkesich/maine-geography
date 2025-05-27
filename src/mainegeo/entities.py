from dataclasses import dataclass
from mainegeo import lookups
from functools import cache
from enum import Enum

def cached_class_attr(f):
    """
    @private
    """
    return classmethod(property(cache(f)))

class TownType(Enum):
    """
    Enumeration of geography types used in `mainegeo.matching.TownReference` objects.
    """
    TOWN = "Town"
    CITY = "City"
    PLANTATION = "Plantation"
    RESERVATION = "Reservation"
    UNORGANIZED = "Unorganized Township"
    ISLAND = "Island Group"

@dataclass
class Cousub:
    """
    An object representing a U.S. Census Bureau county subdivision (`COUSUB`_).

    Args:
        geocode: The ten-digit Census code (state FIPS + county FIPS + county subdivision GEOID)
        name: Census full name for county subdivision (basename + geoclass)
        basename: Census base name for county subdivision
        geoclass: Census `CLASSFP`_ code

    .. _COUSUB: https://www.census.gov/library/reference/code-lists/ansi.html#cousub         
    .. _CLASSFP: https://www.census.gov/library/reference/code-lists/class-codes.html
    """
    geocode: str|int = None
    name: str = None
    basename: str = None
    geoclass: str = None

@dataclass
class County:
    """
    An object representing a county.

    Args:
        name: Full name of the county
        code: First three letters of the county name (commonly used by SoS)
        fips: String or integer FIPS code (used by Census)

    Can be initiated with any argument. If not all arguments are provided,
    the others will be populated from a lookup table.
    """
    name: str = None
    code: str = None
    fips: str|int = None
    
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