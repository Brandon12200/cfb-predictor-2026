"""
Team name normalization system for College Football Market Edge Platform.
Handles mapping between different API formats and user inputs for 130+ FBS teams.
"""

import re
from typing import Dict, List, Optional, Set
from difflib import get_close_matches


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
        """Attempt fuzzy matching for near-misses."""
        # Get close matches from all known names
        matches = get_close_matches(
            clean_name, 
            self._all_names, 
            n=1, 
            cutoff=0.8
        )
        
        if matches:
            matched_name = matches[0]
            # Return the normalized form
            return self.alias_mappings.get(matched_name, matched_name)
        
        return None
    
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
        """Build core team mappings (normalized name -> normalized name)."""
        teams = [
            # SEC
            'ALABAMA', 'ARKANSAS', 'AUBURN', 'FLORIDA', 'GEORGIA', 'KENTUCKY',
            'LSU', 'MISSISSIPPI', 'MISSISSIPPI STATE', 'MISSOURI', 'SOUTH CAROLINA',
            'TENNESSEE', 'TEXAS', 'TEXAS A&M', 'VANDERBILT', 'OKLAHOMA',
            
            # BIG TEN
            'ILLINOIS', 'INDIANA', 'IOWA', 'MARYLAND', 'MICHIGAN', 'MICHIGAN STATE',
            'MINNESOTA', 'NEBRASKA', 'NORTHWESTERN', 'OHIO STATE', 'PENN STATE',
            'PURDUE', 'RUTGERS', 'WISCONSIN', 'OREGON', 'WASHINGTON', 'UCLA', 'USC',
            
            # BIG 12
            'BAYLOR', 'IOWA STATE', 'KANSAS', 'KANSAS STATE', 'OKLAHOMA STATE',
            'TCU', 'TEXAS TECH', 'WEST VIRGINIA', 'CINCINNATI', 'HOUSTON',
            'UCF', 'BYU', 'COLORADO', 'UTAH', 'ARIZONA', 'ARIZONA STATE',
            
            # ACC
            'BOSTON COLLEGE', 'CLEMSON', 'DUKE', 'FLORIDA STATE', 'GEORGIA TECH',
            'LOUISVILLE', 'MIAMI', 'NC STATE', 'NORTH CAROLINA', 'PITTSBURGH',
            'SYRACUSE', 'VIRGINIA', 'VIRGINIA TECH', 'WAKE FOREST', 'NOTRE DAME',
            'CAL', 'STANFORD', 'SMU',
            
            # PAC-12 (remaining)
            'WASHINGTON STATE', 'OREGON STATE',
            
            # GROUP OF 5 - AAC
            'EAST CAROLINA', 'MEMPHIS', 'NAVY', 'SOUTH FLORIDA', 'TEMPLE',
            'TULANE', 'TULSA', 'FAU', 'NORTH TEXAS', 'RICE', 'UAB', 'UTSA',
            
            # GROUP OF 5 - MOUNTAIN WEST
            'AIR FORCE', 'BOISE STATE', 'COLORADO STATE', 'FRESNO STATE',
            'HAWAII', 'NEVADA', 'NEW MEXICO', 'SAN DIEGO STATE', 'SAN JOSE STATE',
            'UNLV', 'UTAH STATE', 'WYOMING',
            
            # GROUP OF 5 - MAC
            'AKRON', 'BALL STATE', 'BOWLING GREEN', 'BUFFALO', 'CENTRAL MICHIGAN',
            'EASTERN MICHIGAN', 'KENT STATE', 'MIAMI (OH)', 'NORTHERN ILLINOIS',
            'OHIO', 'TOLEDO', 'WESTERN MICHIGAN',
            
            # GROUP OF 5 - SUN BELT
            'APPALACHIAN STATE', 'ARKANSAS STATE', 'COASTAL CAROLINA', 'GEORGIA SOUTHERN',
            'GEORGIA STATE', 'JAMES MADISON', 'LOUISIANA', 'LOUISIANA MONROE',
            'MARSHALL', 'OLD DOMINION', 'SOUTH ALABAMA', 'SOUTHERN MISS',
            'TEXAS STATE', 'TROY',
            
            # GROUP OF 5 - C-USA
            'CHARLOTTE', 'FLORIDA INTERNATIONAL', 'LIBERTY', 'LOUISIANA TECH',
            'MIDDLE TENNESSEE', 'NEW MEXICO STATE', 'SAM HOUSTON', 'UTEP',
            'WESTERN KENTUCKY', 'JACKSONVILLE STATE',
            
            # INDEPENDENTS
            'ARMY', 'UMASS', 'UCONN',
            
            # ADDITIONAL TEAMS COMMONLY IN BETTING
            'KENNESAW STATE', 'SAM HOUSTON'
        ]
        
        return {team: team for team in teams}
    
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
        
        # Add identity mappings for all team names
        for team in self.team_mappings.keys():
            if team not in aliases:
                aliases[team] = team
        
        return aliases
    
    def _build_fcs_teams(self) -> Set[str]:
        """Build set of FCS teams to filter out."""
        fcs_teams = {
            # Common FCS teams that appear in early season matchups
            'KENNESAW STATE', 'KENNESAW', 'KSU OWLS',
            'ELON', 'ELON PHOENIX',
            'WEBER STATE', 'WEBER',
            'MONTANA STATE', 'MONTANA', 'MONTANA GRIZZLIES',
            'NORTH DAKOTA', 'NORTH DAKOTA STATE', 'NDSU',
            'SOUTH DAKOTA', 'SOUTH DAKOTA STATE', 'SDSU',
            'PORTLAND STATE', 'PSU VIKINGS',
            'NORTHERN ARIZONA', 'NAU',
            'IDAHO STATE', 'ISU BENGALS',
            'ILLINOIS STATE', 'ISU REDBIRDS',
            'JAMES MADISON', 'JMU',  # Note: JMU is now FBS but often still in FCS data
            'DELAWARE', 'DELAWARE STATE',
            'VILLANOVA', 'NOVA',
            'RICHMOND', 'RICHMOND SPIDERS',
            'WILLIAM & MARY', 'WILLIAM AND MARY',
            'FURMAN', 'FURMAN PALADINS',
            'SAMFORD', 'SAMFORD BULLDOGS',
            'CHATTANOOGA', 'UTC',
            'CITADEL', 'THE CITADEL',
            'VMI', 'VIRGINIA MILITARY',
            'WOFFORD', 'WOFFORD TERRIERS',
            'MERCER', 'MERCER BEARS',
            'GARDNER-WEBB', 'GARDNER WEBB',
            'PRESBYTERIAN', 'PC',
            'CAMPBELL', 'CAMPBELL FIGHTING CAMELS',
            'STETSON', 'STETSON HATTERS',
            'VALPARAISO', 'VALPO',
            'DAVIDSON', 'DAVIDSON WILDCATS',
            'DRAKE', 'DRAKE BULLDOGS',
            'BUTLER', 'BUTLER BULLDOGS',
            'MOREHEAD STATE', 'MOREHEAD',
            'TENNESSEE STATE', 'TSU',
            'TENNESSEE TECH', 'TTU',
            'EASTERN KENTUCKY', 'EKU',
            'EASTERN ILLINOIS', 'EIU',
            'SOUTHEAST MISSOURI', 'SEMO',
            'SOUTHERN ILLINOIS', 'SIU',
            'NORTHERN IOWA', 'UNI',
            'YOUNGSTOWN STATE', 'YSU',
            'MISSOURI STATE', 'MOSTATE',
            'INDIANA STATE', 'ISU SYCAMORES',
            'WESTERN ILLINOIS', 'WIU',
            'NORTH DAKOTA FIGHTING HAWKS',
            'SOUTH DAKOTA COYOTES',
            'IDAHO VANDALS',  # Idaho dropped to FCS
            'PORTLAND STATE VIKINGS',
            'NORTHERN ARIZONA LUMBERJACKS',
            'ILLINOIS STATE REDBIRDS',
            'WEBER STATE WILDCATS',
            'SOUTHERN UTAH', 'SUU',
            'NORTHERN COLORADO', 'UNC BEARS',
            'SACRAMENTO STATE', 'SAC STATE',
            'CAL POLY', 'CALIFORNIA POLYTECHNIC',
            'UC DAVIS', 'CALIFORNIA DAVIS',
            'EASTERN WASHINGTON', 'EWU',
            'IDAHO', 'IDAHO VANDALS',
            'MONTANA STATE BOBCATS',
            'ALABAMA STATE', 'ASU HORNETS',
            'ALABAMA A&M', 'AAMU',
            'ALCORN STATE', 'ALCORN',
            'BETHUNE-COOKMAN', 'BETHUNE COOKMAN', 'BCU',
            'FLORIDA A&M', 'FAMU',
            'GRAMBLING', 'GRAMBLING STATE',
            'JACKSON STATE', 'JSU TIGERS',
            'MISSISSIPPI VALLEY', 'MVSU',
            'PRAIRIE VIEW', 'PRAIRIE VIEW A&M', 'PVAMU',
            'SOUTHERN', 'SOUTHERN UNIVERSITY', 'SU',
            'TEXAS SOUTHERN', 'TXSO',
            'ARKANSAS-PINE BLUFF', 'UAPB',
            'NORFOLK STATE', 'NSU',
            'NORTH CAROLINA A&T', 'NC A&T', 'NCAT',
            'NORTH CAROLINA CENTRAL', 'NCCU',
            'SOUTH CAROLINA STATE', 'SCSU',
            'DELAWARE STATE', 'DSU',
            'HOWARD', 'HOWARD BISON',
            'MORGAN STATE', 'MSU BEARS',
            'SAVANNAH STATE', 'SSU',
            'MAINE', 'MAINE BLACK BEARS',
            'NEW HAMPSHIRE', 'UNH',
            'RHODE ISLAND', 'URI',
            'STONY BROOK', 'SBU',
            'ALBANY', 'UALBANY',
            'TOWSON', 'TOWSON TIGERS',
            'MONMOUTH', 'MONMOUTH HAWKS',
            'SACRED HEART', 'SHU',
            'WAGNER', 'WAGNER SEAHAWKS',
            'DUQUESNE', 'DUQUESNE DUKES',
            'ROBERT MORRIS', 'RMU',
            'SAINT FRANCIS', 'ST FRANCIS', 'SFU',
            'CENTRAL CONNECTICUT', 'CCSU',
            'LONG ISLAND', 'LIU',
            'BRYANT', 'BRYANT BULLDOGS',
            'COLUMBIA', 'COLUMBIA LIONS',
            'CORNELL', 'CORNELL BIG RED',
            'DARTMOUTH', 'DARTMOUTH BIG GREEN',
            'HARVARD', 'HARVARD CRIMSON',
            'PENN', 'PENNSYLVANIA', 'UPENN',
            'PRINCETON', 'PRINCETON TIGERS',
            'YALE', 'YALE BULLDOGS',
            'BROWN', 'BROWN BEARS',
            'GEORGETOWN', 'GEORGETOWN HOYAS',
            'BUCKNELL', 'BUCKNELL BISON',
            'COLGATE', 'COLGATE RAIDERS',
            'FORDHAM', 'FORDHAM RAMS',
            'HOLY CROSS', 'HC',
            'LAFAYETTE', 'LAFAYETTE LEOPARDS',
            'LEHIGH', 'LEHIGH MOUNTAIN HAWKS',
            'MARIST', 'MARIST RED FOXES',
            'AUSTIN PEAY', 'APSU',
            'MURRAY STATE', 'MSU RACERS',
            'TENNESSEE MARTIN', 'UTM',
            'MCNEESE', 'MCNEESE STATE',
            'NICHOLLS', 'NICHOLLS STATE',
            'NORTHWESTERN STATE', 'NSU DEMONS',
            'SOUTHEASTERN LOUISIANA', 'SELU',
            'HOUSTON BAPTIST', 'HBU',
            'INCARNATE WORD', 'UIW',
            'LAMAR', 'LAMAR CARDINALS',
            'SAM HOUSTON', 'SAM HOUSTON STATE', 'SHSU',
            'STEPHEN F AUSTIN', 'SFA',
            'ABILENE CHRISTIAN', 'ACU',
            'CENTRAL ARKANSAS', 'UCA',
            'TARLETON STATE', 'TARLETON',
            'UTAH TECH', 'DIXIE STATE',
            'SOUTHERN UTAH THUNDERBIRDS',
            'HAMPTON', 'HAMPTON PIRATES',
            'CHARLESTON SOUTHERN', 'CSU BUCCANEERS',
            'COASTAL CAROLINA', 'CCU',  # Now FBS but sometimes in FCS data
            'LIBERTY', 'LIBERTY FLAMES',  # Now FBS but sometimes in FCS data
        }
        
        # Convert all to uppercase for consistent matching
        return {team.upper() for team in fcs_teams}
    
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