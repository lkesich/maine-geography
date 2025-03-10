"""This module generates or loads a database of Maine town names and their
aliases, and provides a function for matching.
"""

__docformat__ = 'google'

__all__ = [
    # Classes
    'TownDatabase'
]

from dataclasses import dataclass
from typing import List
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
            self._remove_duplicate_aliases_within_county()
            self.data.sort(key=lambda x: x.name)
            self._processed = True

    def _remove_all_duplicate_aliases(self):
        all = []
        for town in self.data:
            all.extend(town.aliases)
        
        unique_in_state = set([alias for alias in all if all.count(alias) == 1])
        
        for town in self.data:
            canonical = town.name.upper()
            town.aliases = [a for a in town.aliases if a in unique_in_state or a == canonical]

    def _remove_duplicate_aliases_within_county(self):
        all = []
        for town in self.data:
            all.extend(map(lambda alias: f'{alias}_{town.county.fips}', town.aliases))

        unique_in_county = [alias.split('_')[0] for alias in all if all.count(alias) == 1]
        
        for town in self.data:
            canonical = town.name.upper()
            town.aliases = [a for a in town.aliases if a in unique_in_county or a == canonical]
            
    def match_town(self, town: str, county_fips: int = None) -> str:
        if town in (None, ''):
            return None

        statewide = [i for i in self.data if town.upper() in i.aliases]
        if not any(statewide):
            return None
        elif len(statewide) == 1:
            return statewide[0].name
        elif county_fips is None:
            return None
        else:
            countywide = [i for i in statewide if county_fips == i.county.fips]
            if len(countywide) == 1:
                return countywide[0].name
            else:
                return None