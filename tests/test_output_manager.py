"""
Unit tests for MTG Commander Deck Builder output manager.
"""

import unittest
import tempfile
import os
from pathlib import Path
from unittest.mock import patch, mock_open
from datetime import datetime

from mtg_deck_builder.output_manager import OutputManager
from mtg_deck_builder.models import Deck, DeckStatistics, CardRecommendation


class TestOutputManager(unittest.TestCase):
    """Test cases for OutputManager class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.output_manager = OutputManager(self.temp_dir)
        
        # Create test deck
        self.test_deck = Deck(commander="Atraxa, Praetors' Voice")
        self.test_deck.cards = [
            "Sol Ring", "Command Tower", "Counterspell", "Lightning Bolt",
            "Forest", "Plains", "Island", "Swamp"
        ]
        self.test_deck.color_identity = ["W", "U", "B", "G"]
    
    def tearDown(self):
        """Clean up test fixtures."""
        # Clean up temporary directory
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_output_manager_creation(self):
        """Test OutputManager initialization."""
        self.assertEqual(str(self.output_manager.output_directory), self.temp_dir)
        self.assertTrue(Path(self.temp_dir).exists())
    
    def test_output_manager_creates_directory(self):
        """Test that OutputManager creates output directory if it doesn't exist."""
        new_dir = os.path.join(self.temp_dir, "new_output_dir")
        manager = OutputManager(new_dir)
        
        self.assertTrue(Path(new_dir).exists())


class TestFilenameGeneration(unittest.TestCase):
    """Test cases for filename generation functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.output_manager = OutputManager(self.temp_dir)
    
    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_generate_filename_basic(self):
        """Test basic filename generation."""
        filename = self.output_manager.generate_filename("Atraxa, Praetors' Voice")
        expected = "atraxa_praetors_voice_deck.txt"
        
        self.assertEqual(filename, expected)
    
    def test_generate_filename_with_special_characters(self):
        """Test filename generation with special characters."""
        filename = self.output_manager.generate_filename("Jace, the Mind-Sculptor!")
        expected = "jace_the_mind-sculptor_deck.txt"
        
        self.assertEqual(filename, expected)
    
    def test_generate_filename_empty_name(self):
        """Test filename generation with empty commander name."""
        filename = self.output_manager.generate_filename("")
        expected = "unknown_commander_deck.txt"
        
        self.assertEqual(filename, expected)
    
    def test_generate_filename_long_name(self):
        """Test filename generation with very long commander name."""
        long_name = "A" * 100  # Very long name
        filename = self.output_manager.generate_filename(long_name)
        
        # Should be truncated to 50 characters plus suffix
        self.assertTrue(len(filename) <= 60)  # 50 + "_deck.txt"
        self.assertTrue(filename.endswith("_deck.txt"))
    
    @patch('mtg_deck_builder.output_manager.datetime')
    def test_generate_filename_with_timestamp(self, mock_datetime):
        """Test filename generation when file already exists."""
        # Mock datetime for consistent timestamp
        mock_datetime.now.return_value.strftime.return_value = "20231201_143000"
        
        # Create existing file
        existing_file = Path(self.temp_dir) / "atraxa_praetors_voice_deck.txt"
        existing_file.touch()
        
        filename = self.output_manager.generate_filename("Atraxa, Praetors' Voice")
        expected = "atraxa_praetors_voice_deck_20231201_143000.txt"
        
        self.assertEqual(filename, expected)
    
    def test_sanitize_filename(self):
        """Test filename sanitization."""
        # Test various special characters
        test_cases = [
            ("Jace, the Mind Sculptor", "jace_the_mind_sculptor"),
            ("Atraxa/Praetors'Voice", "atraxapraetorsvoice"),
            ("Test@#$%Commander", "testcommander"),
            ("Commander-With_Dashes", "commander-with_dashes"),
            ("123 Numeric Commander", "123_numeric_commander")
        ]
        
        for input_name, expected in test_cases:
            result = self.output_manager._sanitize_filename(input_name)
            self.assertEqual(result, expected)


class TestDeckFormatting(unittest.TestCase):
    """Test cases for deck list formatting functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.output_manager = OutputManager(self.temp_dir)
        
        # Create test deck
        self.test_deck = Deck(commander="Atraxa, Praetors' Voice")
        self.test_deck.cards = ["Sol Ring", "Command Tower", "Counterspell"]
        self.test_deck.color_identity = ["W", "U", "B", "G"]
        
        # Create test statistics
        self.test_stats = DeckStatistics(
            card_types={'creature': 25, 'land': 35, 'instant': 20, 'artifact': 20},
            average_cmc=3.2,
            synergy_score=0.75,
            total_cards=100
        )
    
    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_format_deck_list_basic(self):
        """Test basic deck list formatting."""
        formatted = self.output_manager.format_deck_list(self.test_deck)
        
        # Check for required sections
        self.assertIn("MTG Commander Deck: Atraxa, Praetors' Voice", formatted)
        self.assertIn("COMMANDER:", formatted)
        self.assertIn("1 Atraxa, Praetors' Voice", formatted)
        self.assertIn("MAIN DECK (3 cards):", formatted)
        self.assertIn("1 Sol Ring", formatted)
        self.assertIn("1 Command Tower", formatted)
        self.assertIn("1 Counterspell", formatted)
        self.assertIn("DECK SUMMARY:", formatted)
        self.assertIn("Total Cards: 4", formatted)
    
    def test_format_deck_list_with_statistics(self):
        """Test deck list formatting with statistics included."""
        formatted = self.output_manager.format_deck_list(self.test_deck, self.test_stats)
        
        # Check for statistics section
        self.assertIn("DECK STATISTICS:", formatted)
        self.assertIn("Average CMC: 3.20", formatted)
        self.assertIn("Creatures: 25 (25.0%)", formatted)
        self.assertIn("Lands: 35 (35.0%)", formatted)
        self.assertIn("Synergy Score: 0.75", formatted)
    
    def test_format_deck_list_sorted_cards(self):
        """Test that cards are sorted alphabetically in output."""
        # Add cards in non-alphabetical order
        self.test_deck.cards = ["Zebra Card", "Alpha Card", "Beta Card"]
        formatted = self.output_manager.format_deck_list(self.test_deck)
        
        # Find the main deck section
        lines = formatted.split('\n')
        main_deck_start = None
        for i, line in enumerate(lines):
            if "MAIN DECK" in line:
                main_deck_start = i + 1
                break
        
        self.assertIsNotNone(main_deck_start)
        
        # Check that cards appear in alphabetical order
        card_lines = []
        for i in range(main_deck_start, len(lines)):
            if lines[i].startswith("1 ") and lines[i] != "":
                card_lines.append(lines[i])
            elif lines[i] == "":
                break
        
        expected_order = ["1 Alpha Card", "1 Beta Card", "1 Zebra Card"]
        self.assertEqual(card_lines, expected_order)
    
    def test_format_deck_list_validation_status(self):
        """Test that validation status is included in formatted output."""
        # Test with valid deck
        valid_deck = Deck(commander="Test Commander")
        for i in range(99):
            valid_deck.cards.append(f"Card {i}")
        
        formatted = self.output_manager.format_deck_list(valid_deck)
        self.assertIn("✓ Deck passes all Commander format validation checks", formatted)
        
        # Test with invalid deck
        invalid_deck = Deck(commander="Test Commander")
        invalid_deck.cards = ["Sol Ring", "Sol Ring"]  # Duplicate non-basic
        
        formatted = self.output_manager.format_deck_list(invalid_deck)
        self.assertIn("⚠ Deck validation issues found:", formatted)


class TestFileWriting(unittest.TestCase):
    """Test cases for file writing functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.output_manager = OutputManager(self.temp_dir)
        
        # Create test deck
        self.test_deck = Deck(commander="Atraxa, Praetors' Voice")
        self.test_deck.cards = ["Sol Ring", "Command Tower"]
    
    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_write_deck_file_success(self):
        """Test successful deck file writing."""
        file_path = self.output_manager.write_deck_file(self.test_deck)
        
        # Check that file was created
        self.assertTrue(Path(file_path).exists())
        
        # Check file contents
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        self.assertIn("Atraxa, Praetors' Voice", content)
        self.assertIn("Sol Ring", content)
        self.assertIn("Command Tower", content)
    
    def test_write_deck_file_custom_filename(self):
        """Test deck file writing with custom filename."""
        custom_filename = "my_custom_deck.txt"
        file_path = self.output_manager.write_deck_file(self.test_deck, custom_filename)
        
        expected_path = str(Path(self.temp_dir) / custom_filename)
        self.assertEqual(file_path, expected_path)
        self.assertTrue(Path(file_path).exists())
    
    def test_write_deck_file_with_statistics(self):
        """Test deck file writing with statistics included."""
        stats = DeckStatistics(average_cmc=2.5, synergy_score=0.8, total_cards=100)
        file_path = self.output_manager.write_deck_file(self.test_deck, statistics=stats)
        
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        self.assertIn("Average CMC: 2.50", content)
        self.assertIn("Synergy Score: 0.80", content)
    
    def test_write_deck_file_empty_commander_error(self):
        """Test error handling for deck with empty commander."""
        empty_deck = Deck(commander="")
        
        with self.assertRaises(ValueError) as context:
            self.output_manager.write_deck_file(empty_deck)
        
        self.assertIn("no commander", str(context.exception))
    
    def test_write_deck_file_no_cards_error(self):
        """Test error handling for deck with no cards."""
        empty_deck = Deck(commander="Test Commander")
        empty_deck.cards = []
        
        with self.assertRaises(ValueError) as context:
            self.output_manager.write_deck_file(empty_deck)
        
        self.assertIn("no cards", str(context.exception))
    
    @patch('builtins.open', side_effect=OSError("Permission denied"))
    def test_write_deck_file_permission_error(self, mock_open):
        """Test error handling for file permission issues."""
        with self.assertRaises(OSError) as context:
            self.output_manager.write_deck_file(self.test_deck)
        
        self.assertIn("Failed to write deck file", str(context.exception))


class TestDeckStatisticsGeneration(unittest.TestCase):
    """Test cases for deck statistics generation functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.output_manager = OutputManager(self.temp_dir)
        
        # Create test deck with varied cards
        self.test_deck = Deck(commander="Atraxa, Praetors' Voice")
        self.test_deck.cards = [
            "Sol Ring", "Lightning Bolt", "Counterspell", "Forest",
            "Plains", "Island", "Swamp", "Command Tower",
            "Jace, the Mind Sculptor", "Wrath of God"
        ]
    
    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_generate_deck_statistics_basic(self):
        """Test basic deck statistics generation."""
        stats = self.output_manager.generate_deck_statistics(self.test_deck)
        
        self.assertEqual(stats.total_cards, self.test_deck.total_cards)
        self.assertGreater(len(stats.card_types), 0)
        self.assertGreater(len(stats.mana_curve), 0)
        self.assertGreater(len(stats.color_distribution), 0)
    
    def test_generate_deck_statistics_with_recommendations(self):
        """Test deck statistics generation with card recommendations."""
        recommendations = [
            CardRecommendation(name="Sol Ring", synergy_score=0.9),
            CardRecommendation(name="Lightning Bolt", synergy_score=0.7),
            CardRecommendation(name="Counterspell", synergy_score=0.8)
        ]
        
        stats = self.output_manager.generate_deck_statistics(self.test_deck, recommendations)
        
        self.assertGreater(stats.synergy_score, 0)
        self.assertLessEqual(stats.synergy_score, 1.0)
    
    def test_analyze_card_basic_lands(self):
        """Test card analysis for basic lands."""
        card_type, cmc = self.output_manager._analyze_card("Forest")
        self.assertEqual(card_type, "land")
        self.assertEqual(cmc, 0)
        
        card_type, cmc = self.output_manager._analyze_card("Snow-Covered Plains")
        self.assertEqual(card_type, "land")
        self.assertEqual(cmc, 0)
    
    def test_analyze_card_artifacts(self):
        """Test card analysis for artifacts."""
        card_type, cmc = self.output_manager._analyze_card("Sol Ring")
        self.assertEqual(card_type, "artifact")
        self.assertEqual(cmc, 0)
        
        card_type, cmc = self.output_manager._analyze_card("Azorius Signet")
        self.assertEqual(card_type, "artifact")
        self.assertEqual(cmc, 2)
    
    def test_analyze_card_planeswalkers(self):
        """Test card analysis for planeswalkers."""
        card_type, cmc = self.output_manager._analyze_card("Jace, the Mind Sculptor")
        self.assertEqual(card_type, "planeswalker")
        self.assertEqual(cmc, 4)
    
    def test_analyze_card_spells(self):
        """Test card analysis for instant and sorcery spells."""
        card_type, cmc = self.output_manager._analyze_card("Lightning Bolt")
        self.assertEqual(card_type, "instant")
        self.assertEqual(cmc, 1)
        
        card_type, cmc = self.output_manager._analyze_card("Wrath of God")
        self.assertEqual(card_type, "sorcery")
        self.assertEqual(cmc, 4)
    
    def test_analyze_color_distribution(self):
        """Test color distribution analysis."""
        cards = ["Forest", "Lightning Bolt", "Counterspell", "Angel of Mercy", "Sol Ring"]
        color_dist = self.output_manager._analyze_color_distribution(cards)
        
        # Should have counts for different colors
        self.assertGreaterEqual(color_dist['green'], 0)
        self.assertGreaterEqual(color_dist['red'], 0)
        self.assertGreaterEqual(color_dist['blue'], 0)
        self.assertGreaterEqual(color_dist['white'], 0)
        self.assertGreaterEqual(color_dist['colorless'], 0)
    
    def test_calculate_synergy_score(self):
        """Test synergy score calculation."""
        recommendations = [
            CardRecommendation(name="Sol Ring", synergy_score=0.9),
            CardRecommendation(name="Lightning Bolt", synergy_score=0.7)
        ]
        
        test_deck = Deck(commander="Test")
        test_deck.cards = ["Sol Ring", "Lightning Bolt", "Unknown Card"]
        
        synergy_score = self.output_manager._calculate_synergy_score(test_deck, recommendations)
        
        # Should be average of 0.9 and 0.7 = 0.8
        self.assertAlmostEqual(synergy_score, 0.8, places=2)
    
    def test_calculate_synergy_score_no_matches(self):
        """Test synergy score calculation with no matching cards."""
        recommendations = [
            CardRecommendation(name="Card A", synergy_score=0.9)
        ]
        
        test_deck = Deck(commander="Test")
        test_deck.cards = ["Card B", "Card C"]
        
        synergy_score = self.output_manager._calculate_synergy_score(test_deck, recommendations)
        self.assertEqual(synergy_score, 0.0)


class TestSummaryReport(unittest.TestCase):
    """Test cases for summary report generation."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.output_manager = OutputManager(self.temp_dir)
        
        self.test_deck = Deck(commander="Test Commander")
        self.test_stats = DeckStatistics(
            card_types={'creature': 30, 'land': 35, 'instant': 20, 'artifact': 15},
            mana_curve={0: 5, 1: 8, 2: 12, 3: 15, 4: 10, 5: 8, 6: 5, 7: 2},
            color_distribution={'white': 20, 'blue': 25, 'black': 15, 'red': 10, 'green': 20, 'colorless': 10},
            average_cmc=3.2,
            synergy_score=0.75,
            total_cards=100
        )
    
    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_create_summary_report(self):
        """Test summary report creation."""
        report = self.output_manager.create_summary_report(self.test_deck, self.test_stats)
        
        # Check for required sections
        self.assertIn("DECK COMPOSITION ANALYSIS", report)
        self.assertIn("Card Types:", report)
        self.assertIn("Mana Curve:", report)
        self.assertIn("Color Distribution:", report)
        self.assertIn("Average CMC: 3.20", report)
        self.assertIn("Synergy Score: 0.75", report)
        self.assertIn("Deck Balance Assessment:", report)
    
    def test_summary_report_card_types(self):
        """Test card type breakdown in summary report."""
        report = self.output_manager.create_summary_report(self.test_deck, self.test_stats)
        
        self.assertIn("Creature: 30 (30.0%)", report)
        self.assertIn("Land: 35 (35.0%)", report)
        self.assertIn("Instant: 20 (20.0%)", report)
        self.assertIn("Artifact: 15 (15.0%)", report)
    
    def test_summary_report_mana_curve(self):
        """Test mana curve visualization in summary report."""
        report = self.output_manager.create_summary_report(self.test_deck, self.test_stats)
        
        # Check for CMC entries with visual bars
        self.assertIn("CMC 0:", report)
        self.assertIn("CMC 3:", report)
        self.assertIn("█", report)  # Visual bar character
    
    def test_summary_report_synergy_assessment(self):
        """Test synergy score assessment in summary report."""
        # Test high synergy
        high_synergy_stats = DeckStatistics(synergy_score=0.85, total_cards=100)
        report = self.output_manager.create_summary_report(self.test_deck, high_synergy_stats)
        self.assertIn("Excellent synergy", report)
        
        # Test good synergy
        good_synergy_stats = DeckStatistics(synergy_score=0.65, total_cards=100)
        report = self.output_manager.create_summary_report(self.test_deck, good_synergy_stats)
        self.assertIn("Good synergy", report)
        
        # Test moderate synergy
        moderate_synergy_stats = DeckStatistics(synergy_score=0.55, total_cards=100)
        report = self.output_manager.create_summary_report(self.test_deck, moderate_synergy_stats)
        self.assertIn("Moderate synergy", report)
        
        # Test low synergy
        low_synergy_stats = DeckStatistics(synergy_score=0.25, total_cards=100)
        report = self.output_manager.create_summary_report(self.test_deck, low_synergy_stats)
        self.assertIn("Low synergy", report)
    
    def test_summary_report_balance_assessment(self):
        """Test deck balance assessment in summary report."""
        report = self.output_manager.create_summary_report(self.test_deck, self.test_stats)
        
        # Should have balance assessments
        self.assertIn("✓", report)  # Good balance indicators
        self.assertTrue("creature" in report.lower() and "balance" in report.lower())


if __name__ == '__main__':
    unittest.main()