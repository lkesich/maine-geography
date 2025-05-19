from importlib import resources
from functools import cache

def cached_class_attr(f):
    return classmethod(property(cache(f)))

class CountyDataSource:
    @cached_class_attr
    def csv_path(cls):
        return resources.files('mainegeo.data').joinpath('counties.csv')
    
class TownshipDataSource:
    @cached_class_attr
    def json_path(cls):
        """ Unprocessed data """
        return resources.files('mainegeo.data').joinpath('townships.json')