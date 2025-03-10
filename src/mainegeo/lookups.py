import pandas as pd
from importlib import resources

class CountyLookup(object):
    def __init__(self):
        with resources.files('mainegeo.data').joinpath('counties.csv').open('r') as f:
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

class TownshipLookup(object):
    def __init__(self):
        with resources.files('mainegeo.data').joinpath('townships.csv').open('r') as f:
            data = pd.read_csv(f).replace({float('nan'): None})
            for column in data.columns:
                setattr(self, column, data[column])
            self.data = data.to_dict(orient="records")