"""This module generates or loads a database of Maine town names and their
aliases, and provides a function for matching.
"""

__docformat__ = 'google'

__all__ = [
    # Classes
    'TownDatabase'
]

from dataclasses import dataclass
from functools import cache, cached_property
from typing import List, Dict
from mainegeo import townships, lookups
from mainegeo.entities import County, Cousub
from importlib import resources
from pathlib import Path
import yaml

@dataclass
class TownReference:
    name: str
    geocode: str
    gnis_id: int
    town_type: str
    county: County
    cousub: Cousub
    aliases: List[str]
    _processed: bool = False

    def __post_init__(self):
        if self._processed is False:
            self._clean_aliases()
            self._generate_aliases()

    def _clean_aliases(self):
        aliases = filter(None, self.aliases)
        aliases = sum([a.strip('[]').split(',') for a in aliases], [])
        aliases = map(str.upper, aliases)
        aliases = map(str.strip, aliases)
        self.aliases = list(set(filter(None, aliases)))
        
    def _generate_aliases(self):
        aliases = self.aliases
        aliases.extend(filter(None, [self.name.upper(), self.cousub.basename.upper()]))
        aliases.extend(list(map(townships.clean_code, aliases)))
        aliases.extend(list(map(townships.clean_town, aliases)))
        aliases.extend(list(map(townships.strip_suffix, aliases)))
        aliases.extend(list(map(townships.strip_region, aliases)))
        aliases.extend(list(map(townships.strip_region, aliases))) # 2x
        self.aliases = list(set(aliases))
        self.aliases.sort()

@dataclass
class TownReference:
    name: str
    geocode: str
    gnis_id: int
    town_type: str
    county: County
    cousub: Cousub
    aliases: List[str]
    _processed: bool = False

    def __post_init__(self):
        if self._processed is False:
            self._clean_aliases()
            self._generate_aliases()

    def _clean_aliases(self):
        aliases = filter(None, self.aliases)
        aliases = sum([a.strip('[]').split(',') for a in aliases], [])
        aliases = map(str.upper, aliases)
        aliases = map(str.strip, aliases)
        self.aliases = list(set(filter(None, aliases)))
        
    def _generate_aliases(self):
        aliases = self.aliases
        aliases.extend(filter(None, [self.name.upper(), self.cousub.basename.upper()]))
        aliases.extend(list(map(townships.clean_code, aliases)))
        aliases.extend(list(map(townships.clean_town, aliases)))
        aliases.extend(list(map(townships.strip_suffix, aliases)))
        aliases.extend(list(map(townships.strip_region, aliases)))
        aliases.extend(list(map(townships.strip_region, aliases))) # 2x
        self.aliases = list(set(aliases))
        self.aliases.sort()

@dataclass(frozen=True)
class TownAlias:
    name: str
    county_fips: int

@dataclass
class TownDatabase:
    data: List[TownReference] = None
    _processed: bool = False
    
    def __post_init__(self):
        if self._processed is False:
            self._process_data()

    @classmethod
    def build(cls):
        file_path = resources.files('mainegeo.data').joinpath('townships.yaml')    
        if Path(file_path).exists():    # first call
            return cls.load_from_yaml(file_path)
        else:    # subsequent calls
            towndb = cls.create_from_raw_data()
            towndb.save_to_yaml(file_path)
            return towndb

    @classmethod
    def create_from_raw_data(cls):
        townships = lookups.TownshipLookup().data   
        towns = [
            TownReference(
                name = record['town'],
                geocode = record['town_geocode'],
                gnis_id = record['gnis_id'],
                town_type = record['geotype'],
                county = County(
                    fips = record['county_fips'], 
                    name = record['county_name'],
                    code = record['sos_county']
                ),
                cousub = Cousub(
                    geocode = record['cousub_geocode'],
                    name = record['cousub_name'],
                    basename = record['cousub_basename'],
                    geoclass = record['class']
                ),
                aliases = [
                    record['maine_gis_name'],
                    record['voting_name'],
                    record['tribal_name'],
                    record['gnis_variants'],
                    record['historical_names'],
                    record['islands']
                ],
                _processed = False
            ) for record in townships
        ]
        return cls(towns, _processed=False)
    
    @classmethod
    def load_from_yaml(cls, file_path = None):
        if file_path is None:
            file_path = resources.files('mainegeo.data').joinpath('townships.yaml')
         
        with open(file_path, 'r') as f:
            data = yaml.safe_load(f)
            towns = []
            
            for yml in data['towns']:
                town = TownReference(
                    name = yml['name'],
                    geocode = yml['geocode'],
                    gnis_id = yml['gnis_id'],
                    town_type = yml['town_type'],
                    county = County(
                        fips = yml['county']['fips'], 
                        name = yml['county']['name'],
                        code = yml['county']['code']
                    ),
                    cousub = Cousub(
                        geocode = yml['cousub']['geocode'],
                        name = yml['cousub']['name'],
                        basename = yml['cousub']['basename'],
                        geoclass = yml['cousub']['geoclass']
                    ),
                    aliases = yml['aliases'],
                    _processed = True
                )
                towns.append(town)
            
            return cls(towns, _processed=True)
        
    def save_to_yaml(self, file_path):
        serializable_data = {
            'towns': [
                {
                    'name': town.name,
                    'geocode': town.geocode,
                    'town_type': town.town_type,
                    'gnis_id': town.gnis_id,
                    'county': {
                        'fips': town.county.fips,
                        'name': town.county.name,
                        'code': town.county.code
                    },
                    'cousub' : {
                        'geocode': town.cousub.geocode,
                        'name': town.cousub.name,
                        'basename': town.cousub.basename,
                        'geoclass': town.cousub.geoclass
                    },
                    'aliases': town.aliases
                } for town in self.data
            ]
        }

        output_dir = Path(__file__).parent / "data"
        output_dir.mkdir(exist_ok=True)
        
        with open(file_path, 'w') as f:
            yaml.dump(serializable_data, f, sort_keys=False)

    def _process_data(self):
        if self.data is not None:
            self._remove_duplicate_aliases()
            self.data.sort(key=lambda x: x.name)
            self._processed = True

    def _validate_data(self):
        if None in self.data.geocodes:
            raise ValueError("Missing geocodes in source data")
        elif len(self.data.geocodes) - len(set(self.data.geocodes)) != 0:
            raise ValueError("Non-unique geocodes in source data")

    def _remove_duplicate_aliases(self):
        for town in self.data:
            town.aliases = [
                alias_name for alias_name in town.aliases
                if TownAlias(alias_name, town.county.fips) in self._unique_aliases
                or alias_name == town.name.upper()
            ]

    @cached_property
    def _suggested_aliases(self) -> List[TownAlias]:
        all = []
        for town in self.data:
            for alias in town.aliases:
                all.append(TownAlias(alias, town.county.fips))
        return all
    
    @cached_property
    def _unique_aliases(self) -> List[TownAlias]:
        counts = {}
        for alias in self._suggested_aliases:
            counts[alias] = counts.get(alias, 0) + 1
        return [alias for alias, count in counts.items() if count == 1]
    
    @cached_property
    def alias_lookup(self) -> Dict[TownAlias, TownReference]:
        records = {}
        for town in self.data:
            for alias_name in town.aliases:
                alias = TownAlias(alias_name, town.county.fips)
                if alias in self._unique_aliases:
                    records[alias] = town
        return records
            
    def search_database(self, **kwargs) -> List[TownReference]:
        return [
            town for town in self.data
            if all(getattr(town, k) == v for k, v in kwargs.items())
        ]
    
    def match(self, town: str, county_fips: int = None) -> TownReference:
        return self.alias_lookup[TownAlias(town.upper(), county_fips)]