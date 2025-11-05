"""
Data models for MTG Commander Deck Builder.

This module contains the core data structures used throughout the application,
including CardEntry, Deck, and DeckStatistics classes.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Set
import re


@dataclass
class CardEntry:
    """Represents a single card in a collection with metadata."""
    name: str
    quantity: int
    set_code: str = ""
    normalized_name: str = field(init=False)
    
    def __post_init__(self):
        """Automatically normalize the card name after initialization."""
        self.normalized_name = self._normalize_name(self.name)
    
    def _normalize_name(self, name: str) -> str:
        """
        Normalize card name for consistent lookups.
        
        Args:
            name: Raw card name from collection
            
        Returns:
            Normalized card name
        """
        # Remove extra whitespace and convert to lowercase
        normalized = re.sub(r'\s+', ' ', name.strip().lower())
        
        # Remove common suffixes and prefixes that cause lookup issues
        normalized = re.sub(r'\s*\([^)]*\)$', '', normalized)  # Remove parenthetical info
        normalized = re.sub(r'\s*//.*$', '', normalized)  # Remove double-faced card back names
        
        return normalized


@dataclass
class Deck:
    """Represents a complete Commander deck with validation."""
    commander: str
    cards: List[str] = field(default_factory=list)
    color_identity: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        """Ensure cards list doesn't include the commander."""
        if self.commander in self.cards:
            self.cards.remove(self.commander)
    
    @property
    def total_cards(self) -> int:
        """Total number of cards including commander."""
        return len(self.cards) + 1  # +1 for commander
    
    @property
    def card_names(self) -> Set[str]:
        """Set of all unique card names in the deck (excluding commander)."""
        return set(self.cards)
    
    def add_card(self, card_name: str) -> bool:
        """
        Add a card to the deck if it doesn't violate singleton rule.
        
        Args:
            card_name: Name of card to add
            
        Returns:
            True if card was added, False if it would violate singleton rule
        """
        if card_name == self.commander:
            return False  # Commander is already included
        
        if card_name in self.cards and not self._is_basic_land(card_name):
            return False  # Singleton rule violation
        
        if self.total_cards >= 100:
            return False  # Deck is full
        
        self.cards.append(card_name)
        return True
    
    def _is_basic_land(self, card_name: str) -> bool:
        """Check if a card is a basic land (exempt from singleton rule)."""
        basic_lands = {
            'plains', 'island', 'swamp', 'mountain', 'forest',
            'wastes', 'snow-covered plains', 'snow-covered island',
            'snow-covered swamp', 'snow-covered mountain', 'snow-covered forest'
        }
        return card_name.lower() in basic_lands
    
    def validate(self) -> Dict[str, bool]:
        """
        Validate the deck against Commander format rules.
        
        Returns:
            Dictionary with validation results for different rules
        """
        validation_results = {
            'card_count': self._validate_card_count(),
            'singleton_rule': self._validate_singleton_rule(),
            'color_identity': self._validate_color_identity(),
            'commander_legal': self._validate_commander_legality()
        }
        return validation_results
    
    def is_valid(self) -> bool:
        """Check if deck passes all validation rules."""
        validation_results = self.validate()
        return all(validation_results.values())
    
    def _validate_card_count(self) -> bool:
        """Validate that deck has exactly 100 cards."""
        return self.total_cards == 100
    
    def _validate_singleton_rule(self) -> bool:
        """Validate singleton rule (no duplicates except basic lands)."""
        card_counts = {}
        
        # Count occurrences of each card
        for card in self.cards:
            normalized_name = card.lower()
            card_counts[normalized_name] = card_counts.get(normalized_name, 0) + 1
        
        # Check for violations (more than 1 copy of non-basic lands)
        for card_name, count in card_counts.items():
            if count > 1 and not self._is_basic_land(card_name):
                return False
        
        return True
    
    def _validate_color_identity(self) -> bool:
        """
        Validate that all cards respect the commander's color identity.
        
        Note: This is a simplified validation. In a full implementation,
        this would require card database lookups to check mana costs and rules text.
        """
        if not self.color_identity:
            return True  # No restrictions if color identity not set
        
        # For now, return True as we don't have card database integration
        # In full implementation, this would check each card's color identity
        # against the commander's color identity
        return True
    
    def _validate_commander_legality(self) -> bool:
        """
        Validate that the commander is legal for Commander format.
        
        Note: This is a simplified validation. In a full implementation,
        this would check if the commander is a legendary creature or
        has specific rules text allowing it to be a commander.
        """
        if not self.commander:
            return False
        
        # Basic check - commander name should not be empty
        return len(self.commander.strip()) > 0
    
    def get_validation_errors(self) -> List[str]:
        """Get list of validation error messages."""
        errors = []
        validation_results = self.validate()
        
        if not validation_results['card_count']:
            errors.append(f"Deck must have exactly 100 cards (currently has {self.total_cards})")
        
        if not validation_results['singleton_rule']:
            errors.append("Deck violates singleton rule (duplicate non-basic lands found)")
        
        if not validation_results['color_identity']:
            errors.append("Deck contains cards outside commander's color identity")
        
        if not validation_results['commander_legal']:
            errors.append("Commander is not legal for Commander format")
        
        return errors


@dataclass
class CardRecommendation:
    """Represents a card recommendation from EDHREC API."""
    name: str
    synergy_score: float
    category: str = "synergy"  # 'staple', 'synergy', 'budget', etc.
    inclusion_percentage: float = 0.0
    
    def __post_init__(self):
        """Validate synergy score and inclusion percentage ranges."""
        self.synergy_score = max(0.0, min(1.0, self.synergy_score))
        self.inclusion_percentage = max(0.0, min(100.0, self.inclusion_percentage))


@dataclass
class DeckStatistics:
    """Statistics and analysis data for a deck."""
    card_types: Dict[str, int] = field(default_factory=dict)
    mana_curve: Dict[int, int] = field(default_factory=dict)
    color_distribution: Dict[str, int] = field(default_factory=dict)
    average_cmc: float = 0.0
    synergy_score: float = 0.0
    total_cards: int = 0
    
    def __post_init__(self):
        """Initialize default values for dictionaries."""
        if not self.card_types:
            self.card_types = {
                'creature': 0,
                'instant': 0,
                'sorcery': 0,
                'artifact': 0,
                'enchantment': 0,
                'planeswalker': 0,
                'land': 0
            }
        
        if not self.mana_curve:
            self.mana_curve = {i: 0 for i in range(0, 16)}  # CMC 0-15+
        
        if not self.color_distribution:
            self.color_distribution = {
                'white': 0,
                'blue': 0,
                'black': 0,
                'red': 0,
                'green': 0,
                'colorless': 0
            }
    
    @property
    def creature_percentage(self) -> float:
        """Percentage of creatures in the deck."""
        if self.total_cards == 0:
            return 0.0
        return (self.card_types.get('creature', 0) / self.total_cards) * 100
    
    @property
    def land_percentage(self) -> float:
        """Percentage of lands in the deck."""
        if self.total_cards == 0:
            return 0.0
        return (self.card_types.get('land', 0) / self.total_cards) * 100