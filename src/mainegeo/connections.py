from importlib import resources

COUNTIES_JSON = resources.files('mainegeo.data').joinpath('counties.json')
TOWNSHIPS_JSON = resources.files('mainegeo.data').joinpath('townships.json')
TOWNSHIPS_YAML = resources.files('mainegeo.data').joinpath('townships.yaml')
OVERRIDES_YAML = resources.files('mainegeo.data').joinpath('overrides.yaml')