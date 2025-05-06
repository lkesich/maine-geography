"""This module generates or loads a database of Maine town names and their
aliases, and provides a function for matching.
"""

__docformat__ = 'google'

__all__ = [
    # Classes
    'TownDatabase'
]

from dataclasses import dataclass
from functools import cached_property, cache
from typing import List, Dict, Optional
from mainegeo import lookups
from mainegeo.entities import County, Cousub, TownReference, TownAlias
from importlib import resources
from pathlib import Path
import yaml

def cached_class_attr(f):
    return classmethod(property(cache(f)))

@dataclass
class TownDatabase:
    data: List[TownReference] = None
    _processed: bool = False
    
    def __post_init__(self):
        if self._processed is False:
            self._process_data()
            self._validate_data()

    @cached_class_attr
    def json_path(cls):
        """ Unprocessed data """
        return resources.files('mainegeo.data').joinpath('townships.json')
    
    @cached_class_attr
    def yaml_path(cls):
        """ Processed data """
        return resources.files('mainegeo.data').joinpath('townships.yaml')

    @classmethod
    def build(cls):
        file_path = resources.files('mainegeo.data').joinpath('townships.yaml')    
        # first call
        if Path(file_path).exists():
            return cls.load_from_yaml(file_path)
        # subsequent calls
        else:
            towndb = cls.create_from_raw_data()
            towndb.save_to_yaml(file_path)
            return towndb

    @classmethod
    def create_from_raw_data(cls):
        import json
        with cls.json_path.open('r') as file:
            towns = json.load(file, object_hook=cls.json_object_hook)
            return cls(towns, _processed=False)
    
    @cached_class_attr
    def json_object_hook(cls, json_record):
        return TownReference(
            name = json_record['town'],
            geocode = json_record['town_geocode'],
            gnis_id = json_record['gnis_id'],
            town_type = json_record['geotype'],
            county = County(
                fips = json_record['county_fips'], 
                name = json_record['county_name'],
                code = json_record['sos_county']
            ),
            cousub = Cousub(
                geocode = json_record['cousub_geocode'],
                name = json_record['cousub_name'],
                basename = json_record['cousub_basename'],
                geoclass = json_record['class']
            ),
            aliases = [
                [
                    json_record['maine_gis_name'],
                    json_record['town'],
                    json_record['cousub_basename'],
                    json_record['voting_name'],
                    json_record['tribal_name']
                ],
                json_record['gnis_variants'],
                json_record['historical_names'],
                json_record['islands']
            ],
            _processed = False
        )
    
    @classmethod
    def load_from_yaml(cls, file_path = None):
        if file_path is None:
            file_path = cls.yaml_path
         
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
        geocodes = [town.geocode for town in self.data]
        if not all(geocodes):
            raise ValueError("Missing geocodes in source data")
        elif len(geocodes) != len(set(geocodes)):
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
            for alias_name in town.aliases:
                all.append(TownAlias(alias_name))
                all.append(TownAlias(alias_name, town.county.fips))
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
                state_alias = TownAlias(alias_name)
                county_alias = TownAlias(alias_name, town.county.fips)
                for alias in (state_alias, county_alias):
                    if alias in self._unique_aliases:
                        records[alias] = town
        return records
            
    def search_database(self, **kwargs) -> List[TownReference]:
        return [
            town for town in self.data
            if all(getattr(town, k) == v for k, v in kwargs.items())
        ]
        
    def match(self, town: str, county_fips: Optional[int] = None) -> TownReference:
        """
        Match a town name variant to the alias database and return the TownReference object.
        """
        state_alias = TownAlias(town.upper())
        state_match = self.alias_lookup.get(state_alias)
        if state_match:
            return state_match
        elif county_fips:
            county_alias = TownAlias(town.upper(), county_fips)
            county_match = self.alias_lookup.get(county_alias)
            return county_match
    
    def canonical_name(self, town: str, county_fips: Optional[int] = None) -> str:
        """
        Match a town to the alias database and return the canonical name only.
        """
        match = self.match(town, county_fips)
        if match:
            return match.name