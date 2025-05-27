"""This module generates or loads a database of Maine town names and their
aliases, and provides a function for matching.
"""

__docformat__ = 'google'

__all__ = [
    # Classes
    'TownReference',
    'TownDatabase'
]

from dataclasses import dataclass
from functools import cached_property, cache
from typing import List, Dict, Optional
from importlib import resources
from pathlib import Path
import yaml
from mainegeo.connections import TownshipDataSource
from mainegeo.entities import (County, Cousub, TownType)
from mainegeo.townships import (
    clean_code,
    clean_town,
    strip_suffix,
    strip_region,
    toggle_suffix,
    extract_alias
)

def cached_class_attr(f):
    return classmethod(property(cache(f)))

@dataclass
class TownReference:
    name: str
    geocode: str
    gnis_id: int
    town_type: TownType
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

        township_aliases = filter(None, map(extract_alias, aliases))
        aliases.extend(list(township_aliases))

        if self.town_type in (TownType.UNORGANIZED, TownType.ISLAND):
            aliases.extend(list(map(toggle_suffix, aliases)))
        
        self.aliases = list(set(aliases))
        self.aliases.sort()

@dataclass(frozen=True)
class TownAlias:
    """ A lightweight frozen container holding the minimum elements required for matching.
    """
    name: str
    county_fips: Optional[int] = None

@dataclass
class TownDatabase(TownshipDataSource):
    data: List[TownReference] = None
    _processed: bool = False
    
    def __post_init__(self):
        if self._processed is False:
            self._process_data()
            self._validate_data()
    
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
    
    @staticmethod
    def json_object_hook(json_record):
        return TownReference(
            name = json_record['town'],
            geocode = json_record['town_geocode'],
            gnis_id = json_record['gnis_id'],
            town_type = TownType(json_record['geotype']),
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
                json_record['misspellings'],
                json_record['islands']
            ],
            _processed = False
        )
    
    @classmethod
    def load_from_yaml(cls, file_path = None):
        file_path = file_path or cls.yaml_path
         
        with open(file_path, 'r') as f:
            data = yaml.safe_load(f)
            towns = []
            
            for yml in data['towns']:
                town = TownReference(
                    name = yml['name'],
                    geocode = yml['geocode'],
                    gnis_id = yml['gnis_id'],
                    town_type = TownType(yml['town_type']),
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
        
    def save_to_yaml(self, file_path = None):
        file_path = file_path or self.yaml_path
        
        serializable_data = {
            'towns': [
                {
                    'name': town.name,
                    'geocode': town.geocode,
                    'town_type': town.town_type.value,
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
                if TownAlias(alias_name, town.county.fips) in self.alias_lookup.keys()
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
            canonical = town.name.upper()
            
            for alias_name in town.aliases:
                state_alias = TownAlias(alias_name)
                county_alias = TownAlias(alias_name, town.county.fips)
                
                for alias in (state_alias, county_alias):
                    if alias in self._unique_aliases or alias_name == canonical:
                        records[alias] = town
        return records
            
    def search_database(self, **kwargs) -> List[TownReference]:
        return [
            town for town in self.data
            if all(getattr(town, k) == v for k, v in kwargs.items())
        ]
            
    def match(self, town: str, county_fips: int = None, cleaned: bool = True) -> TownReference:
        """
        Match a town name variant to the alias database and return the TownReference object.

        Args:
            town: A single town or township name
            county_fips: Integer code for county. If used, will improve match rate.
            cleaned: True if the town name is already clean, False if it should be cleaned.

        Examples:
            >>> towndb = TownDatabase.build()
            >>> towndb.match('Cross Lake Twp (T17 R5)', cleaned = False).name
            'Cross Lake Twp'
            >>> towndb.match('Prentiss Twp') is None
            True
            >>> towndb.match('Prentiss Twp', county_fips = 19).name
            'Prentiss Twp T7 R3 NBPP'
        """
        town_name = town.upper() if cleaned else clean_town(town.upper())

        def lazy_get_code(unmatched_town: str):
            township_code = clean_code(unmatched_town)
            if township_code != unmatched_town:
                return township_code
            
        def lazy_get_alias(unmatched_town: str):
            township_alias = extract_alias(unmatched_town)
            if township_alias != unmatched_town:
                return township_alias
        
        # lazy evaluation
        names = [
            lambda: town_name,
            lambda: lazy_get_code(town_name),
            lambda: lazy_get_alias(town_name)
        ]

        for get_name in names:
            name = get_name()
            if name:           
                state_alias = TownAlias(name)
                state_match = self.alias_lookup.get(state_alias)
                
                if state_match:
                    return state_match
                
                if county_fips is None:
                    continue

                county_alias = TownAlias(name, county_fips)
                county_match = self.alias_lookup.get(county_alias)

                if county_match:
                    return county_match
            
    def canonical_name(self, town: str, county_fips: Optional[int] = None) -> str:
        """
        Match a town to the alias database and return the canonical name only.
        """
        match = self.match(town, county_fips)
        if match:
            return match.name