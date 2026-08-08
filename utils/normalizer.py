"""
Team name normalization system for College Football Market Edge Platform.
Handles mapping between different API formats and user inputs for 130+ FBS teams.
"""

import logging
import re
from typing import Dict, List, Optional, Set
from difflib import get_close_matches

from data.team_registry import CANONICAL_OVERRIDES, get_fbs_canonical_names, get_fcs_names

logger = logging.getLogger(__name__)


class TeamNameNormalizer:
    """
    Normalizes team names across different data sources and user inputs.
    
    Handles conversions between:
    - User input (uga, bama, ut, etc.)
    - Internal normalized format (GEORGIA)
    - ESPN API format (Georgia Bulldogs)
    - The Odds API format (Georgia)
    """
    
    def __init__(self):
        """Initialize normalizer with comprehensive team mappings."""
        # Internal normalized name (uppercase, primary name)
        self.team_mappings = self._build_team_mappings()
        
        # ESPN API format mappings (full team names)
        self.espn_mappings = self._build_espn_mappings()
        
        # The Odds API format mappings (shorter format)
        self.odds_mappings = self._build_odds_mappings()
        
        # Common aliases and abbreviations
        self.alias_mappings = self._build_alias_mappings()
        
        # All possible names for quick lookup
        self._all_names = self._build_all_names_index()
        
        # FCS teams to filter out
        self.fcs_teams = self._build_fcs_teams()
    
    def normalize(self, team_name: str) -> Optional[str]:
        """
        Normalize any team name input to internal format.
        
        Args:
            team_name: Team name in any format
            
        Returns:
            str: Normalized team name (uppercase) or None if not found
        """
        if not team_name:
            return None
            
        # Clean input
        clean_name = self._clean_input(team_name)
        
        # Direct lookup in aliases
        if clean_name in self.alias_mappings:
            return self.alias_mappings[clean_name]
        
        # Check if already normalized
        if clean_name in self.team_mappings:
            return clean_name
        
        # Try removing common mascot suffixes and check again
        cleaned_name = self._remove_mascot_suffix(clean_name)
        if cleaned_name != clean_name and cleaned_name in self.alias_mappings:
            return self.alias_mappings[cleaned_name]
        if cleaned_name in self.team_mappings:
            return cleaned_name
        
        # Try fuzzy matching
        result = self._fuzzy_match(clean_name)
        if result:
            return result
            
        # Try fuzzy matching on cleaned name
        return self._fuzzy_match(cleaned_name)
    
    def to_espn_format(self, normalized_name: str) -> Optional[str]:
        """Convert normalized name to ESPN API format."""
        return self.espn_mappings.get(normalized_name)
    
    def to_odds_format(self, normalized_name: str) -> Optional[str]:
        """Convert normalized name to Odds API format."""
        return self.odds_mappings.get(normalized_name)
    
    def get_all_aliases(self, normalized_name: str) -> List[str]:
        """Get all known aliases for a normalized team name."""
        aliases = [normalized_name]
        
        # Add ESPN and Odds formats
        espn_name = self.to_espn_format(normalized_name)
        if espn_name:
            aliases.append(espn_name)
            
        odds_name = self.to_odds_format(normalized_name)
        if odds_name:
            aliases.append(odds_name)
        
        # Add reverse lookup aliases
        for alias, norm_name in self.alias_mappings.items():
            if norm_name == normalized_name:
                aliases.append(alias)
        
        return list(set(aliases))
    
    def validate_team(self, team_name: str) -> bool:
        """Check if team name can be normalized."""
        return self.normalize(team_name) is not None
    
    def get_all_teams(self) -> List[str]:
        """Get list of all normalized team names."""
        return list(self.team_mappings.keys())
    
    def _clean_input(self, name: str) -> str:
        """Clean and standardize input string."""
        # Remove extra whitespace and convert to uppercase
        clean = re.sub(r'\s+', ' ', name.strip().upper())
        
        # Remove common prefixes/suffixes that don't help identification
        # Note: Don't remove 'COLLEGE' as it's part of 'BOSTON COLLEGE'
        patterns_to_remove = [
            r'\bUNIVERSITY OF\b',
            r'\bFOOTBALL\b',
            r'\bUNIVERSITY\b',
            r'\bSTATE UNIVERSITY\b',
        ]
        
        for pattern in patterns_to_remove:
            clean = re.sub(pattern, '', clean, flags=re.IGNORECASE)
        
        # Clean up any resulting double spaces
        clean = re.sub(r'\s+', ' ', clean).strip()
        
        return clean
    
    def _remove_mascot_suffix(self, name: str) -> str:
        """Remove common mascot suffixes to help with team identification."""
        # Common mascot names to remove
        mascots = [
            'CRIMSON TIDE', 'RAZORBACKS', 'TIGERS', 'GATORS', 'BULLDOGS', 'WILDCATS',
            'REBELS', 'GAMECOCKS', 'VOLUNTEERS', 'LONGHORNS', 'AGGIES', 'COMMODORES',
            'SOONERS', 'FIGHTING ILLINI', 'HOOSIERS', 'HAWKEYES', 'TERRAPINS',
            'WOLVERINES', 'SPARTANS', 'GOLDEN GOPHERS', 'CORNHUSKERS', 'BUCKEYES',
            'NITTANY LIONS', 'BOILERMAKERS', 'SCARLET KNIGHTS', 'BADGERS', 'DUCKS',
            'HUSKIES', 'BRUINS', 'TROJANS', 'BEARS', 'CYCLONES', 'JAYHAWKS',
            'COWBOYS', 'HORNED FROGS', 'RED RAIDERS', 'MOUNTAINEERS', 'BEARCATS',
            'COUGARS', 'KNIGHTS', 'BUFFALOES', 'UTES', 'SUN DEVILS', 'EAGLES',
            'BLUE DEVILS', 'SEMINOLES', 'YELLOW JACKETS', 'CARDINALS', 'HURRICANES',
            'WOLFPACK', 'TAR HEELS', 'PANTHERS', 'ORANGE', 'CAVALIERS', 'HOKIES',
            'DEMON DEACONS', 'FIGHTING IRISH', 'GOLDEN BEARS', 'CARDINAL', 'MUSTANGS',
            'BEAVERS', 'BRONCOS', 'AZTECS', 'FALCONS', 'MIDSHIPMEN', 'BLACK KNIGHTS',
            'FLAMES', 'CHANTICLEERS', 'DUKES', 'THUNDERING HERD', 'HILLTOPPERS',
            'GREEN WAVE', 'BULLS', 'PIRATES', 'REDHAWKS', 'ROCKETS', 'CHIPPEWAS',
            'GOLDEN FLASHES', 'ZIPS', 'BOBCATS'
        ]
        
        # Remove mascot suffixes
        for mascot in mascots:
            if name.endswith(f' {mascot}'):
                return name[:-len(f' {mascot}')].strip()
        
        return name
    
    def _fuzzy_match(self, clean_name: str) -> Optional[str]:
        """Near-miss matching that CANNOT cross into the FBS universe.

        **Why this fails closed.** `difflib` at cutoff 0.8 does not distinguish "a typo of an FBS
        team" from "a different school whose name happens to be similar". Measured against the real
        CFBD feed, 16 FCS programs resolved onto FBS teams — Samford→STANFORD, Southern→USC,
        Mississippi Valley State→MISSISSIPPI STATE, North Carolina A&T→NORTH CAROLINA. When both
        sides of an FCS game resolved, a **fabricated FBS game entered the snapshot**, including
        NORTH DAKOTA STATE playing itself. Ten such games were already in the tag-time vehicle.

        A fabricated game is a violation of the no-fabricated-data principle with real downstream
        cost: `data["games"]` drives schedule intelligence, and in-season it would attribute a
        completed FCS result to an FBS team's Elo.

        So membership in the tracked universe is now decided **only** by the authoritative routes —
        exact canonical, explicit alias, or a `CANONICAL_OVERRIDES` entry. Fuzzy matching may still
        resolve *within* the non-FBS vocabulary, but a fuzzy result that lands on an FBS canonical
        is refused. An unresolved name returns ``None`` and is recorded with a reason by the slate
        reconciler (SPEC §5.5.3) — visible, and fixable by adding an alias, rather than silently
        becoming the wrong team.

        This is D7's own doctrine applied at runtime: that entry already forbids a CFBD team
        resolving "by implicit fuzzy match rather than one of these three explicit routes".

        **Accepted cost, stated rather than left implicit:** this also stops fuzzy typo-correction
        of tracked teams themselves — `"Ohio Statee"` now returns ``None`` instead of
        ``"OHIO STATE"``, so a mistyped name in `cfb hypothetical` no longer self-corrects. That is
        the right trade: the same mechanism that forgives a human typo is the one that turned
        Samford into Stanford in an authoritative data feed, and a wrong-but-confident resolution
        is far more expensive than a rejected one. Add an explicit alias if a spelling deserves to
        resolve.
        """
        matches = get_close_matches(clean_name, self._all_names, n=1, cutoff=0.8)
        if not matches:
            return None

        resolved = self.alias_mappings.get(matches[0], matches[0])
        # Compare case-insensitively. `_all_names` also holds the mixed-case ESPN/Odds display
        # forms ("Michigan", "Texas"), whose uppercase IS an FBS canonical but which are not
        # literally keys of `team_mappings` — a route by which a fuzzy hit could confer FBS
        # membership without tripping the guard. No live bypass was found, but this guard is
        # supposed to hold by construction rather than by luck.
        if resolved.upper() in self.team_mappings:
            logger.debug(
                "Refusing fuzzy match %r -> %r: fuzzy matching may not confer FBS membership "
                "(add an explicit alias if this mapping is genuinely correct).",
                clean_name, resolved,
            )
            return None
        return resolved
    
    def _build_all_names_index(self) -> Set[str]:
        """Build index of all possible team names for fuzzy matching."""
        all_names = set()
        
        # Add all team mappings
        all_names.update(self.team_mappings.keys())
        
        # Add all aliases
        all_names.update(self.alias_mappings.keys())
        
        # Add ESPN formats
        all_names.update(self.espn_mappings.values())
        
        # Add Odds formats
        all_names.update(self.odds_mappings.values())
        
        return all_names
    
    def _build_team_mappings(self) -> Dict[str, str]:
        """Core canonical FBS names (normalized name -> itself).

        Sourced from the season team registry (SPEC §5.5), which is built from CFBD
        `/teams?year=YYYY` — no longer a hardcoded list. Canonical names are the
        registry's UPPERCASE form; CFBD's per-source spellings resolve to them via
        the alias mappings below.
        """
        return {team: team for team in get_fbs_canonical_names()}
    
    def _build_espn_mappings(self) -> Dict[str, str]:
        """Build ESPN API format mappings."""
        return {
            # SEC
            'ALABAMA': 'Alabama Crimson Tide',
            'ARKANSAS': 'Arkansas Razorbacks',
            'AUBURN': 'Auburn Tigers',
            'FLORIDA': 'Florida Gators',
            'GEORGIA': 'Georgia Bulldogs',
            'KENTUCKY': 'Kentucky Wildcats',
            'LSU': 'LSU Tigers',
            'MISSISSIPPI': 'Ole Miss Rebels',
            'MISSISSIPPI STATE': 'Mississippi State Bulldogs',
            'MISSOURI': 'Missouri Tigers',
            'SOUTH CAROLINA': 'South Carolina Gamecocks',
            'TENNESSEE': 'Tennessee Volunteers',
            'TEXAS': 'Texas Longhorns',
            'TEXAS A&M': 'Texas A&M Aggies',
            'VANDERBILT': 'Vanderbilt Commodores',
            'OKLAHOMA': 'Oklahoma Sooners',
            
            # BIG TEN
            'ILLINOIS': 'Illinois Fighting Illini',
            'INDIANA': 'Indiana Hoosiers',
            'IOWA': 'Iowa Hawkeyes',
            'MARYLAND': 'Maryland Terrapins',
            'MICHIGAN': 'Michigan Wolverines',
            'MICHIGAN STATE': 'Michigan State Spartans',
            'MINNESOTA': 'Minnesota Golden Gophers',
            'NEBRASKA': 'Nebraska Cornhuskers',
            'NORTHWESTERN': 'Northwestern Wildcats',
            'OHIO STATE': 'Ohio State Buckeyes',
            'PENN STATE': 'Penn State Nittany Lions',
            'PURDUE': 'Purdue Boilermakers',
            'RUTGERS': 'Rutgers Scarlet Knights',
            'WISCONSIN': 'Wisconsin Badgers',
            'OREGON': 'Oregon Ducks',
            'WASHINGTON': 'Washington Huskies',
            'UCLA': 'UCLA Bruins',
            'USC': 'USC Trojans',
            
            # BIG 12
            'BAYLOR': 'Baylor Bears',
            'IOWA STATE': 'Iowa State Cyclones',
            'KANSAS': 'Kansas Jayhawks',
            'KANSAS STATE': 'Kansas State Wildcats',
            'OKLAHOMA STATE': 'Oklahoma State Cowboys',
            'TCU': 'TCU Horned Frogs',
            'TEXAS TECH': 'Texas Tech Red Raiders',
            'WEST VIRGINIA': 'West Virginia Mountaineers',
            'CINCINNATI': 'Cincinnati Bearcats',
            'HOUSTON': 'Houston Cougars',
            'UCF': 'UCF Knights',
            'BYU': 'BYU Cougars',
            'COLORADO': 'Colorado Buffaloes',
            'UTAH': 'Utah Utes',
            'ARIZONA': 'Arizona Wildcats',
            'ARIZONA STATE': 'Arizona State Sun Devils',
            
            # ACC
            'BOSTON COLLEGE': 'Boston College Eagles',
            'CLEMSON': 'Clemson Tigers',
            'DUKE': 'Duke Blue Devils',
            'FLORIDA STATE': 'Florida State Seminoles',
            'GEORGIA TECH': 'Georgia Tech Yellow Jackets',
            'LOUISVILLE': 'Louisville Cardinals',
            'MIAMI': 'Miami Hurricanes',
            'NC STATE': 'NC State Wolfpack',
            'NORTH CAROLINA': 'North Carolina Tar Heels',
            'PITTSBURGH': 'Pittsburgh Panthers',
            'SYRACUSE': 'Syracuse Orange',
            'VIRGINIA': 'Virginia Cavaliers',
            'VIRGINIA TECH': 'Virginia Tech Hokies',
            'WAKE FOREST': 'Wake Forest Demon Deacons',
            'NOTRE DAME': 'Notre Dame Fighting Irish',
            'CAL': 'California Golden Bears',
            'STANFORD': 'Stanford Cardinal',
            'SMU': 'SMU Mustangs',
            
            # Add more as needed...
        }
    
    def _build_odds_mappings(self) -> Dict[str, str]:
        """Build Odds API format mappings."""
        return {
            # SEC
            'ALABAMA': 'Alabama',
            'ARKANSAS': 'Arkansas',
            'AUBURN': 'Auburn',
            'FLORIDA': 'Florida',
            'GEORGIA': 'Georgia',
            'KENTUCKY': 'Kentucky',
            'LSU': 'LSU',
            'MISSISSIPPI': 'Ole Miss',
            'MISSISSIPPI STATE': 'Mississippi State',
            'MISSOURI': 'Missouri',
            'SOUTH CAROLINA': 'South Carolina',
            'TENNESSEE': 'Tennessee',
            'TEXAS': 'Texas',
            'TEXAS A&M': 'Texas A&M',
            'VANDERBILT': 'Vanderbilt',
            'OKLAHOMA': 'Oklahoma',
            
            # BIG TEN
            'ILLINOIS': 'Illinois',
            'INDIANA': 'Indiana',
            'IOWA': 'Iowa',
            'MARYLAND': 'Maryland',
            'MICHIGAN': 'Michigan',
            'MICHIGAN STATE': 'Michigan State',
            'MINNESOTA': 'Minnesota',
            'NEBRASKA': 'Nebraska',
            'NORTHWESTERN': 'Northwestern',
            'OHIO STATE': 'Ohio State',
            'PENN STATE': 'Penn State',
            'PURDUE': 'Purdue',
            'RUTGERS': 'Rutgers',
            'WISCONSIN': 'Wisconsin',
            'OREGON': 'Oregon',
            'WASHINGTON': 'Washington',
            'UCLA': 'UCLA',
            'USC': 'USC',
            
            # Add more as needed...
        }
    
    def _build_alias_mappings(self) -> Dict[str, str]:
        """Build comprehensive alias mappings to normalized names."""
        aliases = {}
        
        # Common abbreviations and nicknames
        common_aliases = {
            # SEC
            'BAMA': 'ALABAMA',
            'ALA': 'ALABAMA',
            'ARK': 'ARKANSAS',
            'UGA': 'GEORGIA',
            'UF': 'FLORIDA',
            'UK': 'KENTUCKY',
            'OLE MISS': 'MISSISSIPPI',
            'MISS STATE': 'MISSISSIPPI STATE',
            'MIZZOU': 'MISSOURI',
            'SCAR': 'SOUTH CAROLINA',
            'UT': 'TENNESSEE',  # Note: conflicts with Texas/Utah
            'VOLS': 'TENNESSEE',
            'A&M': 'TEXAS A&M',
            'TAMU': 'TEXAS A&M',
            'VANDY': 'VANDERBILT',
            'OU': 'OKLAHOMA',
            
            # BIG TEN  
            'ILL': 'ILLINOIS',
            'IU': 'INDIANA',
            'UM': 'MICHIGAN',
            'MSU': 'MICHIGAN STATE',  # Most common usage for MSU
            'UMN': 'MINNESOTA',
            'NU': 'NORTHWESTERN',
            'PSU': 'PENN STATE',
            'UW': 'WISCONSIN',
            'UO': 'OREGON',
            'UDub': 'WASHINGTON',
            
            # BIG 12
            'ISU': 'IOWA STATE',
            'KU': 'KANSAS',
            'KSU': 'KANSAS STATE',  # Note: conflicts
            'OKST': 'OKLAHOMA STATE',
            'OSU': 'OHIO STATE',  # Most common usage, Oklahoma State uses OKST
            'TTU': 'TEXAS TECH',
            'WVU': 'WEST VIRGINIA',
            'UC': 'CINCINNATI',
            'UH': 'HOUSTON',
            'CU': 'COLORADO',
            'ASU': 'ARIZONA STATE',
            'UA': 'ARIZONA',
            
            # ACC
            'BC': 'BOSTON COLLEGE',
            'FSU': 'FLORIDA STATE',
            'GT': 'GEORGIA TECH',
            'UL': 'LOUISVILLE',
            'THE U': 'MIAMI',
            'NCSU': 'NC STATE',
            'UNC': 'NORTH CAROLINA',
            'PITT': 'PITTSBURGH',
            'CUSE': 'SYRACUSE',
            'UVA': 'VIRGINIA',
            'VT': 'VIRGINIA TECH',
            'VPI': 'VIRGINIA TECH',
            'WAKE': 'WAKE FOREST',
            'ND': 'NOTRE DAME',
            
            # Additional common formats
            'SOUTHERN CAL': 'USC',
            'SO CAL': 'USC',
            'SOUTH CAROLINA': 'SOUTH CAROLINA',
            'TEXAS': 'TEXAS',
            'LONGHORNS': 'TEXAS',
            'AGGIES': 'TEXAS A&M',
            'BULLDOGS': 'GEORGIA',  # Most common association
            'TIGERS': 'LSU',  # Most common association
            
        }
        
        aliases.update(common_aliases)
        
        # Add comprehensive full team names with mascots (for Odds API)
        full_team_names = {
            # SEC
            'ALABAMA CRIMSON TIDE': 'ALABAMA',
            'ARKANSAS RAZORBACKS': 'ARKANSAS',
            'AUBURN TIGERS': 'AUBURN',
            'FLORIDA GATORS': 'FLORIDA',
            'GEORGIA BULLDOGS': 'GEORGIA',
            'KENTUCKY WILDCATS': 'KENTUCKY',
            'LSU TIGERS': 'LSU',
            'OLE MISS REBELS': 'MISSISSIPPI',
            'MISSISSIPPI STATE BULLDOGS': 'MISSISSIPPI STATE',
            'MISSOURI TIGERS': 'MISSOURI',
            'SOUTH CAROLINA GAMECOCKS': 'SOUTH CAROLINA',
            'TENNESSEE VOLUNTEERS': 'TENNESSEE',
            'TEXAS LONGHORNS': 'TEXAS',
            'TEXAS A&M AGGIES': 'TEXAS A&M',
            'VANDERBILT COMMODORES': 'VANDERBILT',
            'OKLAHOMA SOONERS': 'OKLAHOMA',
            
            # BIG TEN
            'ILLINOIS FIGHTING ILLINI': 'ILLINOIS',
            'INDIANA HOOSIERS': 'INDIANA',
            'IOWA HAWKEYES': 'IOWA',
            'MARYLAND TERRAPINS': 'MARYLAND',
            'MICHIGAN WOLVERINES': 'MICHIGAN',
            'MICHIGAN STATE SPARTANS': 'MICHIGAN STATE',
            'MINNESOTA GOLDEN GOPHERS': 'MINNESOTA',
            'NEBRASKA CORNHUSKERS': 'NEBRASKA',
            'NORTHWESTERN WILDCATS': 'NORTHWESTERN',
            'OHIO STATE BUCKEYES': 'OHIO STATE',
            'PENN STATE NITTANY LIONS': 'PENN STATE',
            'PURDUE BOILERMAKERS': 'PURDUE',
            'RUTGERS SCARLET KNIGHTS': 'RUTGERS',
            'WISCONSIN BADGERS': 'WISCONSIN',
            'OREGON DUCKS': 'OREGON',
            'WASHINGTON HUSKIES': 'WASHINGTON',
            'UCLA BRUINS': 'UCLA',
            'USC TROJANS': 'USC',
            
            # BIG 12
            'BAYLOR BEARS': 'BAYLOR',
            'IOWA STATE CYCLONES': 'IOWA STATE',
            'KANSAS JAYHAWKS': 'KANSAS',
            'KANSAS STATE WILDCATS': 'KANSAS STATE',
            'OKLAHOMA STATE COWBOYS': 'OKLAHOMA STATE',
            'TCU HORNED FROGS': 'TCU',
            'TEXAS TECH RED RAIDERS': 'TEXAS TECH',
            'WEST VIRGINIA MOUNTAINEERS': 'WEST VIRGINIA',
            'CINCINNATI BEARCATS': 'CINCINNATI',
            'HOUSTON COUGARS': 'HOUSTON',
            'UCF KNIGHTS': 'UCF',
            'BYU COUGARS': 'BYU',
            'COLORADO BUFFALOES': 'COLORADO',
            'UTAH UTES': 'UTAH',
            'ARIZONA WILDCATS': 'ARIZONA',
            'ARIZONA STATE SUN DEVILS': 'ARIZONA STATE',
            
            # ACC
            'BOSTON COLLEGE EAGLES': 'BOSTON COLLEGE',
            'BOSTON COLLEGE': 'BOSTON COLLEGE',  # Direct mapping for base name
            'CLEMSON TIGERS': 'CLEMSON',
            'DUKE BLUE DEVILS': 'DUKE',
            'FLORIDA STATE SEMINOLES': 'FLORIDA STATE',
            'GEORGIA TECH YELLOW JACKETS': 'GEORGIA TECH',
            'LOUISVILLE CARDINALS': 'LOUISVILLE',
            'MIAMI HURRICANES': 'MIAMI',
            'NC STATE WOLFPACK': 'NC STATE',
            'NORTH CAROLINA TAR HEELS': 'NORTH CAROLINA',
            'PITTSBURGH PANTHERS': 'PITTSBURGH',
            'SYRACUSE ORANGE': 'SYRACUSE',
            'VIRGINIA CAVALIERS': 'VIRGINIA',
            'VIRGINIA TECH HOKIES': 'VIRGINIA TECH',
            'WAKE FOREST DEMON DEACONS': 'WAKE FOREST',
            'NOTRE DAME FIGHTING IRISH': 'NOTRE DAME',
            'CALIFORNIA GOLDEN BEARS': 'CAL',
            'STANFORD CARDINAL': 'STANFORD',
            'SMU MUSTANGS': 'SMU',
            
            # PAC-12 (remaining)
            'WASHINGTON STATE COUGARS': 'WASHINGTON STATE',
            'OREGON STATE BEAVERS': 'OREGON STATE',
            
            # Group of 5 teams that commonly appear in betting
            'BOISE STATE BRONCOS': 'BOISE STATE',
            'FRESNO STATE BULLDOGS': 'FRESNO STATE',
            'SAN DIEGO STATE AZTECS': 'SAN DIEGO STATE',
            'AIR FORCE FALCONS': 'AIR FORCE',
            'NAVY MIDSHIPMEN': 'NAVY',
            'ARMY BLACK KNIGHTS': 'ARMY',
            'LIBERTY FLAMES': 'LIBERTY',
            'APPALACHIAN STATE MOUNTAINEERS': 'APPALACHIAN STATE',
            'COASTAL CAROLINA CHANTICLEERS': 'COASTAL CAROLINA',
            'JAMES MADISON DUKES': 'JAMES MADISON',
            'MARSHALL THUNDERING HERD': 'MARSHALL',
            'WESTERN KENTUCKY HILLTOPPERS': 'WESTERN KENTUCKY',
            'MEMPHIS TIGERS': 'MEMPHIS',
            'TULANE GREEN WAVE': 'TULANE',
            'SOUTH FLORIDA BULLS': 'SOUTH FLORIDA',
            'EAST CAROLINA PIRATES': 'EAST CAROLINA',
            'NORTHERN ILLINOIS HUSKIES': 'NORTHERN ILLINOIS',
            'BALL STATE CARDINALS': 'BALL STATE',
            'TOLEDO ROCKETS': 'TOLEDO',
            'MIAMI (OH) REDHAWKS': 'MIAMI (OH)',
            'BOWLING GREEN FALCONS': 'BOWLING GREEN',
            'WESTERN MICHIGAN BRONCOS': 'WESTERN MICHIGAN',
            'CENTRAL MICHIGAN CHIPPEWAS': 'CENTRAL MICHIGAN',
            'EASTERN MICHIGAN EAGLES': 'EASTERN MICHIGAN',
            'KENT STATE GOLDEN FLASHES': 'KENT STATE',
            'AKRON ZIPS': 'AKRON',
            'BUFFALO BULLS': 'BUFFALO',
            'OHIO BOBCATS': 'OHIO',
            
            # Common variations without full mascot names
            'ALABAMA CRIMSON': 'ALABAMA',
            'GEORGIA DOGS': 'GEORGIA',
            'FLORIDA GATOR': 'FLORIDA',
            'TENNESSEE VOLS': 'TENNESSEE',
            'KENTUCKY CATS': 'KENTUCKY',
            'SOUTH CAROLINA COCKS': 'SOUTH CAROLINA',
            'TEXAS HORNS': 'TEXAS',
            'OHIO STATE BUCKS': 'OHIO STATE',
            'MICHIGAN WOLVES': 'MICHIGAN',
            'PENN STATE LIONS': 'PENN STATE',
            'WISCONSIN BADGER': 'WISCONSIN',
            'NOTRE DAME IRISH': 'NOTRE DAME',
            'FLORIDA STATE NOLES': 'FLORIDA STATE',
            'CLEMSON TIGER': 'CLEMSON',
            'MIAMI CANES': 'MIAMI',
            'VIRGINIA TECH HOKIE': 'VIRGINIA TECH',
            'NEBRASKA HUSKERS': 'NEBRASKA',
            
            # Additional teams and variations that commonly appear in betting
            'HAWAII RAINBOW WARRIORS': 'HAWAII',
            'SAM HOUSTON STATE BEARKATS': 'SAM HOUSTON',
            'SAM HOUSTON BEARKATS': 'SAM HOUSTON',
            'CHARLOTTE 49ERS': 'CHARLOTTE',
            'KENNESAW STATE OWLS': 'KENNESAW STATE',
            'UNLV REBELS': 'UNLV',
            'FLORIDA ATLANTIC OWLS': 'FAU',
            'SOUTHERN MISSISSIPPI GOLDEN EAGLES': 'SOUTHERN MISS',
            'SOUTHERN MISS GOLDEN EAGLES': 'SOUTHERN MISS',
            'OLD DOMINION MONARCHS': 'OLD DOMINION',
            'LOUISIANA RAGIN CAJUNS': 'LOUISIANA',
            'RICE OWLS': 'RICE',
            'NEW MEXICO LOBOS': 'NEW MEXICO',
            'NEVADA WOLF PACK': 'NEVADA',
            'UMASS MINUTEMEN': 'UMASS',
            'TEMPLE OWLS': 'TEMPLE',
            'UTSA ROADRUNNERS': 'UTSA',
            'UTEP MINERS': 'UTEP',
            'UTAH STATE AGGIES': 'UTAH STATE',
            'FLORIDA ATLANTIC': 'FAU',
            'SOUTHERN MISSISSIPPI': 'SOUTHERN MISS'
        }
        
        aliases.update(full_team_names)
        
        # Add state abbreviations where unambiguous
        state_mappings = {
            'AL': 'ALABAMA',
            'FL': 'FLORIDA',
            'GA': 'GEORGIA',
            'LA': 'LSU',
            'MS': 'MISSISSIPPI',
            'SC': 'SOUTH CAROLINA',
            'TN': 'TENNESSEE',
            'TX': 'TEXAS',
            'OK': 'OKLAHOMA',
        }
        
        aliases.update(state_mappings)

        # CFBD's own spellings, from the registry's single source of truth.
        #
        # `CANONICAL_OVERRIDES` records where CFBD's `school` field diverges from our canonical
        # name (D7). It was applied only when the registry artifact was BUILT, never at runtime —
        # so `normalize("California")` returned None and every Cal game was dropped, along with
        # "App State", "UL Monroe", "Massachusetts", "Ole Miss", "Hawai'i", "San José State" and
        # "Florida Atlantic". Ten real tracked-vs-tracked games were lost to this alone.
        #
        # Wiring it here rather than re-typing the pairs keeps one source of truth: a future
        # override is picked up by the registry build and by name resolution from the same edit.
        for cfbd_spelling, canonical in CANONICAL_OVERRIDES.items():
            cleaned = self._clean_input(cfbd_spelling)
            if canonical in self.team_mappings:
                aliases[cleaned] = canonical

        # Add identity mappings for all team names
        for team in self.team_mappings.keys():
            if team not in aliases:
                aliases[team] = team

        return aliases
    
    def _build_fcs_teams(self) -> Set[str]:
        """FCS school names to filter out (SPEC §5.5).

        Sourced from the season team registry (CFBD `/teams` rows with
        `classification == "fcs"`), not a hardcoded list. School names are the
        UPPERCASE match key `is_fcs_team` checks after `_clean_input`.
        """
        return set(get_fcs_names())
    
    def is_fcs_team(self, team_name: str) -> bool:
        """
        Check if a team is an FCS team.
        
        Args:
            team_name: Team name in any format
            
        Returns:
            bool: True if team is FCS, False otherwise
        """
        if not team_name:
            return False
        
        # Clean the input
        clean_name = self._clean_input(team_name)
        
        # Check if it's in our FCS list
        if clean_name in self.fcs_teams:
            return True
        
        # Check partial matches for common FCS identifiers
        fcs_keywords = ['STATE', 'NORTHERN', 'SOUTHERN', 'EASTERN', 'WESTERN', 
                       'CENTRAL', 'A&M', 'A&T', 'TECH', 'VALLEY']
        
        # Only check keywords if the team is NOT in our FBS mappings
        if clean_name not in self.team_mappings and clean_name not in self.alias_mappings:
            for keyword in fcs_keywords:
                if keyword in clean_name and clean_name in self.fcs_teams:
                    return True
        
        return False
    
    def is_fbs_vs_fcs_matchup(self, home_team: str, away_team: str) -> bool:
        """
        Check if a matchup involves at least one FCS team.
        
        Args:
            home_team: Home team name
            away_team: Away team name
            
        Returns:
            bool: True if at least one team is FCS
        """
        return self.is_fcs_team(home_team) or self.is_fcs_team(away_team)


# Global normalizer instance
normalizer = TeamNameNormalizer()