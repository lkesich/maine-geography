import pandas as pd
from importlib import resources
from functools import cache, cached_property

def cached_class_attr(f):
    return classmethod(property(cache(f)))

class CountyData:
    @cached_class_attr
    def csv_path(cls):
        return resources.files('mainegeo.data').joinpath('counties.csv')

    def __init__(self):
        with self.csv_path.open('r') as f:
            data = pd.read_csv(f)
            for column in data.columns:
                setattr(self, column, data[column])
            
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

class TownshipData:
    @cached_class_attr
    def json_path(cls):
        """ Unprocessed data """
        return resources.files('mainegeo.data').joinpath('townships.json')

    def __init__(self):
        with self.json_path.open('r') as f:
            data = pd.read_json(f)
            for column in data.columns:
                setattr(self, column, data[column])