__docformat__ = 'google'

__all__ = [
    'Townships'
]

alpha = "A-Za-z"
alnum = alpha + "0-9"
fuzzy = f"[^{alnum},]{{0,3}}"

class Townships:
    """Constants and patterns for township name parsing.
    
    This class provides documentation and organization for township-related
    constants without creating instances. All attributes are class-level.
    
    Attributes:
        `REGIONS` (list): Valid region codes that can appear in township names.
            These are two- to four-letter codes like 'WELS' (West of the 
            Easterly Line of the State) or 'BPP' (Bingham's Penobscot Purchase).

        `REGION_PATTERN` (str): Pattern matching region designators.

        `TOWNSHIP_PATTERN` (str): Pattern matching township designators.
            Townships are designated by:
            - Numbers 1-19 from south to north (e.g., T1, T19)
            - Occasional letter designations (TA, TB, TC, TD, TX)

        `RANGE_PATTERN` (str): Pattern matching range designators.
            Ranges are counted from the easterly line toward the west,
            numbered 1-19 (e.g., R1, R19).
    """
    REGIONS = ['ED','MD','ND','SD','TS','BKP','BPP','EKR','NWP','WKR','NBKP','NBPP','WBKP','WELS']
    REGION_PATTERN = f"(?:{'|'.join(REGIONS)})"
    TOWNSHIP_PATTERN = f"(?:(?<![{alnum}])T[ABCDX](?![{alpha}])|T.?[\\d]{{1,2}})"
    RANGE_PATTERN = f"(?:R.?[\\d]{{1,2}})"