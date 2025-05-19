import pandas as pd
from functools import cached_property
from keyword import iskeyword
from mainegeo.connections import CountyDataSource, TownshipDataSource

class TownshipData(TownshipDataSource):
    def __init__(self):
        with self.json_path.open('r') as f:
            data = pd.read_json(f)
            for column in data.columns:
                if not iskeyword(column):
                    setattr(self, column, data[column])

class CountyData(CountyDataSource):
    def __init__(self):
        with self.csv_path.open('r') as f:
            data = pd.read_csv(f)
            for column in data.columns:
                if not iskeyword(column):
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