"""
Tests for EDHREC service functionality.

This module tests the EDHREC API integration, error handling, retry logic,
and caching functionality.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import tempfile
import shutil
import json
import time
from pathlib import Path

from mtg_deck_builder.edhrec_service import EDHRECService, EDHRECAPIError
from mtg_deck_builder.models import CardRecommendation


class TestEDHRECService(unittest.TestCase):
    """Test cases for EDHRECService class."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create temporary directory for cache testing
        self.temp_dir = tempfile.mkdtemp()
        self.cache_dir = Path(self.temp_dir) / "cache"
        
        # Mock pyedhrec to avoid actual API calls in tests
        self.pyedhrec_patcher = patch('mtg_deck_builder.edhrec_service.pyedhrec')
        self.mock_pyedhrec = self.pyedhrec_patcher.start()
        
        # Create service instance with test cache directory
        self.service = EDHRECService(cache_dir=str(self.cache_dir))
    
    def tearDown(self):
        """Clean up test fixtures."""
        self.pyedhrec_patcher.stop()
        shutil.rmtree(self.temp_dir)
    
    def test_initialization(self):
        """Test EDHRECService initialization."""
        # Test with custom cache directory
        service = EDHRECService(cache_dir=str(self.cache_dir))
        self.assertEqual(service.cache_dir, self.cache_dir)
        self.assertTrue(service.cache_dir.exists())
        
        # Test default cache directory with proper temp directory
        with patch('os.path.expanduser') as mock_expanduser:
            temp_home = tempfile.mkdtemp()
            mock_expanduser.return_value = temp_home
            try:
                service = EDHRECService()
                expected_path = Path(temp_home) / ".mtg_deck_builder" / "cache"
                self.assertEqual(service.cache_dir, expected_path)
                self.assertTrue(service.cache_dir.exists())
            finally:
                shutil.rmtree(temp_home)
    
    def test_get_commander_recommendations_success(self):
        """Test successful commander recommendations retrieval."""
        # Mock API response
        mock_response = {
            'high_synergy': [
                {
                    'name': 'Doubling Season',
                    'synergy_score': 0.9,
                    'inclusion_percentage': 75.0
                }
            ],
            'staples': [
                {
                    'name': 'Sol Ring',
                    'synergy_score': 0.95,
                    'inclusion_percentage': 85.0
                }
            ]
        }
        
        self.mock_pyedhrec.get_commander_data.return_value = mock_response
        
        # Test the method
        recommendations = self.service.get_commander_recommendations("Atraxa, Praetors' Voice")
        
        # Verify results
        self.assertEqual(len(recommendations), 2)
        
        # Check first recommendation
        rec1 = recommendations[0]
        self.assertEqual(rec1.name, 'Doubling Season')
        self.assertEqual(rec1.synergy_score, 0.9)
        self.assertEqual(rec1.category, 'synergy')
        self.assertEqual(rec1.inclusion_percentage, 75.0)
        
        # Check second recommendation
        rec2 = recommendations[1]
        self.assertEqual(rec2.name, 'Sol Ring')
        self.assertEqual(rec2.synergy_score, 0.95)
        self.assertEqual(rec2.category, 'staple')
        self.assertEqual(rec2.inclusion_percentage, 85.0)
    
    def test_get_commander_recommendations_api_error(self):
        """Test handling of API errors."""
        # Mock API to raise an exception
        self.mock_pyedhrec.get_commander_data.side_effect = Exception("API Error")
        
        # Test that EDHRECAPIError is raised
        with self.assertRaises(EDHRECAPIError):
            self.service.get_commander_recommendations("Invalid Commander")
    
    def test_get_card_synergy_score(self):
        """Test card synergy score calculation."""
        # Mock recommendations
        mock_response = {
            'high_synergy': [
                {
                    'name': 'Doubling Season',
                    'synergy_score': 0.9,
                    'inclusion_percentage': 75.0
                }
            ]
        }
        
        self.mock_pyedhrec.get_commander_data.return_value = mock_response
        
        # Test existing card
        score = self.service.get_card_synergy_score("Doubling Season", "Atraxa, Praetors' Voice")
        self.assertEqual(score, 0.9)
        
        # Test non-existing card
        score = self.service.get_card_synergy_score("Random Card", "Atraxa, Praetors' Voice")
        self.assertEqual(score, 0.1)
    
    def test_caching_functionality(self):
        """Test caching of API responses."""
        # Mock API response
        mock_response = {
            'staples': [
                {
                    'name': 'Sol Ring',
                    'synergy_score': 0.95,
                    'inclusion_percentage': 85.0
                }
            ]
        }
        
        self.mock_pyedhrec.get_commander_data.return_value = mock_response
        
        # First call should hit API
        recommendations1 = self.service.get_commander_recommendations("Test Commander")
        self.assertEqual(self.mock_pyedhrec.get_commander_data.call_count, 1)
        
        # Second call should use cache
        recommendations2 = self.service.get_commander_recommendations("Test Commander")
        self.assertEqual(self.mock_pyedhrec.get_commander_data.call_count, 1)  # No additional calls
        
        # Results should be identical
        self.assertEqual(len(recommendations1), len(recommendations2))
        self.assertEqual(recommendations1[0].name, recommendations2[0].name)
    
    def test_cache_expiration(self):
        """Test cache expiration functionality."""
        # Mock API response
        mock_response = {
            'staples': [
                {
                    'name': 'Sol Ring',
                    'synergy_score': 0.95,
                    'inclusion_percentage': 85.0
                }
            ]
        }
        
        self.mock_pyedhrec.get_commander_data.return_value = mock_response
        
        # Set very short cache TTL for testing
        self.service.cache_ttl = 0.1  # 0.1 seconds
        
        # First call
        self.service.get_commander_recommendations("Test Commander")
        self.assertEqual(self.mock_pyedhrec.get_commander_data.call_count, 1)
        
        # Wait for cache to expire
        time.sleep(0.2)
        
        # Second call should hit API again due to expired cache
        self.service.get_commander_recommendations("Test Commander")
        self.assertEqual(self.mock_pyedhrec.get_commander_data.call_count, 2)
    
    def test_retry_logic(self):
        """Test retry logic with exponential backoff."""
        # Mock API to fail twice then succeed
        self.mock_pyedhrec.get_commander_data.side_effect = [
            Exception("Network Error"),
            Exception("Timeout"),
            {'staples': [{'name': 'Sol Ring', 'synergy_score': 0.95, 'inclusion_percentage': 85.0}]}
        ]
        
        # Reduce delays for faster testing
        self.service.base_delay = 0.01
        self.service.max_delay = 0.1
        
        # Should succeed after retries
        recommendations = self.service.get_commander_recommendations("Test Commander")
        self.assertEqual(len(recommendations), 1)
        self.assertEqual(self.mock_pyedhrec.get_commander_data.call_count, 3)
    
    def test_retry_exhaustion(self):
        """Test behavior when all retries are exhausted."""
        # Mock API to always fail
        self.mock_pyedhrec.get_commander_data.side_effect = Exception("Persistent Error")
        
        # Reduce delays for faster testing
        self.service.base_delay = 0.01
        self.service.max_delay = 0.1
        
        # Should raise EDHRECAPIError after max retries
        with self.assertRaises(EDHRECAPIError):
            self.service.get_commander_recommendations("Test Commander")
        
        # Should have tried max_retries times
        self.assertEqual(self.mock_pyedhrec.get_commander_data.call_count, self.service.max_retries)
    
    def test_fallback_recommendations(self):
        """Test fallback recommendations when API is unavailable."""
        fallback_recs = self.service.get_fallback_recommendations("Test Commander")
        
        # Should return generic staple cards
        self.assertGreater(len(fallback_recs), 0)
        
        # Check that Sol Ring is included (common staple)
        sol_ring_found = any(rec.name == "Sol Ring" for rec in fallback_recs)
        self.assertTrue(sol_ring_found)
        
        # Verify recommendation structure
        for rec in fallback_recs:
            self.assertIsInstance(rec, CardRecommendation)
            self.assertIsInstance(rec.name, str)
            self.assertGreaterEqual(rec.synergy_score, 0.0)
            self.assertLessEqual(rec.synergy_score, 1.0)
    
    def test_get_commander_recommendations_with_fallback(self):
        """Test automatic fallback when API fails."""
        # Mock API to fail
        self.mock_pyedhrec.get_commander_data.side_effect = Exception("API Unavailable")
        
        # Should return fallback recommendations without raising exception
        recommendations = self.service.get_commander_recommendations_with_fallback("Test Commander")
        
        # Should get fallback recommendations
        self.assertGreater(len(recommendations), 0)
        
        # Verify these are fallback recommendations (should include Sol Ring)
        sol_ring_found = any(rec.name == "Sol Ring" for rec in recommendations)
        self.assertTrue(sol_ring_found)
    
    def test_api_availability_check(self):
        """Test API availability checking."""
        # Mock successful API call
        self.mock_pyedhrec.get_commander_data.return_value = {'test': 'data'}
        
        # Should return True for available API
        self.assertTrue(self.service.is_api_available())
        
        # Mock failed API call
        self.mock_pyedhrec.get_commander_data.side_effect = Exception("API Down")
        
        # Should return False for unavailable API
        self.assertFalse(self.service.is_api_available())
    
    def test_cache_management(self):
        """Test cache clearing functionality."""
        # Create some cache files
        cache_file1 = self.cache_dir / "test1.json"
        cache_file2 = self.cache_dir / "test2.json"
        
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        cache_file1.write_text('{"test": "data1"}')
        cache_file2.write_text('{"test": "data2"}')
        
        # Verify files exist
        self.assertTrue(cache_file1.exists())
        self.assertTrue(cache_file2.exists())
        
        # Clear cache
        self.service.clear_cache()
        
        # Verify files are removed
        self.assertFalse(cache_file1.exists())
        self.assertFalse(cache_file2.exists())
    
    def test_error_handling_decorator(self):
        """Test the error handling decorator."""
        # Create a test function that raises EDHRECAPIError
        @self.service.handle_api_errors
        def test_recommendations_func():
            raise EDHRECAPIError("Test error")
        
        # Should return fallback recommendations instead of raising
        result = test_recommendations_func()
        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)
        
        # Create a test function that should return synergy score
        @self.service.handle_api_errors
        def test_synergy_func():
            raise EDHRECAPIError("Test error")
        
        # Should return neutral score
        result = test_synergy_func()
        self.assertEqual(result, 0.5)


if __name__ == '__main__':
    unittest.main()