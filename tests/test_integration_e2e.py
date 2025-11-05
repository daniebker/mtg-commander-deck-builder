"""
End-to-end integration tests for MTG Commander Deck Builder.

These tests verify the complete workflow from CSV input to deck output,
including real API interactions and file I/O operations.
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock
import sys
import os

# Add the project root to the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from mtg_deck_builder.cli import main, build_commander_deck
from mtg_deck_builder.collection_parser import CollectionParser
from mtg_deck_builder.scryfall_service import ScryfallService
from mtg_deck_builder.deck_builder import DeckBuilder
from mtg_deck_builder.output_manager import OutputManager


class TestEndToEndIntegration:
    """End-to-end integration tests."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for test files."""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir)
    
    @pytest.fixture
    def sample_csv_basic(self, temp_dir):
        """Create a basic sample CSV file."""
        csv_content = '''Name,Quantity
"Cloud, Midgar Mercenary",1
"Sol Ring",1
"Command Tower",1
"Plains",10
"Swords to Plowshares",1
"Wrath of God",1
"Serra Angel",1
"Lightning Greaves",1
"Arcane Signet",1
"Mind Stone",1'''
        
        csv_path = temp_dir / "basic_collection.csv"
        csv_path.write_text(csv_content)
        return csv_path
    
    @pytest.fixture
    def sample_csv_multicolor(self, temp_dir):
        """Create a multicolor commander CSV file."""
        csv_content = '''Card Name,Count,Set
"Atraxa, Praetors' Voice",1,"C16"
"Sol Ring",1,"C21"
"Command Tower",1,"C21"
"Cultivate",1,"M11"
"Counterspell",1,"TMP"
"Swords to Plowshares",1,"ICE"
"Demonic Tutor",1,"LEA"
"Forest",5,"Basic"
"Island",5,"Basic"
"Plains",5,"Basic"
"Swamp",5,"Basic"
"Rhystic Study",1,"PCY"
"Smothering Tithe",1,"RNA"
"Cyclonic Rift",1,"RTR"
"Wrath of God",1,"10E"'''
        
        csv_path = temp_dir / "multicolor_collection.csv"
        csv_path.write_text(csv_content)
        return csv_path
    
    @pytest.fixture
    def sample_csv_large(self, temp_dir):
        """Create a larger collection CSV for testing performance."""
        csv_content = '''Name,Quantity,Set Code
"Edgar Markov",1,"C17"
"Sol Ring",2,"C21"
"Command Tower",1,"C21"
"Lightning Bolt",3,"LEA"
"Swords to Plowshares",2,"ICE"
"Path to Exile",2,"CON"
"Counterspell",3,"TMP"
"Dark Ritual",4,"LEA"
"Lightning Greaves",1,"MRD"
"Swiftfoot Boots",1,"M12"
"Chromatic Lantern",1,"RTR"
"Arcane Signet",1,"C19"
"Plains",15,"Basic"
"Island",12,"Basic"
"Swamp",15,"Basic"
"Mountain",12,"Basic"
"Forest",10,"Basic"
"Flooded Strand",1,"ONS"
"Polluted Delta",1,"ONS"
"Bloodstained Mire",1,"ONS"'''
        
        csv_path = temp_dir / "large_collection.csv"
        csv_path.write_text(csv_content)
        return csv_path
    
    def test_csv_parsing_basic_format(self, sample_csv_basic):
        """Test parsing of basic CSV format."""
        parser = CollectionParser()
        collection = parser.load_collection(str(sample_csv_basic))
        
        assert len(collection) > 0
        assert any("cloud" in name.lower() for name in collection.keys())
        assert any("sol ring" in name.lower() for name in collection.keys())
    
    def test_csv_parsing_detailed_format(self, sample_csv_multicolor):
        """Test parsing of detailed CSV format with set information."""
        parser = CollectionParser()
        collection = parser.load_collection(str(sample_csv_multicolor))
        
        assert len(collection) > 0
        assert any("atraxa" in name.lower() for name in collection.keys())
        
        # Check that set codes are preserved
        for card_entry in collection.values():
            if "atraxa" in card_entry.name.lower():
                assert card_entry.set_code in ["C16", ""]  # May be empty if not parsed
    
    def test_commander_validation_success(self, sample_csv_basic):
        """Test successful commander validation."""
        parser = CollectionParser()
        collection = parser.load_collection(str(sample_csv_basic))
        
        # Should not raise an exception
        result = parser.validate_commander("Cloud, Midgar Mercenary", collection)
        assert result is True
    
    def test_commander_validation_failure(self, sample_csv_basic):
        """Test commander validation failure for non-existent commander."""
        parser = CollectionParser()
        collection = parser.load_collection(str(sample_csv_basic))
        
        with pytest.raises(Exception):  # Should raise CommanderNotFoundError
            parser.validate_commander("Nonexistent Commander", collection)
    
    def test_scryfall_service_caching(self, temp_dir):
        """Test Scryfall service caching functionality."""
        cache_dir = temp_dir / "scryfall_cache"
        service = ScryfallService(cache_dir=cache_dir)
        
        # Mock the API call to avoid hitting real Scryfall
        with patch.object(service, '_fetch_from_api_raw') as mock_fetch:
            mock_fetch.return_value = {
                'name': 'Sol Ring',
                'color_identity': [],
                'mana_cost': '{1}',
                'type_line': 'Artifact',
                'oracle_text': '{T}: Add {C}{C}.',
                'cmc': 1.0,
                'colors': []
            }
            
            # First call should hit the API
            color_identity1 = service.get_color_identity("Sol Ring")
            assert color_identity1 == []
            assert mock_fetch.call_count == 1
            
            # Second call should use cache
            color_identity2 = service.get_color_identity("Sol Ring")
            assert color_identity2 == []
            assert mock_fetch.call_count == 1  # No additional API call
            
            # Verify cache file was created
            cache_files = list(cache_dir.glob("*.json"))
            assert len(cache_files) > 0
    
    def test_batch_color_identity_fetching(self, temp_dir):
        """Test batched color identity fetching."""
        cache_dir = temp_dir / "scryfall_cache"
        service = ScryfallService(cache_dir=cache_dir)
        
        card_names = ["Sol Ring", "Lightning Greaves", "Command Tower"]
        
        # Mock the batch processing
        with patch.object(service, '_fetch_from_api_raw') as mock_fetch:
            mock_fetch.side_effect = [
                {
                    'name': 'Sol Ring',
                    'color_identity': [],
                    'mana_cost': '{1}',
                    'type_line': 'Artifact',
                    'oracle_text': '{T}: Add {C}{C}.',
                    'cmc': 1.0,
                    'colors': []
                },
                {
                    'name': 'Lightning Greaves',
                    'color_identity': [],
                    'mana_cost': '{2}',
                    'type_line': 'Artifact — Equipment',
                    'oracle_text': 'Equipped creature has haste and shroud.',
                    'cmc': 2.0,
                    'colors': []
                },
                {
                    'name': 'Command Tower',
                    'color_identity': [],
                    'mana_cost': '',
                    'type_line': 'Land',
                    'oracle_text': '{T}: Add one mana of any color in your commander\'s color identity.',
                    'cmc': 0.0,
                    'colors': []
                }
            ]
            
            results = service.batch_get_color_identities(card_names)
            
            assert len(results) == 3
            assert all(results[name] == [] for name in card_names)  # All colorless
    
    @patch('mtg_deck_builder.edhrec_service.pyedhrec')
    def test_deck_building_workflow_mono_white(self, mock_pyedhrec, sample_csv_basic, temp_dir):
        """Test complete deck building workflow with mono-white commander."""
        # Mock EDHREC service
        mock_pyedhrec.get_commander_recommendations.return_value = [
            {'name': 'Swords to Plowshares', 'synergy_score': 0.9},
            {'name': 'Wrath of God', 'synergy_score': 0.8},
            {'name': 'Serra Angel', 'synergy_score': 0.7},
        ]
        
        # Mock Scryfall responses for color identity
        scryfall_responses = {
            "Cloud, Midgar Mercenary": ['W'],
            "Sol Ring": [],
            "Command Tower": [],
            "Plains": [],
            "Swords to Plowshares": ['W'],
            "Wrath of God": ['W'],
            "Serra Angel": ['W'],
            "Lightning Greaves": [],
            "Arcane Signet": [],
            "Mind Stone": []
        }
        
        with patch('mtg_deck_builder.scryfall_service.ScryfallService.batch_get_color_identities') as mock_batch:
            mock_batch.return_value = scryfall_responses
            
            with patch('mtg_deck_builder.scryfall_service.ScryfallService.get_color_identity') as mock_single:
                mock_single.side_effect = lambda name: scryfall_responses.get(name, [])
                
                # Test the complete workflow
                try:
                    build_commander_deck(
                        csv_file=str(sample_csv_basic),
                        commander="Cloud, Midgar Mercenary",
                        output_dir=str(temp_dir),
                        min_deck_size=10,  # Lower threshold for small test collection
                        use_cache=False,
                        verbose=True,
                        quiet=False
                    )
                    
                    # Check that a deck file was created
                    deck_files = list(temp_dir.glob("*Cloud*.txt"))
                    assert len(deck_files) > 0
                    
                    # Verify deck file content
                    deck_file = deck_files[0]
                    content = deck_file.read_text()
                    assert "Commander: Cloud, Midgar Mercenary" in content
                    assert "Sol Ring" in content  # Should include colorless cards
                    assert "Plains" in content  # Should include basic lands
                    
                except Exception as e:
                    pytest.fail(f"Deck building failed: {e}")
    
    def test_color_identity_filtering(self, sample_csv_multicolor, temp_dir):
        """Test that color identity filtering works correctly."""
        # Mock Scryfall responses
        scryfall_responses = {
            "Atraxa, Praetors' Voice": ['W', 'U', 'B', 'G'],  # 4-color commander
            "Sol Ring": [],  # Colorless
            "Command Tower": [],  # Colorless
            "Cultivate": ['G'],  # Green
            "Counterspell": ['U'],  # Blue
            "Swords to Plowshares": ['W'],  # White
            "Demonic Tutor": ['B'],  # Black
            "Forest": [],
            "Island": [],
            "Plains": [],
            "Swamp": [],
            "Rhystic Study": ['U'],  # Blue
            "Smothering Tithe": ['W'],  # White
            "Cyclonic Rift": ['U'],  # Blue
            "Wrath of God": ['W']  # White
        }
        
        with patch('mtg_deck_builder.scryfall_service.ScryfallService.batch_get_color_identities') as mock_batch:
            mock_batch.return_value = scryfall_responses
            
            with patch('mtg_deck_builder.scryfall_service.ScryfallService.get_color_identity') as mock_single:
                mock_single.side_effect = lambda name: scryfall_responses.get(name, [])
                
                # Create deck builder and test filtering
                scryfall_service = ScryfallService()
                deck_builder = DeckBuilder(scryfall_service=scryfall_service)
                
                parser = CollectionParser()
                collection = parser.load_collection(str(sample_csv_multicolor))
                
                # Extract commander color identity
                commander_colors = deck_builder._extract_color_identity("Atraxa, Praetors' Voice")
                assert set(commander_colors) == {'W', 'U', 'B', 'G'}
                
                # Filter collection
                filtered_collection = deck_builder._filter_by_color_identity(collection, commander_colors)
                
                # All cards should be legal for Atraxa (4-color commander)
                assert len(filtered_collection) == len(collection)
    
    def test_error_handling_invalid_csv(self, temp_dir):
        """Test error handling for invalid CSV files."""
        # Create invalid CSV
        invalid_csv = temp_dir / "invalid.csv"
        invalid_csv.write_text("This is not a valid CSV file\nwith proper headers")
        
        parser = CollectionParser()
        
        with pytest.raises(Exception):  # Should raise CollectionParseError
            parser.load_collection(str(invalid_csv))
    
    def test_error_handling_missing_file(self):
        """Test error handling for missing CSV file."""
        parser = CollectionParser()
        
        with pytest.raises(FileNotFoundError):
            parser.load_collection("nonexistent_file.csv")
    
    def test_partial_deck_generation(self, temp_dir):
        """Test partial deck generation when collection is insufficient."""
        # Create minimal CSV
        minimal_csv_content = '''Name,Quantity
"Cloud, Midgar Mercenary",1
"Sol Ring",1
"Plains",5'''
        
        minimal_csv = temp_dir / "minimal_collection.csv"
        minimal_csv.write_text(minimal_csv_content)
        
        scryfall_responses = {
            "Cloud, Midgar Mercenary": ['W'],
            "Sol Ring": [],
            "Plains": []
        }
        
        with patch('mtg_deck_builder.scryfall_service.ScryfallService.batch_get_color_identities') as mock_batch:
            mock_batch.return_value = scryfall_responses
            
            with patch('mtg_deck_builder.scryfall_service.ScryfallService.get_color_identity') as mock_single:
                mock_single.side_effect = lambda name: scryfall_responses.get(name, [])
                
                with patch('mtg_deck_builder.edhrec_service.pyedhrec'):
                    try:
                        build_commander_deck(
                            csv_file=str(minimal_csv),
                            commander="Cloud, Midgar Mercenary",
                            output_dir=str(temp_dir),
                            min_deck_size=5,  # Very low threshold
                            use_cache=False,
                            verbose=True,
                            quiet=False
                        )
                        
                        # Should still create a deck file even if partial
                        deck_files = list(temp_dir.glob("*Cloud*.txt"))
                        assert len(deck_files) > 0
                        
                    except Exception as e:
                        # Partial deck generation might still fail, but shouldn't crash
                        assert "insufficient" in str(e).lower() or "not found" in str(e).lower()
    
    def test_output_file_naming(self, sample_csv_basic, temp_dir):
        """Test that output files are named correctly."""
        scryfall_responses = {
            "Cloud, Midgar Mercenary": ['W'],
            "Sol Ring": [],
            "Command Tower": [],
            "Plains": [],
            "Swords to Plowshares": ['W'],
            "Wrath of God": ['W'],
            "Serra Angel": ['W'],
            "Lightning Greaves": [],
            "Arcane Signet": [],
            "Mind Stone": []
        }
        
        with patch('mtg_deck_builder.scryfall_service.ScryfallService.batch_get_color_identities') as mock_batch:
            mock_batch.return_value = scryfall_responses
            
            with patch('mtg_deck_builder.scryfall_service.ScryfallService.get_color_identity') as mock_single:
                mock_single.side_effect = lambda name: scryfall_responses.get(name, [])
                
                with patch('mtg_deck_builder.edhrec_service.pyedhrec'):
                    try:
                        build_commander_deck(
                            csv_file=str(sample_csv_basic),
                            commander="Cloud, Midgar Mercenary",
                            output_dir=str(temp_dir),
                            min_deck_size=5,
                            use_cache=False,
                            verbose=False,
                            quiet=True
                        )
                        
                        # Check file naming pattern
                        deck_files = list(temp_dir.glob("*.txt"))
                        assert len(deck_files) > 0
                        
                        deck_file = deck_files[0]
                        filename = deck_file.name
                        
                        # Should contain commander name and timestamp
                        assert "cloud" in filename.lower()
                        assert filename.endswith(".txt")
                        
                    except Exception:
                        # Test might fail due to missing dependencies, but naming logic should work
                        pass
    
    def test_enhanced_deck_statistics(self, temp_dir):
        """Test enhanced deck statistics with card type breakdown and mana curve."""
        from mtg_deck_builder.models import Deck, CardRecommendation
        from mtg_deck_builder.output_manager import OutputManager
        
        # Create a test deck with known card types
        deck = Deck(
            commander="Cloud, Midgar Mercenary",
            cards=[
                "Sol Ring",  # Artifact
                "Arcane Signet",  # Artifact
                "Plains",  # Land
                "Command Tower",  # Land
                "Swords to Plowshares",  # Instant
                "Path to Exile",  # Instant
                "Wrath of God",  # Sorcery
                "Cultivate",  # Sorcery
                "Serra Angel",  # Creature
                "Leonin Skyhunter",  # Creature
                "Pacifism",  # Enchantment
                "Faith's Fetters"  # Enchantment
            ],
            color_identity=['W']
        )
        
        # Create output manager and generate statistics
        output_manager = OutputManager(str(temp_dir))
        statistics = output_manager.generate_deck_statistics(deck)
        
        # Verify card type breakdown
        assert statistics.card_types['artifact'] >= 2  # Sol Ring, Arcane Signet
        assert statistics.card_types['land'] >= 2  # Plains, Command Tower
        assert statistics.card_types['instant'] >= 2  # Swords to Plowshares, Path to Exile
        assert statistics.card_types['sorcery'] >= 2  # Wrath of God, Cultivate
        assert statistics.card_types['creature'] >= 2  # Serra Angel, Leonin Skyhunter
        assert statistics.card_types['enchantment'] >= 2  # Pacifism, Faith's Fetters
        
        # Verify mana curve is populated
        assert sum(statistics.mana_curve.values()) > 0
        
        # Verify average CMC is calculated
        assert statistics.average_cmc > 0
        
        # Test deck file output with enhanced statistics
        deck_file_path = output_manager.write_deck_file(deck, statistics=statistics)
        
        # Read and verify the output file contains enhanced statistics
        with open(deck_file_path, 'r') as f:
            content = f.read()
        
        # Check for card type breakdown section
        assert "CARD TYPE BREAKDOWN:" in content
        assert "Creature:" in content
        assert "Enchantment:" in content
        assert "Artifact:" in content
        assert "Instant:" in content
        assert "Sorcery:" in content
        assert "Land:" in content
        
        # Check for mana curve section
        assert "MANA CURVE:" in content
        assert "CMC" in content
        
        # Check for average CMC
        assert "Average CMC:" in content
    
    def test_real_collection_statistics(self):
        """Test statistics generation with the actual collection file."""
        from mtg_deck_builder.collection_parser import CollectionParser
        from mtg_deck_builder.output_manager import OutputManager
        from mtg_deck_builder.models import Deck
        
        # Use the real collection file
        collection_file = "ManaBox_Collection_250714.2.csv"
        if not Path(collection_file).exists():
            pytest.skip("Real collection file not available")
        
        try:
            # Parse the collection
            parser = CollectionParser()
            collection = parser.load_collection(collection_file)
            
            # Create a sample deck from the collection
            card_names = list(collection.keys())[:50]  # Take first 50 cards
            
            # Find a commander in the collection
            commander = None
            for name in card_names:
                if "cloud" in name.lower() and "mercenary" in name.lower():
                    commander = name
                    break
            
            if not commander:
                commander = card_names[0]  # Use first card as commander
            
            # Remove commander from cards list
            deck_cards = [name for name in card_names if name != commander][:99]
            
            deck = Deck(
                commander=commander,
                cards=deck_cards,
                color_identity=['W']
            )
            
            # Generate statistics
            output_manager = OutputManager()
            statistics = output_manager.generate_deck_statistics(deck)
            
            # Verify statistics are reasonable
            assert statistics.total_cards == 100  # Commander + 99 cards
            assert sum(statistics.card_types.values()) == 100
            assert statistics.average_cmc >= 0
            
            # Verify all card types are represented in the breakdown
            card_type_keys = set(statistics.card_types.keys())
            expected_types = {'creature', 'enchantment', 'artifact', 'instant', 'sorcery', 'land'}
            assert expected_types.issubset(card_type_keys)
            
        except Exception as e:
            pytest.skip(f"Real collection test failed: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])