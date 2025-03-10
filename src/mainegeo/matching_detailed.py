"""Place name matching.
"""

from dataclasses import dataclass
from typing import List, Optional
from itertools import permutations
import re
from mainegeo import lookups, townships
from enum import Enum
from utils.core import flatten_nested_list
import yaml
from pathlib import Path

TOWNSHIPS = lookups.TownshipLookup().data

class NameType(Enum):
    HISTORICAL = "historical"
    VARIANT = "variant"
    TRIBAL = "tribal"
    VOTING = "voting"
    ISLAND = "island"
    CANONICAL = "canonical"

class TownType(Enum):
    TOWN = "Town"
    CITY = "City"
    PLANTATION = "Plantation"
    RESERVATION = "Reservation"
    UNORGANIZED = "Unorganized Township"
    ISLAND = "Island Group"

@dataclass
class TownName:
    """Represents a single name variant for a town"""
    name: str
    name_type: NameType
    source: Optional[str] = None
    
    def __hash__(self):
        return hash(self.name)

@dataclass
class TownReference:
    geocode: str
    name: str
    county_fips: str|int
    town_type: str
    aliases: List[TownName|List[TownName]]
    cousub_geocode: str
    cousub_name: Optional[str] = None
    cousub_basename: Optional[str] = None
    cousub_class: Optional[str] = None
    gnis_feature_id: Optional[int] = None

    def __post_init__(self):
        counties = lookups.CountyLookup()
        self.fips_lookup = dict(zip(counties.county_fips, counties.data))    
        self._lookup_counties()
        self._clean_aliases()

    def _clean_aliases(self):
        aliases = self.aliases
        aliases = flatten_nested_list(aliases)
        aliases = [alias for alias in aliases if alias.name not in ('', None)]
        for alias in aliases:
            alias.name = alias.name.upper().strip()
        self.aliases = list(set(aliases))
        
    def _lookup_counties(self):
        county = self.fips_lookup.get(int(self.county_fips))
        self.county_name = county.get('county_name')
        self.county_sos_name = county.get('sos_county')


@dataclass
class TownDatabase:
    data: List[TownReference]
    
    def __post_init__(self):
        self._remove_duplicate_aliases()
        self.data.sort(key=lambda x: x.name)

    def _remove_duplicate_aliases(self):
        all = [alias for aliases in [town.aliases for town in self.data] for alias in aliases]
        unique = [alias for alias in all if all.count(alias) == 1]
        for town in self.data:
            town.aliases = [alias for alias in town.aliases if alias in unique or alias==town.name.upper()]

    def match_town(self, town: str) -> str:
        """
        Example:
            >>> match_town('T17 R4')
            'Sinclair Twp'
            >>> match_town('PENOBSCOT NATION VOTING DISTRICT')
            'Penobscot Indian Island'
        """
        candidates = [i.name for i in self.data if town.upper() in i.aliases]
        if len(candidates) < 1:
            return "No match"
        elif len(candidates) > 1:
            return f"Multiple matches: {' or '.join(candidates)}"
        else:
            return f"Match: {candidates[0]}"
        

def build_town_database():
    # Load raw data
    townships = lookups.TownshipLookup().data

    # Process the data
    towns = [
        TownReference(
            geocode = record['town_geocode'],
            name = record['town'],
            county_fips = record['county_fips'],
            town_type = TownType(record['geotype']),
            aliases = [
                TownName(record['maine_gis_name'], 'variant', 'Maine Geolibrary'),
                TownName(record['voting_name'], 'voting', 'Secretary of State'),
                TownName(record['tribal_name'], 'tribal'),
                TownName(record['gnis_name'], 'variant', 'Geographic Names Information System'),
                [
                    TownName(name, 'historical', 'Geographic Names Information System')
                    for name in record['gnis_variants'][1:-1].split(',')
                ],
                [
                    TownName(name, 'historical', 'Maine State Auditor')
                    for name in record['historical_names'][1:-1].split(',')
                ],
                [
                    TownName(name, 'island', 'Maine Revenue Services')
                    for name in record['islands'][1:-1].split(',')
                ],
            ],
            cousub_geocode = record['cousub_geocode'],
            cousub_name = record['cousub_name'],
            cousub_basename = record['cousub_basename'],
            cousub_class = record['class'],
            gnis_feature_id = record['gnis_id']
        ) for record in townships
    ]
    
    # Create and process database
    town_db = TownDatabase(towns)
    
    # Convert to serializable format
    data = {
        'towns': {
            town.name: {
                'geocode': town.geocode,
                'gnis_id': town.gnis_feature_id,
                'county': {
                    'fips': town.county_fips,
                    'name': town.county_name,
                    'sos_name': town.county_sos_name
                },
                'cousub' : {
                    'geocode': town.cousub_geocode,
                    'name': town.cousub_name,
                    'basename': town.cousub_basename,
                    'class': town.cousub_class
                },
                'aliases': town.aliases,
                'aliases': [
                    {
                        alias.name: {
                            'name_type': alias.name_type,
                            'source': alias.source
                        }
                    }
                    for alias in town.aliases
                ],
            } for town in town_db.data
        }
    }
    
    # Ensure output directory exists
    output_dir = Path(__file__).parent / "data"
    output_dir.mkdir(exist_ok=True)
    
    # Save to YAML
    with open(output_dir / 'townships_detailed.yaml', 'w') as f:
        yaml.dump(data, f, sort_keys=False)

if __name__ == "__main__":
    build_town_database()