from dataclasses import dataclass
from mainegeo import lookups
from enum import Enum

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
    fips: str|int = None

    _lookup = None
    
    def __post_init__(self):
        self._get_missing_info()
    
    @classmethod
    def _get_lookup(cls):
        if cls._lookup is None:
            cls._lookup = lookups.CountyLookup()
        return cls._lookup

    def _get_missing_info(self):
        if all((self.name, self.code, self.fips)):
            return        
        elif not any((self.name, self.code, self.fips)):
            return
        else:
            lookup = self._get_lookup()        
            if self.fips is None:
                if self.code is not None:
                    self.fips = lookup.code_to_fips.get(self.code)
                else:
                    self.fips = lookup.name_to_fips.get(self.name)
            if self.code is None:
                if self.fips is not None:
                    self.code = lookup.fips_to_code.get(int(self.fips))
                else:
                    self.code = lookup.name_to_code.get(self.name)
            if self.name is None:
                if self.fips is not None:
                    self.name = lookup.fips_to_name.get(int(self.fips))
                else:
                    self.name = lookup.code_to_name.get(self.code)