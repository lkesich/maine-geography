import pandas as pd
from importlib import resources

class CountyLookup(object):
    def __init__(self):
        with resources.files('mainegeo.data').joinpath('counties.csv').open('r') as f:
            data = pd.read_csv(f)
            for column in data.columns:
                setattr(self, column, data[column])

class TownshipLookup(object):
    def __init__(self):
        with resources.files('mainegeo.data').joinpath('townships.csv').open('r') as f:
            data = pd.read_csv(f)
            for column in data.columns:
                setattr(self, column, data[column])               