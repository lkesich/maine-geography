"""Place name matching.
"""

__docformat__ = 'google'

__all__ = [
    # Functions
    
    # Classes
]

from dataclasses import dataclass
from typing import List
from itertools import permutations
import re
from mainegeo import lookups, townships

TOWNSHIPS = lookups.TownshipLookup().data

tribal_districts = {
    '19630': 'PENOBSCOT NATION VOTING DISTRICT',
    '29480': 'PLEASANT POINT VOTING DISTRICT'
}

former_names = {
    '25866': 'RAYTOWN TWP',
    '25861': 'SPRING LAKE TWP',
    '03897': 'T17 R3 WELS'
}

@dataclass
class TownRecord:
    geocode: str
    name: str
    county: str
    aliases: List[str]

    def __post_init__(self):
       self._generate_aliases()

    def _generate_aliases(self) -> List[str]:
        aliases = self.aliases
        aliases.append(self.name.upper())
        aliases.append(former_names.get(self.geocode))
        aliases.append(tribal_districts.get(self.geocode))

        aliases = list(filter(None, aliases))
        
        aliases.extend(self._generate_variants(self.name.upper(), ['ST. ', 'SAINT ', 'ST ']))
        aliases.extend(self._generate_variants(self.name.upper(), [' AND ', ' & ']))

        aliases.extend(list(map(townships.strip_suffix, aliases)))
        aliases.extend(list(map(townships.normalize_suffix, aliases)))
        aliases.extend(list(map(townships.strip_region, aliases)))
        aliases.extend(list(map(townships.strip_region, aliases))) # 2x

        aliases = map(str.upper, aliases)
        self.aliases = list(set(aliases))

    def _generate_variants(self, base: str, patterns: List[str]) -> List[str]:
        if not any(pattern in base for pattern in patterns):
            return []
        else:
            comb = list(permutations(patterns, 2))
            find, replace = zip(*comb)
            find = map(lambda f: r'\b' + re.escape(f) + r'\b', find)
            variants = map(lambda f, r: re.sub(f, r, base), find, replace)
            return list(set(variants))

reference_data = [
    TownRecord(
        geocode = record['town_geocode'],
        name = record['town'],
        county = record['sos_county'],
        aliases = [
            record['gnis_name'], 
            record['maine_gis_name'],
            record['historical_name']
        ]
    ) for record in TOWNSHIPS
]


all_aliases = [a for al in [town.aliases for town in reference_data] for a in al]
unique_aliases = [a for a in all_aliases if all_aliases.count(a) == 1]

for town in reference_data:
    town.aliases = [a for a in town.aliases if a in unique_aliases or a==town.name.upper()]

reference_data