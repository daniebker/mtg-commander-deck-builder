"""
Integration tests for MTG Commander Deck Builder CLI.

Tests cover end-to-end workflow with sample CSV files and commanders,
error handling with invalid inputs, and CLI argument parsing.
"""

import unittest
import tempfile
import os
import sys
import io
from pathlib import Path
from unittest.mock import patch, MagicMock, call
import argparse

from mtg_deck_builder.cli import (
    parse_arguments, validate_inputs, setup_logging, main,
    list_available_commanders, build_commander_deck,
    handle_user_friendly_errors, ProgressIndicator
)
from mtg_deck_builder.collection_parser import CollectionParseError, CommanderNotFoundError
from mtg_deck_builder.edhrec_service import EDHRECAPIError


class TestCLIArgumentParsing(unittest.TestCase):
    """Test cases for CLI argument parsing functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.sample_csv = self.create_sample_csv()
    
    def tearDown(self):
        """Clean up test fixtures."""
        for file in Path(self.temp_dir).glob("*"):
            file.unlink()
        os.rmdir(self.temp_dir)
    
    def create_sample_csv(self) -> str:
        """Create a sample CSV file for testing."""
        csv_content = """name,quantity,set
Lightning Bolt,4,M21
Sol Ring,1,C20
Command Tower,1,C21
Atraxa Praetors Voice,1,C16
Forest,10,BFZ
Island,10,BFZ
Plains,10,BFZ
Swamp,10,BFZ"""
        
        csv_path = os.path.join(self.temp_dir, "test_collection.csv")
        with open(csv_path, 'w', encoding='utf-8') as f:
            f.write(csv_content)
        return csv_path
    
    def test_parse_arguments_basic(self):
        """Test basic argument parsing with required arguments."""
        test_args = [self.sample_csv, "Atraxa, Praetors' Voice"]
        
        with patch('sys.argv', ['mtg-deck-builder'] + test_args):
            args = parse_arguments()
            
        self.assertEqual(args.csv_file, self.sample_csv)
        self.assertEqual(args.commander, "Atraxa, Praetors' Voice")
        self.assertEqual(args.output_dir, '.')
        self.assertFalse(args.verbose)
        self.assertFalse(args.quiet)
    
    def test_parse_arguments_with_options(self):
        """Test argument parsing with optional flags."""
        test_args = [
            '--verbose',
            '--output-dir', '/tmp/decks',
            '--min-deck-size', '80',
            self.sample_csv,
            "Edgar Markov"
        ]
        
        with patch('sys.argv', ['mtg-deck-builder'] + test_args):
            args = parse_arguments()
            
        self.assertTrue(args.verbose)
        self.assertEqual(args.output_dir, '/tmp/decks')
        self.assertEqual(args.min_deck_size, 80)
        self.assertEqual(args.commander, "Edgar Markov")
    
    def test_parse_arguments_list_commanders(self):
        """Test argument parsing for list commanders mode."""
        test_args = ['--list-commanders', self.sample_csv]
        
        with patch('sys.argv', ['mtg-deck-builder'] + test_args):
            args = parse_arguments()
            
        self.assertTrue(args.list_commanders)
        self.assertIsNone(args.commander)
    
    def test_parse_arguments_missing_commander(self):
        """Test that missing commander raises error unless list-commanders is used."""
        test_args = [self.sample_csv]
        
        with patch('sys.argv', ['mtg-deck-builder'] + test_args):
            with self.assertRaises(SystemExit):
                parse_arguments()
    
    def test_parse_arguments_conflicting_flags(self):
        """Test that conflicting verbose and quiet flags raise error."""
        test_args = ['--verbose', '--quiet', self.sample_csv, "Test Commander"]
        
        with patch('sys.argv', ['mtg-deck-builder'] + test_args):
            with self.assertRaises(SystemExit):
                parse_arguments()


class TestInputValidation(unittest.TestCase):
    """Test cases for input validation functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.valid_csv = self.create_test_file("name,quantity\nSol Ring,1\n")
        self.empty_csv = self.create_test_file("")
    
    def tearDown(self):
        """Clean up test fixtures."""
        for file in Path(self.temp_dir).glob("*"):
            file.unlink()
        os.rmdir(self.temp_dir)
    
    def create_test_file(self, content: str) -> str:
        """Create a test file with given content."""
        file_path = os.path.join(self.temp_dir, f"test_{len(content)}.csv")
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return file_path
    
    def test_validate_inputs_valid_file(self):
        """Test validation with valid CSV file."""
        # Should not raise any exceptions
        validate_inputs(self.valid_csv, "Test Commander")
    
    def test_validate_inputs_missing_file(self):
        """Test validation with non-existent file."""
        with self.assertRaises(FileNotFoundError):
            validate_inputs("/nonexistent/file.csv", "Test Commander")
    
    def test_validate_inputs_empty_file(self):
        """Test validation with empty CSV file."""
        with self.assertRaises(ValueError):
            validate_inputs(self.empty_csv, "Test Commander")
    
    def test_validate_inputs_directory_instead_of_file(self):
        """Test validation when path points to directory."""
        with self.assertRaises(ValueError):
            validate_inputs(self.temp_dir, "Test Commander")
    
    def test_validate_inputs_invalid_commander_name(self):
        """Test validation with invalid commander names."""
        # Empty commander name
        with self.assertRaises(ValueError):
            validate_inputs(self.valid_csv, "")
        
        # Too short commander name
        with self.assertRaises(ValueError):
            validate_inputs(self.valid_csv, "A")
        
        # Commander name with invalid characters
        with self.assertRaises(ValueError):
            validate_inputs(self.valid_csv, "Test<Commander>")


class TestProgressIndicator(unittest.TestCase):
    """Test cases for progress indicator functionality."""
    
    def test_progress_indicator_normal_mode(self):
        """Test progress indicator in normal mode."""
        with patch('sys.stdout', new_callable=io.StringIO) as mock_stdout:
            with ProgressIndicator("Test operation", verbose=False, quiet=False):
                pass
            
            output = mock_stdout.getvalue()
            self.assertIn("Test operation", output)
            self.assertIn("✓", output)
    
    def test_progress_indicator_verbose_mode(self):
        """Test progress indicator in verbose mode."""
        with patch('sys.stdout', new_callable=io.StringIO) as mock_stdout:
            with ProgressIndicator("Test operation", verbose=True, quiet=False):
                pass
            
            output = mock_stdout.getvalue()
            self.assertIn("Starting: Test operation", output)
            self.assertIn("Completed: Test operation", output)
    
    def test_progress_indicator_quiet_mode(self):
        """Test progress indicator in quiet mode."""
        with patch('sys.stdout', new_callable=io.StringIO) as mock_stdout:
            with ProgressIndicator("Test operation", verbose=False, quiet=True):
                pass
            
            output = mock_stdout.getvalue()
            self.assertEqual(output, "")


class TestEndToEndWorkflow(unittest.TestCase):
    """Test cases for end-to-end CLI workflow."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.sample_csv = self.create_comprehensive_csv()
        self.output_dir = os.path.join(self.temp_dir, "output")
        os.makedirs(self.output_dir, exist_ok=True)
    
    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def create_comprehensive_csv(self) -> str:
        """Create a comprehensive CSV file for testing."""
        csv_content = """name,quantity,set
Atraxa Praetors Voice,1,C16
Sol Ring,1,C20
Command Tower,1,C21
Lightning Bolt,4,M21
Counterspell,2,M21
Brainstorm,3,EMA
Forest,15,BFZ
Island,15,BFZ
Plains,15,BFZ
Swamp,15,BFZ
Cultivate,2,M21
Kodamas Reach,2,CHK
Swords to Plowshares,3,EMA
Path to Exile,2,CON
Rhystic Study,1,PCY
Mystic Remora,1,ICE
Cyclonic Rift,1,RTR
Wrath of God,2,10E
Supreme Verdict,1,RTR
Elspeth Knight Errant,1,ALA"""
        
        csv_path = os.path.join(self.temp_dir, "comprehensive_collection.csv")
        with open(csv_path, 'w', encoding='utf-8') as f:
            f.write(csv_content)
        return csv_path
    
    @patch('mtg_deck_builder.cli.EDHRECService')
    @patch('mtg_deck_builder.cli.DeckBuilder')
    @patch('mtg_deck_builder.cli.OutputManager')
    def test_successful_deck_building(self, mock_output_manager, mock_deck_builder, mock_edhrec_service):
        """Test successful end-to-end deck building workflow."""
        # Mock EDHREC service
        mock_edhrec = mock_edhrec_service.return_value
        mock_edhrec.get_commander_recommendations_with_fallback.return_value = [
            MagicMock(name="Sol Ring", synergy_score=0.95),
            MagicMock(name="Lightning Bolt", synergy_score=0.85)
        ]
        
        # Mock deck builder
        mock_builder = mock_deck_builder.return_value
        mock_deck = MagicMock()
        mock_deck.commander = "Atraxa, Praetors' Voice"
        mock_deck.total_cards = 100
        mock_deck.is_valid.return_value = True
        mock_deck.get_validation_errors.return_value = []
        mock_builder.build_deck.return_value = mock_deck
        
        # Mock output manager
        mock_output = mock_output_manager.return_value
        mock_statistics = MagicMock()
        mock_statistics.average_cmc = 3.2
        mock_statistics.creature_percentage = 35.0
        mock_statistics.land_percentage = 38.0
        mock_statistics.synergy_score = 0.75
        mock_statistics.card_types = {'creature': 35, 'land': 38}
        mock_output.generate_deck_statistics.return_value = mock_statistics
        mock_output.write_deck_file.return_value = "/path/to/deck.txt"
        
        # Test the workflow
        with patch('sys.stdout', new_callable=io.StringIO) as mock_stdout:
            build_commander_deck(
                csv_file=self.sample_csv,
                commander="Atraxa, Praetors' Voice",
                output_dir=self.output_dir,
                verbose=False,
                quiet=False
            )
        
        output = mock_stdout.getvalue()
        self.assertIn("Deck building completed successfully", output)
        self.assertIn("Atraxa, Praetors' Voice", output)
        
        # Verify mocks were called
        mock_builder.build_deck.assert_called_once()
        mock_output.write_deck_file.assert_called_once()
    
    @patch('mtg_deck_builder.cli.CollectionParser')
    def test_list_commanders_functionality(self, mock_parser_class):
        """Test the list commanders functionality."""
        mock_parser = mock_parser_class.return_value
        mock_parser.load_collection.return_value = {"test": MagicMock()}
        mock_parser.list_available_commanders.return_value = [
            "Atraxa, Praetors' Voice",
            "Edgar Markov",
            "The Ur-Dragon"
        ]
        
        with patch('sys.stdout', new_callable=io.StringIO) as mock_stdout:
            list_available_commanders(self.sample_csv)
        
        output = mock_stdout.getvalue()
        self.assertIn("Found 3 potential commanders", output)
        self.assertIn("Atraxa, Praetors' Voice", output)
        self.assertIn("Edgar Markov", output)
        self.assertIn("The Ur-Dragon", output)
    
    @patch('mtg_deck_builder.cli.CollectionParser')
    def test_commander_not_found_error_handling(self, mock_parser_class):
        """Test error handling when commander is not found."""
        mock_parser = mock_parser_class.return_value
        mock_parser.load_collection.return_value = {"test": MagicMock()}
        mock_parser.validate_commander.side_effect = CommanderNotFoundError("Commander not found")
        mock_parser.list_available_commanders.return_value = ["Alternative Commander"]
        
        with self.assertRaises(CommanderNotFoundError):
            build_commander_deck(
                csv_file=self.sample_csv,
                commander="Nonexistent Commander",
                output_dir=self.output_dir,
                quiet=True
            )
    
    @patch('mtg_deck_builder.cli.CollectionParser')
    def test_collection_parse_error_handling(self, mock_parser_class):
        """Test error handling for collection parsing errors."""
        mock_parser = mock_parser_class.return_value
        mock_parser.load_collection.side_effect = CollectionParseError("Invalid CSV format")
        
        with self.assertRaises(CollectionParseError):
            build_commander_deck(
                csv_file=self.sample_csv,
                commander="Test Commander",
                output_dir=self.output_dir,
                quiet=True
            )


class TestErrorHandling(unittest.TestCase):
    """Test cases for error handling and user-friendly messages."""
    
    def test_handle_user_friendly_errors(self):
        """Test conversion of technical errors to user-friendly messages."""
        # Test FileNotFoundError
        error = FileNotFoundError("test.csv")
        message = handle_user_friendly_errors(error, verbose=False)
        self.assertIn("File not found", message)
        
        # Test CollectionParseError
        error = CollectionParseError("Invalid CSV")
        message = handle_user_friendly_errors(error, verbose=False)
        self.assertIn("Could not parse your collection file", message)
        
        # Test CommanderNotFoundError
        error = CommanderNotFoundError("Commander not found")
        message = handle_user_friendly_errors(error, verbose=False)
        self.assertIn("Commander issue", message)
        
        # Test EDHRECAPIError
        error = EDHRECAPIError("API unavailable")
        message = handle_user_friendly_errors(error, verbose=False)
        self.assertIn("EDHREC service error", message)
        
        # Test generic error
        error = RuntimeError("Something went wrong")
        message = handle_user_friendly_errors(error, verbose=False)
        self.assertIn("unexpected error occurred", message)
    
    def test_handle_user_friendly_errors_verbose(self):
        """Test error handling in verbose mode."""
        error = RuntimeError("Detailed error message")
        message = handle_user_friendly_errors(error, verbose=True)
        self.assertIn("Detailed error message", message)


class TestMainFunction(unittest.TestCase):
    """Test cases for the main CLI function."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.sample_csv = self.create_sample_csv()
    
    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def create_sample_csv(self) -> str:
        """Create a sample CSV file."""
        csv_content = "name,quantity\nSol Ring,1\nAtraxa Praetors Voice,1\n"
        csv_path = os.path.join(self.temp_dir, "test.csv")
        with open(csv_path, 'w') as f:
            f.write(csv_content)
        return csv_path
    
    @patch('mtg_deck_builder.cli.build_commander_deck')
    def test_main_successful_execution(self, mock_build_deck):
        """Test successful execution of main function."""
        test_args = ['mtg-deck-builder', self.sample_csv, 'Test Commander']
        
        with patch('sys.argv', test_args):
            with patch('sys.stdout', new_callable=io.StringIO):
                main()
        
        mock_build_deck.assert_called_once()
    
    @patch('mtg_deck_builder.cli.list_available_commanders')
    def test_main_list_commanders_mode(self, mock_list_commanders):
        """Test main function in list commanders mode."""
        test_args = ['mtg-deck-builder', '--list-commanders', self.sample_csv]
        
        with patch('sys.argv', test_args):
            with patch('sys.stdout', new_callable=io.StringIO):
                main()
        
        mock_list_commanders.assert_called_once_with(self.sample_csv)
    
    def test_main_keyboard_interrupt(self):
        """Test main function handling of keyboard interrupt."""
        test_args = ['mtg-deck-builder', self.sample_csv, 'Test Commander']
        
        with patch('sys.argv', test_args):
            with patch('mtg_deck_builder.cli.build_commander_deck', side_effect=KeyboardInterrupt):
                with patch('sys.stdout', new_callable=io.StringIO) as mock_stdout:
                    with self.assertRaises(SystemExit) as cm:
                        main()
                    
                    self.assertEqual(cm.exception.code, 1)
                    output = mock_stdout.getvalue()
                    self.assertIn("cancelled by user", output)
    
    def test_main_invalid_arguments(self):
        """Test main function with invalid arguments."""
        test_args = ['mtg-deck-builder', '/nonexistent/file.csv', 'Test Commander']
        
        with patch('sys.argv', test_args):
            with patch('sys.stdout', new_callable=io.StringIO):
                with self.assertRaises(SystemExit) as cm:
                    main()
                
                self.assertEqual(cm.exception.code, 1)


if __name__ == '__main__':
    unittest.main()