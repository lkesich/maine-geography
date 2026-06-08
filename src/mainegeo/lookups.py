__docformat__ = 'google'

__all__ = [
    'Overrides',
    'TownshipData',
    'CountyData'
]

from ruamel.yaml import YAML
import json
from collections import defaultdict
from dataclasses import dataclass
from functools import cached_property
from typing import ClassVar
from pathlib import Path

from mainegeo.connections import (
    OVERRIDES_YAML,
    COUNTIES_JSON,
    TOWNSHIPS_JSON
)

yaml = YAML()
yaml.indent(mapping = 2, sequence = 4)

@dataclass
class Lookup:
    DATA_SOURCE: ClassVar[Path] = None
    
    def __post_init__(self):
        self.set_data()
        self.set_convenience_attrs()
        
    @property
    def loader(self):
        extension = self.DATA_SOURCE.suffix.lower()
        if extension == '.json':
            return json.load
        elif extension in ('.yaml', '.yml'):
            return yaml.load
    
    def load_data(self):
        with open(self.DATA_SOURCE) as f:
            return self.loader(f)
    
    def set_data(self):
        data = self.load_data()
        if isinstance(data, list):
            data = Lookup.invert_list_of_dicts(data)
        self.data = data
                
    def set_convenience_attrs(self):
        for key in self.data.keys():
            if key in self.__dataclass_fields__.keys():
                setattr(self, key, self.data[key])
    
    @staticmethod
    def invert_list_of_dicts(dictionaries: list[dict]):
        result = defaultdict(list)
        for dictionary in dictionaries:
            for key, value in dictionary.items():
                result[key].append(value)
        return dict(result)

@dataclass     
class Overrides(Lookup):
    known_typos: dict = None
    ambiguous_groups: dict = None
    
    DATA_SOURCE: ClassVar[Path] = OVERRIDES_YAML
    
    def add_typo(self, original: str, replacement: str, notes: str = None):
        data = self.load_data()
        entry_template = {
            'original': original,
            'replacement': replacement,
            'notes': notes
        }
        entry = {k: v for k, v in entry_template.items() if v}
        data['known_typos'].append(entry)
        
        with open(self.DATA_SOURCE, 'w') as f:
            yaml.dump(data, f)
            
        self.__post_init__()
            
    def add_group_pattern(self, pattern: str, replacement: str, notes: str = None):
        data = self.load_data()
        entry_template = {
            'pattern': pattern,
            'replacement': replacement,
            'notes': notes
        }
        entry = {k: v for k, v in entry_template.items() if v}
        data['ambiguous_groups'].append(entry)
        
        with open(self.DATA_SOURCE, 'w') as f:
            yaml.dump(data, f)
        
        self.__post_init__()

@dataclass       
class TownshipData(Lookup):
    town: list[str] = None
    
    DATA_SOURCE: ClassVar[Path] = TOWNSHIPS_JSON

@dataclass
class CountyData(Lookup):
    county_name: list[str] = None
    sos_county: list[str] = None
    county_fips: list[str] | list[int] = None
    
    DATA_SOURCE: ClassVar[Path] = COUNTIES_JSON
    
    def __post_init__(self):
        self.set_data()
        self.set_convenience_attrs()
        self.county_fips = [int(fips) for fips in self.county_fips]
            
    @cached_property
    def code_to_fips(self):
        return dict(zip(self.sos_county, self.county_fips))

    @cached_property
    def name_to_fips(self):
        return dict(zip(self.county_name, self.county_fips))
    
    @cached_property
    def fips_to_code(self):
        return dict(zip(self.county_fips, self.sos_county))

    @cached_property
    def name_to_code(self):
        return dict(zip(self.county_name, self.sos_county))
    
    @cached_property
    def code_to_name(self):
        return dict(zip(self.sos_county, self.county_name))
    
    @cached_property
    def fips_to_name(self):
        return dict(zip(self.county_fips, self.county_name))