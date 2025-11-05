"""
Unit tests for MTG Commander Deck Builder data models.
"""

import unittest
from mtg_deck_builder.models import CardEntry, Deck, DeckStatistics


class TestCardEntry(unittest.TestCase):
    """Test cases for CardEntry dataclass."""
    
    def test_card_entry_creation(self):
        """Test basic CardEntry creation and field assignment."""
        card = CardEntry(name="Lightning Bolt", quantity=1, set_code="M21")
        
        self.assertEqual(card.name, "Lightning Bolt")
        self.assertEqual(card.quantity, 1)
        self.assertEqual(card.set_code, "M21")
        self.assertEqual(card.normalized_name, "lightning bolt")
    
    def test_card_name_normalization(self):
        """Test card name normalization functionality."""
        # Test basic normalization
        card1 = CardEntry(name="  Lightning   Bolt  ", quantity=1)
        self.assertEqual(card1.normalized_name, "lightning bolt")
        
        # Test parenthetical removal
        card2 = CardEntry(name="Jace, the Mind Sculptor (Promo)", quantity=1)
        self.assertEqual(card2.normalized_name, "jace, the mind sculptor")
        
        # Test double-faced card handling
        card3 = CardEntry(name="Delver of Secrets // Insectile Aberration", quantity=1)
        self.assertEqual(card3.normalized_name, "delver of secrets")
        
        # Test case insensitivity
        card4 = CardEntry(name="COUNTERSPELL", quantity=1)
        self.assertEqual(card4.normalized_name, "counterspell")
    
    def test_card_entry_without_set_code(self):
        """Test CardEntry creation without set code."""
        card = CardEntry(name="Sol Ring", quantity=1)
        
        self.assertEqual(card.name, "Sol Ring")
        self.assertEqual(card.quantity, 1)
        self.assertEqual(card.set_code, "")
        self.assertEqual(card.normalized_name, "sol ring")


class TestDeck(unittest.TestCase):
    """Test cases for Deck dataclass."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.deck = Deck(commander="Atraxa, Praetors' Voice")
    
    def test_deck_creation(self):
        """Test basic Deck creation."""
        self.assertEqual(self.deck.commander, "Atraxa, Praetors' Voice")
        self.assertEqual(len(self.deck.cards), 0)
        self.assertEqual(self.deck.total_cards, 1)  # Commander counts as 1
    
    def test_deck_with_initial_cards(self):
        """Test Deck creation with initial card list."""
        initial_cards = ["Sol Ring", "Command Tower", "Counterspell"]
        deck = Deck(commander="Jace, Vryn's Prodigy", cards=initial_cards)
        
        self.assertEqual(len(deck.cards), 3)
        self.assertEqual(deck.total_cards, 4)  # 3 cards + commander
    
    def test_commander_removed_from_cards_list(self):
        """Test that commander is automatically removed from cards list."""
        commander = "Atraxa, Praetors' Voice"
        initial_cards = ["Sol Ring", commander, "Counterspell"]
        deck = Deck(commander=commander, cards=initial_cards)
        
        self.assertNotIn(commander, deck.cards)
        self.assertEqual(len(deck.cards), 2)
    
    def test_add_card_success(self):
        """Test successful card addition."""
        result = self.deck.add_card("Sol Ring")
        
        self.assertTrue(result)
        self.assertIn("Sol Ring", self.deck.cards)
        self.assertEqual(self.deck.total_cards, 2)
    
    def test_add_card_singleton_violation(self):
        """Test singleton rule enforcement."""
        self.deck.add_card("Sol Ring")
        result = self.deck.add_card("Sol Ring")  # Try to add duplicate
        
        self.assertFalse(result)
        self.assertEqual(self.deck.cards.count("Sol Ring"), 1)
    
    def test_add_basic_land_multiple_copies(self):
        """Test that basic lands can be added multiple times."""
        result1 = self.deck.add_card("Forest")
        result2 = self.deck.add_card("Forest")
        result3 = self.deck.add_card("Plains")
        
        self.assertTrue(result1)
        self.assertTrue(result2)
        self.assertTrue(result3)
        self.assertEqual(self.deck.cards.count("Forest"), 2)
    
    def test_add_commander_as_card_fails(self):
        """Test that commander cannot be added to cards list."""
        result = self.deck.add_card(self.deck.commander)
        
        self.assertFalse(result)
        self.assertNotIn(self.deck.commander, self.deck.cards)
    
    def test_card_names_property(self):
        """Test card_names property returns unique card names."""
        self.deck.cards = ["Sol Ring", "Forest", "Forest", "Counterspell"]
        card_names = self.deck.card_names
        
        self.assertEqual(len(card_names), 3)
        self.assertIn("Sol Ring", card_names)
        self.assertIn("Forest", card_names)
        self.assertIn("Counterspell", card_names)
    
    def test_is_basic_land(self):
        """Test basic land identification."""
        self.assertTrue(self.deck._is_basic_land("Forest"))
        self.assertTrue(self.deck._is_basic_land("PLAINS"))  # Case insensitive
        self.assertTrue(self.deck._is_basic_land("Snow-Covered Mountain"))
        self.assertFalse(self.deck._is_basic_land("Command Tower"))
        self.assertFalse(self.deck._is_basic_land("Sol Ring"))


class TestDeckValidation(unittest.TestCase):
    """Test cases for Deck validation methods."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.deck = Deck(commander="Atraxa, Praetors' Voice")
    
    def test_validate_card_count_valid(self):
        """Test card count validation with exactly 100 cards."""
        # Add 99 cards to make total 100 (including commander)
        for i in range(99):
            self.deck.cards.append(f"Card {i}")
        
        self.assertTrue(self.deck._validate_card_count())
        self.assertEqual(self.deck.total_cards, 100)
    
    def test_validate_card_count_invalid(self):
        """Test card count validation with incorrect number of cards."""
        # Add only 50 cards
        for i in range(50):
            self.deck.cards.append(f"Card {i}")
        
        self.assertFalse(self.deck._validate_card_count())
        self.assertEqual(self.deck.total_cards, 51)  # 50 + commander
    
    def test_validate_singleton_rule_valid(self):
        """Test singleton rule validation with no duplicates."""
        self.deck.cards = ["Sol Ring", "Counterspell", "Lightning Bolt", "Forest", "Forest"]
        
        self.assertTrue(self.deck._validate_singleton_rule())
    
    def test_validate_singleton_rule_invalid(self):
        """Test singleton rule validation with duplicates."""
        self.deck.cards = ["Sol Ring", "Sol Ring", "Counterspell"]
        
        self.assertFalse(self.deck._validate_singleton_rule())
    
    def test_validate_commander_legality_valid(self):
        """Test commander legality validation with valid commander."""
        self.assertTrue(self.deck._validate_commander_legality())
    
    def test_validate_commander_legality_invalid(self):
        """Test commander legality validation with invalid commander."""
        self.deck.commander = ""
        self.assertFalse(self.deck._validate_commander_legality())
        
        self.deck.commander = "   "
        self.assertFalse(self.deck._validate_commander_legality())
    
    def test_validate_color_identity(self):
        """Test color identity validation (simplified)."""
        # Currently returns True as it's a placeholder
        self.assertTrue(self.deck._validate_color_identity())
    
    def test_full_validation_valid_deck(self):
        """Test full validation with a valid deck."""
        # Create a valid 100-card deck
        for i in range(99):
            self.deck.cards.append(f"Card {i}")
        
        validation_results = self.deck.validate()
        
        self.assertTrue(validation_results['card_count'])
        self.assertTrue(validation_results['singleton_rule'])
        self.assertTrue(validation_results['color_identity'])
        self.assertTrue(validation_results['commander_legal'])
        self.assertTrue(self.deck.is_valid())
    
    def test_full_validation_invalid_deck(self):
        """Test full validation with an invalid deck."""
        # Create deck with duplicates and wrong card count
        self.deck.cards = ["Sol Ring", "Sol Ring", "Counterspell"]
        
        validation_results = self.deck.validate()
        
        self.assertFalse(validation_results['card_count'])
        self.assertFalse(validation_results['singleton_rule'])
        self.assertFalse(self.deck.is_valid())
    
    def test_get_validation_errors(self):
        """Test validation error message generation."""
        # Create deck with multiple issues
        self.deck.cards = ["Sol Ring", "Sol Ring"]  # Wrong count + duplicates
        
        errors = self.deck.get_validation_errors()
        
        self.assertGreater(len(errors), 0)
        self.assertTrue(any("100 cards" in error for error in errors))
        self.assertTrue(any("singleton rule" in error for error in errors))


class TestDeckStatistics(unittest.TestCase):
    """Test cases for DeckStatistics dataclass."""
    
    def test_deck_statistics_creation(self):
        """Test basic DeckStatistics creation."""
        stats = DeckStatistics()
        
        # Check default values are set
        self.assertIn('creature', stats.card_types)
        self.assertIn('land', stats.card_types)
        self.assertEqual(stats.card_types['creature'], 0)
        self.assertEqual(stats.average_cmc, 0.0)
        self.assertEqual(stats.synergy_score, 0.0)
    
    def test_deck_statistics_with_data(self):
        """Test DeckStatistics with actual data."""
        card_types = {'creature': 25, 'instant': 10, 'land': 35}
        mana_curve = {1: 5, 2: 8, 3: 12, 4: 10}
        
        stats = DeckStatistics(
            card_types=card_types,
            mana_curve=mana_curve,
            total_cards=100,
            average_cmc=2.8
        )
        
        self.assertEqual(stats.card_types['creature'], 25)
        self.assertEqual(stats.mana_curve[3], 12)
        self.assertEqual(stats.total_cards, 100)
        self.assertEqual(stats.average_cmc, 2.8)
    
    def test_creature_percentage(self):
        """Test creature percentage calculation."""
        stats = DeckStatistics(
            card_types={'creature': 30, 'land': 35, 'instant': 35},
            total_cards=100
        )
        
        self.assertEqual(stats.creature_percentage, 30.0)
    
    def test_land_percentage(self):
        """Test land percentage calculation."""
        stats = DeckStatistics(
            card_types={'creature': 30, 'land': 35, 'instant': 35},
            total_cards=100
        )
        
        self.assertEqual(stats.land_percentage, 35.0)
    
    def test_percentage_with_zero_cards(self):
        """Test percentage calculations with zero total cards."""
        stats = DeckStatistics(total_cards=0)
        
        self.assertEqual(stats.creature_percentage, 0.0)
        self.assertEqual(stats.land_percentage, 0.0)


if __name__ == '__main__':
    unittest.main()