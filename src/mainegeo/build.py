
from mainegeo import matching
from importlib import resources

def build_town_database():
    town_db = matching.TownDatabase.create_from_raw_data()
    file_path = resources.files('mainegeo.data').joinpath('townships.yaml')
    town_db.save_to_yaml(file_path)

if __name__ == "__main__":
    build_town_database()