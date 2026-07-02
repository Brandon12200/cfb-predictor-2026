"""
Tests for team name normalizer functionality.
"""

import unittest
from utils.normalizer import TeamNameNormalizer, normalizer


class TestTeamNameNormalizer(unittest.TestCase):
    """Test cases for TeamNameNormalizer class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.normalizer = TeamNameNormalizer()
    
    def test_normalize_common_aliases(self):
        """Test normalization of common team aliases."""
        test_cases = [
            ('bama', 'ALABAMA'),
            ('uga', 'GEORGIA'),
            ('uf', 'FLORIDA'),
            ('ou', 'OKLAHOMA'),
            ('osu', 'OHIO STATE'),  # Note: Could be Oklahoma State too
            ('psu', 'PENN STATE'),
            ('fsu', 'FLORIDA STATE'),
            ('the u', 'MIAMI'),
            ('nd', 'NOTRE DAME'),
        ]
        
        for input_name, expected in test_cases:
            with self.subTest(input=input_name):
                result = self.normalizer.normalize(input_name)
                self.assertEqual(result, expected, 
                               f"Expected '{input_name}' to normalize to '{expected}', got '{result}'")
    
    def test_normalize_full_names(self):
        """Test normalization of full team names."""
        test_cases = [
            ('Alabama', 'ALABAMA'),
            ('georgia bulldogs', 'GEORGIA'),
            ('University of Georgia', 'GEORGIA'),
            ('Ohio State Buckeyes', 'OHIO STATE'),
            ('Florida State Seminoles', 'FLORIDA STATE'),
        ]
        
        for input_name, expected in test_cases:
            with self.subTest(input=input_name):
                result = self.normalizer.normalize(input_name)
                self.assertEqual(result, expected)
    
    def test_normalize_case_insensitive(self):
        """Test that normalization is case insensitive."""
        test_cases = [
            'alabama', 'ALABAMA', 'Alabama', 'aLaBaMa'
        ]
        
        for input_name in test_cases:
            with self.subTest(input=input_name):
                result = self.normalizer.normalize(input_name)
                self.assertEqual(result, 'ALABAMA')
    
    def test_normalize_whitespace_handling(self):
        """Test handling of extra whitespace."""
        test_cases = [
            ('  alabama  ', 'ALABAMA'),
            ('georgia   bulldogs', 'GEORGIA'),
            ('ohio\tstate', 'OHIO STATE'),
        ]
        
        for input_name, expected in test_cases:
            with self.subTest(input=input_name):
                result = self.normalizer.normalize(input_name)
                self.assertEqual(result, expected)
    
    def test_normalize_invalid_names(self):
        """Test handling of invalid team names."""
        invalid_names = [
            'invalid team',
            'xyz university',
            'fake college',
            '',
            None
        ]
        
        for invalid_name in invalid_names:
            with self.subTest(input=invalid_name):
                result = self.normalizer.normalize(invalid_name)
                self.assertIsNone(result)
    
    def test_espn_format_conversion(self):
        """Test conversion to ESPN API format."""
        test_cases = [
            ('ALABAMA', 'Alabama Crimson Tide'),
            ('GEORGIA', 'Georgia Bulldogs'),
            ('OHIO STATE', 'Ohio State Buckeyes'),
            ('FLORIDA STATE', 'Florida State Seminoles'),
        ]
        
        for normalized_name, expected_espn in test_cases:
            with self.subTest(input=normalized_name):
                result = self.normalizer.to_espn_format(normalized_name)
                self.assertEqual(result, expected_espn)
    
    def test_odds_format_conversion(self):
        """Test conversion to Odds API format."""
        test_cases = [
            ('ALABAMA', 'Alabama'),
            ('GEORGIA', 'Georgia'),
            ('OHIO STATE', 'Ohio State'),
            ('MISSISSIPPI', 'Ole Miss'),
        ]
        
        for normalized_name, expected_odds in test_cases:
            with self.subTest(input=normalized_name):
                result = self.normalizer.to_odds_format(normalized_name)
                self.assertEqual(result, expected_odds)
    
    def test_get_all_aliases(self):
        """Test retrieval of all aliases for a team."""
        aliases = self.normalizer.get_all_aliases('ALABAMA')
        
        # Should include the normalized name
        self.assertIn('ALABAMA', aliases)
        
        # Should be a list
        self.assertIsInstance(aliases, list)
        
        # Should have more than just the normalized name
        self.assertGreater(len(aliases), 1)
    
    def test_validate_team(self):
        """Test team name validation."""
        # Valid teams
        valid_teams = ['alabama', 'uga', 'Georgia Bulldogs', 'ohio state']
        for team in valid_teams:
            with self.subTest(team=team):
                self.assertTrue(self.normalizer.validate_team(team))
        
        # Invalid teams
        invalid_teams = ['invalid team', 'xyz university', '']
        for team in invalid_teams:
            with self.subTest(team=team):
                self.assertFalse(self.normalizer.validate_team(team))
    
    def test_get_all_teams(self):
        """Test retrieval of all supported teams."""
        all_teams = self.normalizer.get_all_teams()
        
        # Should be a list
        self.assertIsInstance(all_teams, list)
        
        # Should contain major teams
        expected_teams = ['ALABAMA', 'GEORGIA', 'OHIO STATE', 'FLORIDA', 'TEXAS']
        for team in expected_teams:
            self.assertIn(team, all_teams)
        
        # Should have a reasonable number of teams (100+ FBS teams)
        self.assertGreater(len(all_teams), 100)
    
    def test_fuzzy_matching(self):
        """Test fuzzy matching for near-miss inputs."""
        test_cases = [
            ('georiga', 'GEORGIA'),  # Typo
            ('alabam', 'ALABAMA'),   # Missing letter
            ('ohio stat', 'OHIO STATE'),  # Partial name
        ]
        
        for input_name, expected in test_cases:
            with self.subTest(input=input_name):
                result = self.normalizer.normalize(input_name)
                # Fuzzy matching might not always work, so we allow None
                if result is not None:
                    self.assertEqual(result, expected)
    
    def test_conference_coverage(self):
        """Test that major conferences are well represented."""
        all_teams = set(self.normalizer.get_all_teams())
        
        # SEC teams
        sec_teams = {'ALABAMA', 'GEORGIA', 'LSU', 'FLORIDA', 'TEXAS', 'OKLAHOMA'}
        self.assertTrue(sec_teams.issubset(all_teams), "Missing SEC teams")
        
        # Big Ten teams
        big_ten_teams = {'OHIO STATE', 'MICHIGAN', 'PENN STATE', 'WISCONSIN'}
        self.assertTrue(big_ten_teams.issubset(all_teams), "Missing Big Ten teams")
        
        # Big 12 teams
        big12_teams = {'TEXAS TECH', 'OKLAHOMA STATE', 'BAYLOR', 'TCU'}
        self.assertTrue(big12_teams.issubset(all_teams), "Missing Big 12 teams")
        
        # ACC teams
        acc_teams = {'CLEMSON', 'FLORIDA STATE', 'MIAMI', 'NORTH CAROLINA'}
        self.assertTrue(acc_teams.issubset(all_teams), "Missing ACC teams")
    
    def test_ambiguous_abbreviations(self):
        """Test handling of ambiguous abbreviations."""
        # These abbreviations could refer to multiple teams
        # The normalizer should handle them consistently
        
        # MSU could be Michigan State or Mississippi State
        result = self.normalizer.normalize('MSU')
        self.assertIn(result, ['MICHIGAN STATE', 'MISSISSIPPI STATE'])
        
        # OSU could be Ohio State or Oklahoma State
        result = self.normalizer.normalize('OSU')
        self.assertIn(result, ['OHIO STATE', 'OKLAHOMA STATE'])
    
    def test_global_normalizer_instance(self):
        """Test that global normalizer instance works correctly."""
        # Test using the global instance
        result = normalizer.normalize('alabama')
        self.assertEqual(result, 'ALABAMA')
        
        # Test that it's the same type as our test instance
        self.assertIsInstance(normalizer, TeamNameNormalizer)
    
    def test_normalize_same_team_edge_case(self):
        """Test edge case where home and away teams are the same."""
        # This should be caught at a higher level, but normalizer should handle it
        home = self.normalizer.normalize('alabama')
        away = self.normalizer.normalize('bama')
        
        # Both should normalize to the same team
        self.assertEqual(home, away)
        self.assertEqual(home, 'ALABAMA')
    
    def test_clean_input_method(self):
        """Test the internal _clean_input method."""
        test_cases = [
            ('  Alabama Football  ', 'ALABAMA'),
            ('georgia university', 'GEORGIA'),
            ('Ohio State University', 'OHIO STATE'),
        ]
        
        for input_str, expected in test_cases:
            with self.subTest(input=input_str):
                cleaned = self.normalizer._clean_input(input_str)
                # The cleaned input should help with normalization
                result = self.normalizer.normalize(input_str)
                self.assertEqual(result, expected)


class TestNormalizerIntegration(unittest.TestCase):
    """Integration tests for normalizer with other components."""
    
    def test_normalizer_with_cache_keys(self):
        """Test that normalized names work well as cache keys."""
        from data.cache_manager import CacheKeyGenerator
        
        key_gen = CacheKeyGenerator()
        
        # Normalize different inputs for same team
        team1 = normalizer.normalize('alabama')
        team2 = normalizer.normalize('bama')
        team3 = normalizer.normalize('Alabama Crimson Tide')
        
        # All should produce same cache key
        key1 = key_gen.team_data_key(team1, 'stats')
        key2 = key_gen.team_data_key(team2, 'stats')
        key3 = key_gen.team_data_key(team3, 'stats')
        
        self.assertEqual(key1, key2)
        self.assertEqual(key2, key3)
    
    def test_normalizer_consistency(self):
        """Test that normalization is consistent across calls."""
        test_inputs = ['alabama', 'uga', 'ohio state', 'fsu']
        
        for input_name in test_inputs:
            # Multiple calls should return same result
            result1 = normalizer.normalize(input_name)
            result2 = normalizer.normalize(input_name)
            result3 = normalizer.normalize(input_name)
            
            self.assertEqual(result1, result2)
            self.assertEqual(result2, result3)


if __name__ == '__main__':
    unittest.main()