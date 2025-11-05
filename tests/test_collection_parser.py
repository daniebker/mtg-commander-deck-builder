"""
Unit tests for MTG Commander Deck Builder collection parser.
"""

import unittest
import tempfile
import os
from pathlib import Path
from mtg_deck_builder.collection_parser import (
    CollectionParser, CollectionParseError, CommanderNotFoundError
)
from mtg_deck_builder.models import CardEntry


class TestCollectionParser(unittest.TestCase):
    """Test cases for CollectionParser class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.parser = CollectionParser()
        self.temp_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        """Clean up test fixtures."""
        # Clean up temporary files
        for file in Path(self.temp_dir).glob("*"):
            file.unlink()
        os.rmdir(self.temp_dir)
    
    def create_temp_csv(self, content: str, filename: str = "test.csv") -> str:
        """Create a temporary CSV file with given content."""
        file_path = os.path.join(self.temp_dir, filename)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return file_path


class TestCSVParsing(TestCollectionParser):
    """Test cases for CSV parsing functionality."""
    
    def test_load_collection_basic_csv(self):
        """Test loading a basic CSV file."""
        csv_content = """name,quantity,set
Lightning Bolt,4,M21
Sol Ring,1,C20
Forest,10,BFZ"""
        
        csv_path = self.create_temp_csv(csv_content)
        collection = self.parser.load_collection(csv_path)
        
        self.assertEqual(len(collection), 3)
        self.assertIn("lightning bolt", collection)
        self.assertIn("sol ring", collection)
        self.assertIn("forest", collection)
        
        # Check card details
        lightning_bolt = collection["lightning bolt"]
        self.assertEqual(lightning_bolt.name, "Lightning Bolt")
        self.assertEqual(lightning_bolt.quantity, 4)
        self.assertEqual(lightning_bolt.set_code, "M21")
    
    def test_load_collection_different_headers(self):
        """Test CSV parsing with different column headers."""
        csv_content = """card_name,qty,edition
Counterspell,2,7ED
Command Tower,1,C13"""
        
        csv_path = self.create_temp_csv(csv_content)
        collection = self.parser.load_collection(csv_path)
        
        self.assertEqual(len(collection), 2)
        self.assertIn("counterspell", collection)
        self.assertEqual(collection["counterspell"].quantity, 2)
    
    def test_load_collection_semicolon_delimiter(self):
        """Test CSV parsing with semicolon delimiter."""
        csv_content = """name;quantity;set
Brainstorm;3;ICE
Ponder;2;M12"""
        
        csv_path = self.create_temp_csv(csv_content)
        collection = self.parser.load_collection(csv_path)
        
        self.assertEqual(len(collection), 2)
        self.assertIn("brainstorm", collection)
        self.assertEqual(collection["brainstorm"].quantity, 3)
    
    def test_load_collection_tab_delimiter(self):
        """Test CSV parsing with tab delimiter."""
        csv_content = "name\tquantity\tset\nPreordain\t1\tM11\nOpt\t4\tXLN"
        
        csv_path = self.create_temp_csv(csv_content)
        collection = self.parser.load_collection(csv_path)
        
        self.assertEqual(len(collection), 2)
        self.assertIn("preordain", collection)
    
    def test_load_collection_missing_quantity_defaults_to_one(self):
        """Test that missing quantity defaults to 1."""
        csv_content = """name,set
Ancestral Recall,LEA
Black Lotus,LEA"""
        
        csv_path = self.create_temp_csv(csv_content)
        collection = self.parser.load_collection(csv_path)
        
        self.assertEqual(collection["ancestral recall"].quantity, 1)
        self.assertEqual(collection["black lotus"].quantity, 1)
    
    def test_load_collection_duplicate_cards_combine_quantities(self):
        """Test that duplicate card entries combine quantities."""
        csv_content = """name,quantity,set
Lightning Bolt,2,M21
Lightning Bolt,1,M20
Lightning Bolt,1,LEA"""
        
        csv_path = self.create_temp_csv(csv_content)
        collection = self.parser.load_collection(csv_path)
        
        self.assertEqual(len(collection), 1)
        self.assertEqual(collection["lightning bolt"].quantity, 4)
    
    def test_load_collection_empty_rows_skipped(self):
        """Test that empty rows are skipped."""
        csv_content = """name,quantity,set
Lightning Bolt,1,M21

Sol Ring,1,C20
,2,M21
Forest,5,BFZ"""
        
        csv_path = self.create_temp_csv(csv_content)
        collection = self.parser.load_collection(csv_path)
        
        self.assertEqual(len(collection), 3)
        self.assertIn("lightning bolt", collection)
        self.assertIn("sol ring", collection)
        self.assertIn("forest", collection)
    
    def test_load_collection_file_not_found(self):
        """Test error handling for missing file."""
        with self.assertRaises(FileNotFoundError):
            self.parser.load_collection("nonexistent.csv")
    
    def test_load_collection_invalid_quantity(self):
        """Test error handling for invalid quantity values."""
        csv_content = """name,quantity,set
Lightning Bolt,invalid,M21"""
        
        csv_path = self.create_temp_csv(csv_content)
        
        with self.assertRaises(CollectionParseError) as context:
            self.parser.load_collection(csv_path)
        
        self.assertIn("Invalid quantity format", str(context.exception))
    
    def test_load_collection_negative_quantity(self):
        """Test error handling for negative quantities."""
        csv_content = """name,quantity,set
Lightning Bolt,-1,M21"""
        
        csv_path = self.create_temp_csv(csv_content)
        
        with self.assertRaises(CollectionParseError) as context:
            self.parser.load_collection(csv_path)
        
        self.assertIn("must be positive", str(context.exception))
    
    def test_load_collection_float_quantity_converted(self):
        """Test that float quantities are converted to integers."""
        csv_content = """name,quantity,set
Lightning Bolt,4.0,M21
Sol Ring,1.5,C20"""
        
        csv_path = self.create_temp_csv(csv_content)
        collection = self.parser.load_collection(csv_path)
        
        self.assertEqual(collection["lightning bolt"].quantity, 4)
        self.assertEqual(collection["sol ring"].quantity, 1)  # 1.5 -> 1
    
    def test_load_collection_empty_file(self):
        """Test error handling for empty CSV file."""
        csv_path = self.create_temp_csv("")
        
        with self.assertRaises(CollectionParseError) as context:
            self.parser.load_collection(csv_path)
        
        # Empty file will fail at header identification stage
        self.assertIn("Could not identify card name column", str(context.exception))


class TestCardNameNormalization(TestCollectionParser):
    """Test cases for card name normalization functionality."""
    
    def test_normalize_card_name_basic(self):
        """Test basic card name normalization."""
        self.assertEqual(
            self.parser.normalize_card_name("Lightning Bolt"),
            "lightning bolt"
        )
        
        self.assertEqual(
            self.parser.normalize_card_name("  COUNTERSPELL  "),
            "counterspell"
        )
    
    def test_normalize_card_name_special_characters(self):
        """Test normalization of special characters."""
        # Smart quotes
        self.assertEqual(
            self.parser.normalize_card_name("Jace's Ingenuity"),
            "jace's ingenuity"
        )
        
        # Æ character
        self.assertEqual(
            self.parser.normalize_card_name("Ætherling"),
            "aetherling"
        )
        
        # Various dashes
        self.assertEqual(
            self.parser.normalize_card_name("X–Ray Vision"),
            "x-ray vision"
        )
    
    def test_normalize_card_name_parenthetical_removal(self):
        """Test removal of parenthetical information."""
        self.assertEqual(
            self.parser.normalize_card_name("Jace, the Mind Sculptor (Promo)"),
            "jace, the mind sculptor"
        )
        
        self.assertEqual(
            self.parser.normalize_card_name("Lightning Bolt [Foil]"),
            "lightning bolt"
        )
    
    def test_normalize_card_name_double_faced_cards(self):
        """Test handling of double-faced cards."""
        self.assertEqual(
            self.parser.normalize_card_name("Delver of Secrets // Insectile Aberration"),
            "delver of secrets"
        )
        
        self.assertEqual(
            self.parser.normalize_card_name("Huntmaster of the Fells // Ravager of the Fells"),
            "huntmaster of the fells"
        )
    
    def test_normalize_card_name_version_numbers(self):
        """Test removal of version numbers and suffixes."""
        self.assertEqual(
            self.parser.normalize_card_name("Lightning Bolt v2"),
            "lightning bolt"
        )
        
        self.assertEqual(
            self.parser.normalize_card_name("Sol Ring #123"),
            "sol ring"
        )
    
    def test_normalize_card_name_empty_input(self):
        """Test normalization with empty or invalid input."""
        self.assertEqual(self.parser.normalize_card_name(""), "")
        self.assertEqual(self.parser.normalize_card_name(None), "")
        self.assertEqual(self.parser.normalize_card_name("   "), "")
    
    def test_create_name_lookup_table(self):
        """Test creation of name lookup table."""
        collection = {
            "lightning bolt": CardEntry("Lightning Bolt", 1),
            "jace, the mind sculptor": CardEntry("Jace, the Mind Sculptor", 1)
        }
        
        lookup_table = self.parser.create_name_lookup_table(collection)
        
        # Should include original names
        self.assertIn("lightning bolt", lookup_table)
        self.assertIn("jace, the mind sculptor", lookup_table)
        
        # Should include variations
        self.assertIn("lightningbolt", lookup_table)  # No spaces
        
    def test_resolve_card_name_exact_match(self):
        """Test card name resolution with exact matches."""
        collection = {
            "lightning bolt": CardEntry("Lightning Bolt", 1)
        }
        lookup_table = self.parser.create_name_lookup_table(collection)
        
        result = self.parser.resolve_card_name("Lightning Bolt", lookup_table)
        self.assertEqual(result, "lightning bolt")
    
    def test_resolve_card_name_fuzzy_match(self):
        """Test card name resolution with fuzzy matching."""
        collection = {
            "lightning bolt": CardEntry("Lightning Bolt", 1)
        }
        lookup_table = self.parser.create_name_lookup_table(collection)
        
        # Test without punctuation
        result = self.parser.resolve_card_name("lightningbolt", lookup_table)
        self.assertEqual(result, "lightning bolt")
    
    def test_resolve_card_name_no_match(self):
        """Test card name resolution when no match is found."""
        collection = {
            "lightning bolt": CardEntry("Lightning Bolt", 1)
        }
        lookup_table = self.parser.create_name_lookup_table(collection)
        
        result = self.parser.resolve_card_name("Nonexistent Card", lookup_table)
        self.assertIsNone(result)


class TestCommanderValidation(TestCollectionParser):
    """Test cases for commander validation functionality."""
    
    def setUp(self):
        """Set up test fixtures with sample collection."""
        super().setUp()
        self.collection = {
            "atraxa, praetors' voice": CardEntry("Atraxa, Praetors' Voice", 1),
            "edgar markov": CardEntry("Edgar Markov", 1),
            "lightning bolt": CardEntry("Lightning Bolt", 4),
            "sol ring": CardEntry("Sol Ring", 1),
            "forest": CardEntry("Forest", 10)
        }
    
    def test_validate_commander_exists_and_legal(self):
        """Test validation of existing legal commander."""
        result = self.parser.validate_commander("Atraxa, Praetors' Voice", self.collection)
        self.assertTrue(result)
    
    def test_validate_commander_case_insensitive(self):
        """Test commander validation is case insensitive."""
        result = self.parser.validate_commander("ATRAXA, PRAETORS' VOICE", self.collection)
        self.assertTrue(result)
    
    def test_validate_commander_not_found(self):
        """Test validation fails for commander not in collection."""
        with self.assertRaises(CommanderNotFoundError) as context:
            self.parser.validate_commander("Nonexistent Commander", self.collection)
        
        self.assertIn("not found in collection", str(context.exception))
    
    def test_validate_commander_empty_name(self):
        """Test validation fails for empty commander name."""
        with self.assertRaises(CommanderNotFoundError) as context:
            self.parser.validate_commander("", self.collection)
        
        self.assertIn("cannot be empty", str(context.exception))
    
    def test_validate_commander_none_name(self):
        """Test validation fails for None commander name."""
        with self.assertRaises(CommanderNotFoundError) as context:
            self.parser.validate_commander(None, self.collection)
        
        self.assertIn("cannot be empty", str(context.exception))
    
    def test_validate_commander_not_legal(self):
        """Test validation fails for non-legendary creature."""
        with self.assertRaises(CommanderNotFoundError) as context:
            self.parser.validate_commander("Lightning Bolt", self.collection)
        
        self.assertIn("not a legal commander", str(context.exception))
    
    def test_get_commander_from_collection(self):
        """Test retrieving commander CardEntry from collection."""
        commander_entry = self.parser.get_commander_from_collection(
            "Atraxa, Praetors' Voice", self.collection
        )
        
        self.assertIsInstance(commander_entry, CardEntry)
        self.assertEqual(commander_entry.name, "Atraxa, Praetors' Voice")
    
    def test_list_available_commanders(self):
        """Test listing all available commanders in collection."""
        commanders = self.parser.list_available_commanders(self.collection)
        
        self.assertIn("Atraxa, Praetors' Voice", commanders)
        self.assertIn("Edgar Markov", commanders)
        self.assertNotIn("Lightning Bolt", commanders)
        self.assertNotIn("Sol Ring", commanders)
    
    def test_suggest_similar_commanders(self):
        """Test commander name suggestions."""
        suggestions = self.parser._suggest_similar_commanders("Atrax", self.collection)
        
        self.assertIn("Atraxa, Praetors' Voice", suggestions)
    
    def test_is_legal_commander_known_commander(self):
        """Test legal commander check for known commanders."""
        card_entry = CardEntry("Atraxa, Praetors' Voice", 1)
        result = self.parser._is_legal_commander("atraxa, praetors' voice", card_entry)
        self.assertTrue(result)
    
    def test_is_legal_commander_heuristic_patterns(self):
        """Test legal commander check using name patterns."""
        # Test legendary creature patterns
        card_entry = CardEntry("Thalia, Guardian of Thraben", 1)
        result = self.parser._is_legal_commander("thalia, guardian of thraben", card_entry)
        self.assertTrue(result)
        
        # Test planeswalker pattern
        card_entry = CardEntry("Jace, the Mind Sculptor", 1)
        result = self.parser._is_legal_commander("jace, the mind sculptor", card_entry)
        self.assertTrue(result)
    
    def test_is_legal_commander_non_legendary(self):
        """Test legal commander check for non-legendary creatures."""
        card_entry = CardEntry("Lightning Bolt", 1)
        result = self.parser._is_legal_commander("lightning bolt", card_entry)
        self.assertFalse(result)
    
    def test_names_are_similar(self):
        """Test name similarity checking."""
        # Names that contain each other
        self.assertTrue(self.parser._names_are_similar("atraxa", "atraxa, praetors' voice"))
        
        # Names with shared words
        self.assertTrue(self.parser._names_are_similar("jace beleren", "jace, the mind sculptor"))
        
        # Completely different names
        self.assertFalse(self.parser._names_are_similar("lightning bolt", "counterspell"))


class TestEdgeCases(TestCollectionParser):
    """Test cases for edge cases and error conditions."""
    
    def test_load_collection_unicode_characters(self):
        """Test handling of Unicode characters in card names."""
        csv_content = """name,quantity,set
Ætherling,1,DGM
Draconic Roär,1,M19"""
        
        csv_path = self.create_temp_csv(csv_content)
        collection = self.parser.load_collection(csv_path)
        
        # Check that the cards are loaded (normalized names will have special chars converted)
        self.assertEqual(len(collection), 2)
        # The æ should be converted to ae in normalization
        self.assertIn("aetherling", collection)
        self.assertEqual(collection["aetherling"].name, "Ætherling")
    
    def test_load_collection_very_long_card_names(self):
        """Test handling of very long card names."""
        long_name = "A" * 200  # Very long card name
        csv_content = f"""name,quantity,set
{long_name},1,TST"""
        
        csv_path = self.create_temp_csv(csv_content)
        collection = self.parser.load_collection(csv_path)
        
        self.assertEqual(len(collection), 1)
        normalized_long_name = long_name.lower()
        self.assertIn(normalized_long_name, collection)
    
    def test_load_collection_malformed_csv(self):
        """Test handling of malformed CSV files."""
        csv_content = """name,quantity,set
Lightning Bolt,1,M21
"Unclosed quote,2,M20
Sol Ring,1,C20"""
        
        csv_path = self.create_temp_csv(csv_content)
        
        # Should handle malformed CSV gracefully
        try:
            collection = self.parser.load_collection(csv_path)
            # If it succeeds, should have valid entries
            self.assertGreater(len(collection), 0)
        except CollectionParseError:
            # If it fails, should provide meaningful error
            pass
    
    def test_normalize_card_name_complex_cases(self):
        """Test normalization of complex card name cases."""
        # Multiple special characters
        result = self.parser.normalize_card_name("Æther Vial™ (Promo) // Alternate Art")
        self.assertEqual(result, "aether vial")
        
        # Mixed case with numbers
        result = self.parser.normalize_card_name("Jace 2.0, Mind Sculptor v3")
        self.assertEqual(result, "jace 2.0, mind sculptor")


if __name__ == '__main__':
    unittest.main()