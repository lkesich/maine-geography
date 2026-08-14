from mainegeo import elections
from pathlib import Path
import pandas as pd

TEST_DIR = Path(__file__).parent
TEST_UNITS = TEST_DIR / 'data' / 'sample_reporting_units.csv'
TEST_UNITS_TO_FILE = TEST_DIR / 'data' / 'sample_reporting_units_to_file.csv'

def parse_row(town_str: str, county_code: str):
    if town_str is None:
        return None
    try:
        return elections.ReportingUnit.from_strings(town_str, county_code).to_dict()
    except Exception as e:
        return {
            'error': type(e).__name__,
            'message': str(e),
            'is_matched': False
        }

def get_unmatched():
    with open(TEST_UNITS) as f:
        df = pd.read_csv(f)
        df['parsed'] = [
            parse_row(unit, county)
            for unit, county
            in zip(df['reporting_unit'], df['county'])
        ]
        return df[[not(unit.get('is_matched')) for unit in df['parsed']]]