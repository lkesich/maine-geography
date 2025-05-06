import pandas as pd
from importlib import resources
from functools import cached_property, cache

def cached_class_attr(f):
    return classmethod(property(cache(f)))

class CountyLookup:
    @cached_class_attr
    def csv_path(cls):
        return resources.files('mainegeo.data').joinpath('counties.csv')

    def __init__(self):
        with self.csv_path.open('r') as f:
            data = pd.read_csv(f).replace({float('nan'): None})
            for column in data.columns:
                setattr(self, column, data[column])
            self.data = data.to_dict(orient="records")
            self.code_to_fips = dict(zip(self.sos_county, self.county_fips))
            self.name_to_fips = dict(zip(self.county_name, self.county_fips))
            self.fips_to_code = dict(zip(self.county_fips, self.sos_county))
            self.name_to_code = dict(zip(self.county_name, self.sos_county))
            self.code_to_name = dict(zip(self.sos_county, self.county_name))
            self.fips_to_name = dict(zip(self.county_fips, self.county_name))

class TownshipLookup:
    @cached_class_attr
    def json_path(cls):
        """ Unprocessed data """
        return resources.files('mainegeo.data').joinpath('townships.json')

    def __init__(self):
        with self.json_path.open('r') as f:
            data = pd.read_json(f)
            for column in data.columns:
                setattr(self, column, data[column])
            self.data = data.to_dict(orient="records")