from dataclasses import dataclass
from enum import Enum
from mainegeo.lookups import CountyData

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
        if self.fips:
            self.fips = int(self.fips)
            
        if not all((self.name, self.code, self.fips)):
            lookup = CountyData.get_lookup()
            fips = self.fips
            code = self.code
            name = self.name
            self.fips = fips or lookup.code_to_fips.get(code) or lookup.name_to_fips.get(name)
            self.code = code or lookup.fips_to_code.get(fips) or lookup.name_to_code.get(name)
            self.name = name or lookup.fips_to_name.get(fips) or lookup.code_to_name.get(code)