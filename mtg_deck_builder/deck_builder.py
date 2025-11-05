"""
Core deck building engine for generating Commander decks.

This module contains the main deck building algorithm that orchestrates
the entire deck generation process using EDHREC recommendations and
collection availability.
"""

import logging
from typing import Dict, List, Set, Tuple, Optional
from dataclasses import dataclass
from .models import Deck, CardEntry, CardRecommendation, DeckStatistics
from .scryfall_service import ScryfallService


@dataclass
class DeckBuildingConfig:
    """Configuration parameters for deck building algorithm."""
    MIN_LANDS = 35
    MAX_LANDS = 40
    PREFERRED_CREATURE_COUNT = 25
    PREFERRED_NONCREATURE_SPELLS = 35
    SYNERGY_WEIGHT = 0.7
    AVAILABILITY_WEIGHT = 0.3
    TARGET_DECK_SIZE = 99  # Excluding commander
    
    # Card type overrides (None means use strategy-based defaults)
    creature_count: Optional[int] = None
    instant_count: Optional[int] = None
    sorcery_count: Optional[int] = None
    artifact_count: Optional[int] = None
    enchantment_count: Optional[int] = None
    land_count: Optional[int] = None
    
    # Deck building strategy
    strategy: str = 'balanced'  # 'balanced', 'aggro', 'control', 'combo', 'ramp'
    
    def get_strategy_ratios(self) -> Dict[str, float]:
        """
        Get card type ratios based on the selected strategy.
        
        Returns:
            Dictionary mapping card types to target ratios (0.0 to 1.0)
        """
        strategies = {
            'balanced': {
                'creature': 0.30,      # 30% creatures
                'instant': 0.12,       # 12% instants
                'sorcery': 0.12,       # 12% sorceries
                'artifact': 0.15,      # 15% artifacts (including ramp)
                'enchantment': 0.08,   # 8% enchantments
                'land': 0.38,          # 38% lands
            },
            'aggro': {
                'creature': 0.45,      # 45% creatures (aggressive)
                'instant': 0.15,       # 15% instants (protection/removal)
                'sorcery': 0.08,       # 8% sorceries
                'artifact': 0.10,      # 10% artifacts
                'enchantment': 0.05,   # 5% enchantments
                'land': 0.35,          # 35% lands (lower curve)
            },
            'control': {
                'creature': 0.15,      # 15% creatures (few but powerful)
                'instant': 0.25,       # 25% instants (counterspells, removal)
                'sorcery': 0.20,       # 20% sorceries (board wipes, card draw)
                'artifact': 0.12,      # 12% artifacts
                'enchantment': 0.10,   # 10% enchantments
                'land': 0.40,          # 40% lands (higher curve)
            },
            'combo': {
                'creature': 0.20,      # 20% creatures (combo pieces)
                'instant': 0.20,       # 20% instants (protection, tutors)
                'sorcery': 0.18,       # 18% sorceries (tutors, setup)
                'artifact': 0.15,      # 15% artifacts (combo pieces)
                'enchantment': 0.12,   # 12% enchantments (combo pieces)
                'land': 0.37,          # 37% lands
            },
            'ramp': {
                'creature': 0.25,      # 25% creatures (big threats)
                'instant': 0.10,       # 10% instants
                'sorcery': 0.15,       # 15% sorceries (ramp spells)
                'artifact': 0.20,      # 20% artifacts (mana rocks)
                'enchantment': 0.08,   # 8% enchantments
                'land': 0.42,          # 42% lands (ramp targets)
            }
        }
        
        return strategies.get(self.strategy, strategies['balanced'])
    
    def get_target_counts(self, total_nonland_cards: int = 62) -> Dict[str, int]:
        """
        Get target card counts based on strategy and overrides.
        
        Args:
            total_nonland_cards: Number of non-land cards in deck (default: 62 for 37 lands)
            
        Returns:
            Dictionary mapping card types to target counts
        """
        ratios = self.get_strategy_ratios()
        
        # Calculate base counts from ratios
        base_counts = {}
        remaining_cards = total_nonland_cards
        
        # Handle land count first (it affects the total non-land cards)
        if self.land_count is not None:
            base_counts['land'] = self.land_count
            total_nonland_cards = self.TARGET_DECK_SIZE - self.land_count
        else:
            base_counts['land'] = int(self.TARGET_DECK_SIZE * ratios['land'])
            total_nonland_cards = self.TARGET_DECK_SIZE - base_counts['land']
        
        # Calculate non-land card counts
        nonland_types = ['creature', 'instant', 'sorcery', 'artifact', 'enchantment']
        
        for card_type in nonland_types:
            override_attr = f"{card_type}_count"
            if hasattr(self, override_attr) and getattr(self, override_attr) is not None:
                # Use override value
                base_counts[card_type] = getattr(self, override_attr)
            else:
                # Calculate from ratio
                type_ratio = ratios[card_type] / sum(ratios[t] for t in nonland_types)
                base_counts[card_type] = int(total_nonland_cards * type_ratio)
        
        # Ensure total doesn't exceed deck size
        total_specified = sum(base_counts.values())
        if total_specified > self.TARGET_DECK_SIZE:
            # Proportionally reduce non-override counts
            excess = total_specified - self.TARGET_DECK_SIZE
            # This is a simplified adjustment - in practice, you might want more sophisticated balancing
            base_counts['creature'] = max(0, base_counts['creature'] - excess)
        
        return base_counts


class DeckBuilder:
    """Main deck building engine that generates Commander decks."""
    
    def __init__(self, config: Optional[DeckBuildingConfig] = None, scryfall_service: Optional[ScryfallService] = None):
        """
        Initialize the deck builder with configuration.
        
        Args:
            config: Optional configuration parameters
            scryfall_service: Optional Scryfall service for card data
        """
        self.config = config or DeckBuildingConfig()
        self.scryfall = scryfall_service or ScryfallService()
        self.logger = logging.getLogger(__name__)
    
    def build_deck(
        self, 
        commander: str, 
        collection: Dict[str, CardEntry], 
        recommendations: List[CardRecommendation]
    ) -> Deck:
        """
        Main deck building method that orchestrates the entire process.
        
        Args:
            commander: Name of the commander card
            collection: Dictionary of available cards
            recommendations: List of EDHREC recommendations
            
        Returns:
            Generated Deck object
            
        Raises:
            ValueError: If commander not found in collection or insufficient cards
        """
        self.logger.info(f"Starting deck build for commander: {commander}")
        
        # Validate commander exists in collection
        if not self._validate_commander_in_collection(commander, collection):
            raise ValueError(f"Commander '{commander}' not found in collection")
        
        # Extract commander's color identity
        color_identity = self._extract_color_identity(commander)
        
        # Create initial deck with commander
        deck = Deck(commander=commander, color_identity=color_identity)
        
        # Filter collection by color identity restrictions
        available_cards = self._filter_by_color_identity(collection, color_identity)
        
        # Filter out cards that are not legal in Commander format
        available_cards = self._filter_by_commander_legality(available_cards)
        
        # Remove commander from available cards to prevent duplication
        available_cards = {k: v for k, v in available_cards.items() 
                          if v.normalized_name != commander.lower()}
        
        self.logger.info(f"Available cards after filtering: {len(available_cards)}")
        
        # Build recommendation lookup for faster access
        rec_lookup = {rec.name.lower(): rec for rec in recommendations}
        
        # Select cards using algorithm
        selected_cards = self._select_cards_for_deck(
            available_cards, rec_lookup, deck
        )
        
        # Add selected cards to deck
        for card_name in selected_cards:
            deck.add_card(card_name)
        
        self.logger.info(f"Deck building complete. Total cards: {deck.total_cards}")
        return deck
    
    def _validate_commander_in_collection(
        self, 
        commander: str, 
        collection: Dict[str, CardEntry]
    ) -> bool:
        """
        Validate that the commander exists in the collection.
        
        Args:
            commander: Commander name to validate
            collection: Card collection to search
            
        Returns:
            True if commander found, False otherwise
        """
        commander_normalized = commander.lower()
        for card_entry in collection.values():
            if card_entry.normalized_name == commander_normalized:
                return True
        return False
    
    def _extract_color_identity(self, commander: str) -> List[str]:
        """
        Extract color identity from commander using Scryfall API.
        
        Args:
            commander: Commander name
            
        Returns:
            List of colors in the commander's identity
        """
        self.logger.info(f"Extracting color identity for commander: {commander}")
        
        # Get color identity from Scryfall
        color_identity = self.scryfall.get_color_identity(commander)
        
        # If no color identity found, assume colorless
        if not color_identity:
            color_identity = []
            self.logger.warning(f"No color identity found for '{commander}', assuming colorless")
        
        self.logger.info(f"Color identity for '{commander}': {color_identity}")
        return color_identity
    
    def _filter_by_color_identity(
        self, 
        collection: Dict[str, CardEntry], 
        color_identity: List[str]
    ) -> Dict[str, CardEntry]:
        """
        Filter collection cards by commander's color identity restrictions.
        
        Args:
            collection: Full card collection
            color_identity: Commander's color identity
            
        Returns:
            Filtered collection of legal cards
        """
        self.logger.info(f"Filtering {len(collection)} cards by color identity: {color_identity}")
        
        # Convert commander color identity to set for faster lookup
        commander_colors = set(color_identity)
        
        # Get all card names for batch processing
        card_names = [card_entry.name for card_entry in collection.values()]
        
        # Batch fetch color identities from Scryfall
        self.logger.info("Fetching color identities from Scryfall...")
        card_color_identities = self.scryfall.batch_get_color_identities(card_names)
        
        filtered_collection = {}
        excluded_count = 0
        
        for normalized_name, card_entry in collection.items():
            # Get card's color identity from batch results
            card_color_identity = card_color_identities.get(card_entry.name, [])
            
            # Check if card's color identity is subset of commander's
            card_colors = set(card_color_identity) if card_color_identity else set()
            
            # Card is legal if all its colors are in the commander's color identity
            if card_colors.issubset(commander_colors) or not card_colors:  # Empty set means colorless
                filtered_collection[normalized_name] = card_entry
            else:
                excluded_count += 1
                self.logger.debug(f"Excluded '{card_entry.name}' - colors {card_color_identity} not in commander identity {color_identity}")
        
        self.logger.info(f"Filtered collection: {len(filtered_collection)} legal cards, {excluded_count} excluded")
        return filtered_collection
    
    def _filter_by_commander_legality(
        self, 
        collection: Dict[str, CardEntry]
    ) -> Dict[str, CardEntry]:
        """
        Filter collection cards by Commander format legality.
        
        Args:
            collection: Card collection to filter
            
        Returns:
            Filtered collection of Commander-legal cards
        """
        self.logger.info(f"Checking Commander format legality for {len(collection)} cards")
        
        # Get all card names for batch processing
        card_names = [card_entry.name for card_entry in collection.values()]
        
        # Batch check Commander legality
        legality_results = self.scryfall.batch_check_commander_legality(card_names)
        
        filtered_collection = {}
        excluded_count = 0
        
        for normalized_name, card_entry in collection.items():
            is_legal = legality_results.get(card_entry.name, False)
            
            if is_legal:
                filtered_collection[normalized_name] = card_entry
            else:
                excluded_count += 1
                self.logger.debug(f"Excluded '{card_entry.name}' - not legal in Commander format")
        
        self.logger.info(f"Commander legality filter: {len(filtered_collection)} legal cards, {excluded_count} excluded")
        return filtered_collection
    

    
    def _select_cards_for_deck(
        self,
        available_cards: Dict[str, CardEntry],
        recommendations: Dict[str, CardRecommendation],
        deck: Deck
    ) -> List[str]:
        """
        Select cards for the deck using strategy-based targets and EDHREC synergy scores.
        
        Args:
            available_cards: Cards available in collection
            recommendations: EDHREC recommendations lookup
            deck: Current deck being built
            
        Returns:
            List of selected card names
        """
        selected_cards = []
        
        # Get target counts based on strategy and overrides
        target_counts = self.config.get_target_counts()
        
        self.logger.info(f"Using strategy '{self.config.strategy}' with targets: {target_counts}")
        
        # Categorize available cards by type
        cards_by_type = self._categorize_available_cards_by_type(available_cards)
        
        # Select cards for each type based on targets
        for card_type, target_count in target_counts.items():
            if target_count <= 0:
                continue
                
            type_cards = cards_by_type.get(card_type, {})
            if not type_cards:
                self.logger.warning(f"No {card_type} cards available in collection")
                continue
            
            # Score and sort cards of this type
            scored_type_cards = []
            for card_name, card_entry in type_cards.items():
                if card_name not in selected_cards:  # Avoid duplicates
                    score = self._calculate_card_score(card_entry, recommendations)
                    # Boost score slightly for cards matching strategy
                    if self._card_matches_strategy(card_entry, self.config.strategy):
                        score *= 1.1
                    scored_type_cards.append((card_name, score, card_entry))
            
            # Sort by score (highest first)
            scored_type_cards.sort(key=lambda x: x[1], reverse=True)
            
            # Select top cards for this type
            selected_for_type = 0
            for card_name, score, card_entry in scored_type_cards:
                if selected_for_type >= target_count:
                    break
                
                if self._can_add_card_to_deck(card_name, selected_cards, deck):
                    selected_cards.append(card_name)
                    selected_for_type += 1
                    self.logger.debug(f"Selected {card_type}: {card_name} (score: {score:.3f})")
            
            self.logger.info(f"Selected {selected_for_type}/{target_count} {card_type} cards")
        
        # Fill remaining slots with best available cards if under target
        remaining_slots = self.config.TARGET_DECK_SIZE - len(selected_cards)
        if remaining_slots > 0:
            self.logger.info(f"Filling {remaining_slots} remaining slots with best available cards")
            
            # Get all remaining cards
            remaining_cards = []
            for card_name, card_entry in available_cards.items():
                if card_name not in selected_cards:
                    score = self._calculate_card_score(card_entry, recommendations)
                    remaining_cards.append((card_name, score, card_entry))
            
            # Sort by score and fill remaining slots
            remaining_cards.sort(key=lambda x: x[1], reverse=True)
            
            for card_name, score, card_entry in remaining_cards:
                if len(selected_cards) >= self.config.TARGET_DECK_SIZE:
                    break
                
                if self._can_add_card_to_deck(card_name, selected_cards, deck):
                    selected_cards.append(card_name)
                    self.logger.debug(f"Filled slot: {card_name} (score: {score:.3f})")
        
        self.logger.info(f"Selected {len(selected_cards)} cards for deck")
        return selected_cards
    
    def _calculate_card_score(
        self,
        card_entry: CardEntry,
        recommendations: Dict[str, CardRecommendation]
    ) -> float:
        """
        Calculate a score for a card based on EDHREC synergy and availability.
        
        Args:
            card_entry: Card from collection
            recommendations: EDHREC recommendations lookup
            
        Returns:
            Calculated score for the card
        """
        # Base availability score (higher quantity = higher score)
        availability_score = min(1.0, card_entry.quantity / 4.0)  # Cap at 4 copies
        
        # Get synergy score from EDHREC recommendations
        synergy_score = 0.0
        rec = recommendations.get(card_entry.normalized_name)
        if rec:
            synergy_score = rec.synergy_score
        
        # Combine scores using configured weights
        total_score = (
            self.config.SYNERGY_WEIGHT * synergy_score +
            self.config.AVAILABILITY_WEIGHT * availability_score
        )
        
        return total_score
    
    def _categorize_available_cards_by_type(self, available_cards: Dict[str, CardEntry]) -> Dict[str, Dict[str, CardEntry]]:
        """
        Categorize available cards by their type for targeted selection.
        
        Args:
            available_cards: Cards available in collection
            
        Returns:
            Dictionary mapping card types to cards of that type
        """
        cards_by_type = {
            'creature': {},
            'instant': {},
            'sorcery': {},
            'artifact': {},
            'enchantment': {},
            'land': {}
        }
        
        for card_name, card_entry in available_cards.items():
            card_type = self._determine_card_type(card_entry.name)
            if card_type in cards_by_type:
                cards_by_type[card_type][card_name] = card_entry
        
        return cards_by_type
    
    def _determine_card_type(self, card_name: str) -> str:
        """
        Determine the primary type of a card based on name patterns.
        
        Args:
            card_name: Name of the card
            
        Returns:
            Primary card type string
        """
        name_lower = card_name.lower()
        
        # Land detection (highest priority)
        land_keywords = [
            'plains', 'island', 'swamp', 'mountain', 'forest', 'wastes',
            'command tower', 'temple', 'gate', 'sanctuary', 'land', 'haven'
        ]
        if any(keyword in name_lower for keyword in land_keywords):
            return 'land'
        
        # Artifact detection
        artifact_keywords = [
            'sol ring', 'signet', 'talisman', 'mox', 'vault', 'crypt', 'sphere',
            'rod', 'lance', 'glove', 'horn', 'copter', 'airship', 'scarecrow',
            'golem', 'welding jar', 'ruin', 'pala', 'basket', 'pot', 'pandora',
            'auracite', 'down', 'tub', 'masamune', 'greaves', 'boots'
        ]
        if any(keyword in name_lower for keyword in artifact_keywords):
            return 'artifact'
        
        # Enchantment detection
        enchantment_keywords = [
            'honden', 'pacifism', 'vigilance', 'fetters', 'breath', 'haze',
            'offering', 'purity', 'valor', 'vengeance', 'court', 'case',
            'aura', 'curse', 'blessing'
        ]
        if any(keyword in name_lower for keyword in enchantment_keywords):
            return 'enchantment'
        
        # Instant detection
        instant_keywords = [
            'path to exile', 'swords to plowshares', 'counterspell', 'lightning bolt',
            'clever concealment', 'hold the line', 'slash of light', 'candles\' glow',
            'blessed breath', 'ethereal haze', 'divine offering', 'cleanfall'
        ]
        if any(keyword in name_lower for keyword in instant_keywords):
            return 'instant'
        
        # Sorcery detection
        sorcery_keywords = [
            'wrath of god', 'day of judgment', 'cultivate', 'kodama\'s reach',
            'battle screech', 'call the coppercoats', 'collective effort',
            'battle menu', 'rescue mission', 'inspiration', 'tutor', 'rampant growth'
        ]
        if any(keyword in name_lower for keyword in sorcery_keywords):
            return 'sorcery'
        
        # Default to creature for most other cards
        return 'creature'
    
    def _card_matches_strategy(self, card_entry: CardEntry, strategy: str) -> bool:
        """
        Check if a card matches the deck building strategy.
        
        Args:
            card_entry: Card to evaluate
            strategy: Deck building strategy
            
        Returns:
            True if card matches strategy preferences
        """
        name_lower = card_entry.name.lower()
        
        if strategy == 'aggro':
            # Favor low-cost creatures and aggressive spells
            return any(word in name_lower for word in [
                'bolt', 'haste', 'first strike', 'double strike', 'trample',
                'aggressive', 'attack', 'combat', 'warrior', 'soldier'
            ])
        
        elif strategy == 'control':
            # Favor counterspells, removal, and card draw
            return any(word in name_lower for word in [
                'counter', 'draw', 'wrath', 'destroy', 'exile', 'bounce',
                'control', 'permission', 'board wipe', 'removal'
            ])
        
        elif strategy == 'combo':
            # Favor tutors, protection, and combo pieces
            return any(word in name_lower for word in [
                'tutor', 'search', 'protection', 'hexproof', 'indestructible',
                'combo', 'infinite', 'synergy', 'engine'
            ])
        
        elif strategy == 'ramp':
            # Favor mana acceleration and big threats
            return any(word in name_lower for word in [
                'mana', 'ramp', 'cultivate', 'explosive', 'sol ring',
                'signet', 'talisman', 'dragon', 'titan', 'colossus'
            ])
        
        # Balanced strategy - no specific preferences
        return False
    
    def _can_add_card_to_deck(
        self, 
        card_name: str, 
        selected_cards: List[str], 
        deck: Deck
    ) -> bool:
        """
        Check if a card can be added to the deck without violating rules.
        
        Args:
            card_name: Name of card to check
            selected_cards: Currently selected cards
            deck: Current deck state
            
        Returns:
            True if card can be added, False otherwise
        """
        # Check singleton rule (except for basic lands)
        if card_name in selected_cards and not deck._is_basic_land(card_name):
            return False
        
        # Check if deck would exceed size limit
        if len(selected_cards) >= self.config.TARGET_DECK_SIZE:
            return False
        
        return True
    
    def select_mana_base(
        self, 
        color_identity: List[str], 
        collection: Dict[str, CardEntry],
        nonland_cards: List[str]
    ) -> List[str]:
        """
        Select appropriate lands for the mana base.
        
        Args:
            color_identity: Commander's color identity
            collection: Available cards in collection
            nonland_cards: Non-land cards already selected for deck
            
        Returns:
            List of selected land names
        """
        self.logger.info(f"Selecting mana base for colors: {color_identity}")
        
        # Calculate optimal land count
        land_count = self._calculate_optimal_land_count(nonland_cards)
        
        # Get available lands from collection
        available_lands = self._get_available_lands(collection)
        
        # Prioritize lands that support the color identity
        prioritized_lands = self._prioritize_lands_by_colors(
            available_lands, color_identity
        )
        
        # Select lands up to the calculated count
        selected_lands = self._select_lands_for_deck(
            prioritized_lands, land_count, color_identity
        )
        
        self.logger.info(f"Selected {len(selected_lands)} lands for mana base")
        return selected_lands
    
    def _calculate_optimal_land_count(self, nonland_cards: List[str]) -> int:
        """
        Calculate optimal number of lands based on deck composition.
        
        Args:
            nonland_cards: List of non-land cards in deck
            
        Returns:
            Recommended number of lands
        """
        # Simple heuristic: aim for 37-38 lands in most decks
        # In a full implementation, this would analyze mana costs
        
        nonland_count = len(nonland_cards)
        target_total = self.config.TARGET_DECK_SIZE
        
        # Calculate remaining slots for lands
        remaining_slots = target_total - nonland_count
        
        # Ensure land count is within reasonable bounds
        land_count = max(
            self.config.MIN_LANDS,
            min(self.config.MAX_LANDS, remaining_slots)
        )
        
        self.logger.debug(f"Calculated optimal land count: {land_count}")
        return land_count
    
    def _get_available_lands(
        self, 
        collection: Dict[str, CardEntry]
    ) -> Dict[str, CardEntry]:
        """
        Extract land cards from the collection.
        
        Args:
            collection: Full card collection
            
        Returns:
            Dictionary of available land cards
        """
        lands = {}
        
        # Simple heuristic to identify lands
        land_keywords = [
            'plains', 'island', 'swamp', 'mountain', 'forest',
            'land', 'gate', 'temple', 'sanctuary', 'wastes',
            'command tower', 'sol ring'  # Include mana rocks
        ]
        
        for card_name, card_entry in collection.items():
            card_lower = card_entry.name.lower()
            
            # Check if card name contains land keywords
            if any(keyword in card_lower for keyword in land_keywords):
                lands[card_name] = card_entry
            
            # Also include cards that are obviously lands by name patterns
            if (card_lower.endswith(' plains') or 
                card_lower.endswith(' island') or
                card_lower.endswith(' swamp') or
                card_lower.endswith(' mountain') or
                card_lower.endswith(' forest')):
                lands[card_name] = card_entry
        
        self.logger.debug(f"Found {len(lands)} potential lands in collection")
        return lands
    
    def _prioritize_lands_by_colors(
        self,
        available_lands: Dict[str, CardEntry],
        color_identity: List[str]
    ) -> List[Tuple[str, CardEntry, float]]:
        """
        Prioritize lands based on how well they support the color identity.
        
        Args:
            available_lands: Available land cards
            color_identity: Commander's color identity
            
        Returns:
            List of (card_name, card_entry, priority_score) tuples
        """
        prioritized = []
        
        for card_name, card_entry in available_lands.items():
            priority = self._calculate_land_priority(card_entry, color_identity)
            prioritized.append((card_name, card_entry, priority))
        
        # Sort by priority (highest first)
        prioritized.sort(key=lambda x: x[2], reverse=True)
        
        return prioritized
    
    def _calculate_land_priority(
        self, 
        land_card: CardEntry, 
        color_identity: List[str]
    ) -> float:
        """
        Calculate priority score for a land based on color support.
        
        Args:
            land_card: Land card to evaluate
            color_identity: Commander's color identity
            
        Returns:
            Priority score (higher is better)
        """
        card_lower = land_card.name.lower()
        priority = 0.0
        
        # Basic lands get high priority if they match color identity
        basic_lands = {
            'plains': ['W'], 'island': ['U'], 'swamp': ['B'],
            'mountain': ['R'], 'forest': ['G']
        }
        
        for basic_name, colors in basic_lands.items():
            if basic_name in card_lower:
                if any(color in color_identity for color in colors):
                    priority += 1.0  # High priority for matching basics
                else:
                    priority += 0.1  # Low priority for non-matching basics
        
        # Command Tower and other universal lands get high priority
        if 'command tower' in card_lower:
            priority += 1.5
        
        # Dual lands and other multicolor lands get medium-high priority
        if any(word in card_lower for word in ['gate', 'temple', 'sanctuary']):
            priority += 0.8
        
        # Mana rocks get medium priority
        if any(word in card_lower for word in ['sol ring', 'signet', 'talisman']):
            priority += 0.7
        
        # Utility lands get lower priority
        if 'land' in card_lower and priority == 0.0:
            priority += 0.3
        
        return priority
    
    def _select_lands_for_deck(
        self,
        prioritized_lands: List[Tuple[str, CardEntry, float]],
        target_count: int,
        color_identity: List[str]
    ) -> List[str]:
        """
        Select the final set of lands for the deck.
        
        Args:
            prioritized_lands: Lands sorted by priority
            target_count: Number of lands to select
            color_identity: Commander's color identity
            
        Returns:
            List of selected land names
        """
        selected = []
        basic_land_counts = {}
        
        for card_name, card_entry, priority in prioritized_lands:
            if len(selected) >= target_count:
                break
            
            # Handle basic lands specially (can have multiple copies)
            if self._is_basic_land_type(card_entry.name):
                basic_type = self._get_basic_land_type(card_entry.name)
                current_count = basic_land_counts.get(basic_type, 0)
                
                # Limit basic lands to reasonable numbers
                max_basics = min(10, target_count // 3)  # At most 1/3 of lands
                
                if current_count < max_basics:
                    selected.append(card_name)
                    basic_land_counts[basic_type] = current_count + 1
            else:
                # Non-basic lands: only add if not already selected
                if card_name not in selected:
                    selected.append(card_name)
        
        return selected
    
    def _is_basic_land_type(self, card_name: str) -> bool:
        """Check if a card is a basic land type."""
        basic_types = ['plains', 'island', 'swamp', 'mountain', 'forest', 'wastes']
        card_lower = card_name.lower()
        return any(basic in card_lower for basic in basic_types)
    
    def _get_basic_land_type(self, card_name: str) -> str:
        """Get the basic land type from a card name."""
        card_lower = card_name.lower()
        basic_types = ['plains', 'island', 'swamp', 'mountain', 'forest', 'wastes']
        
        for basic_type in basic_types:
            if basic_type in card_lower:
                return basic_type
        
        return 'unknown'
    
    def balance_mana_curve(
        self, 
        available_cards: Dict[str, CardEntry], 
        recommendations: Dict[str, CardRecommendation],
        target_curve: Optional[Dict[int, int]] = None
    ) -> List[str]:
        """
        Optimize converted mana cost distribution for balanced gameplay.
        
        Args:
            available_cards: Cards available for selection
            recommendations: EDHREC recommendations lookup
            target_curve: Optional target mana curve distribution
            
        Returns:
            List of cards selected for optimal mana curve
        """
        if target_curve is None:
            target_curve = self._get_default_mana_curve()
        
        self.logger.info("Balancing mana curve for optimal gameplay")
        
        # Categorize cards by CMC
        cards_by_cmc = self._categorize_cards_by_cmc(available_cards)
        
        # Select cards to match target curve
        selected_cards = []
        
        for cmc, target_count in target_curve.items():
            if cmc in cards_by_cmc:
                # Get cards for this CMC slot
                cmc_cards = cards_by_cmc[cmc]
                
                # Score and sort cards for this CMC
                scored_cards = []
                for card_name, card_entry in cmc_cards.items():
                    score = self._calculate_card_score(card_entry, recommendations)
                    scored_cards.append((card_name, score))
                
                scored_cards.sort(key=lambda x: x[1], reverse=True)
                
                # Select top cards up to target count
                selected_count = 0
                for card_name, score in scored_cards:
                    if selected_count >= target_count:
                        break
                    if card_name not in selected_cards:
                        selected_cards.append(card_name)
                        selected_count += 1
        
        self.logger.info(f"Selected {len(selected_cards)} cards for balanced mana curve")
        return selected_cards
    
    def _get_default_mana_curve(self) -> Dict[int, int]:
        """
        Get default target mana curve for Commander decks.
        
        Returns:
            Dictionary mapping CMC to target card count
        """
        # Standard Commander mana curve (excluding lands)
        return {
            0: 2,   # 0 CMC (mana rocks, free spells)
            1: 4,   # 1 CMC (cheap utility)
            2: 8,   # 2 CMC (ramp, cheap removal)
            3: 12,  # 3 CMC (core spells)
            4: 10,  # 4 CMC (value creatures/spells)
            5: 8,   # 5 CMC (powerful effects)
            6: 6,   # 6 CMC (big threats)
            7: 4,   # 7+ CMC (game-enders)
            8: 2,
            9: 1,
            10: 1
        }
    
    def _categorize_cards_by_cmc(
        self, 
        available_cards: Dict[str, CardEntry]
    ) -> Dict[int, Dict[str, CardEntry]]:
        """
        Categorize cards by their converted mana cost.
        
        Args:
            available_cards: Cards to categorize
            
        Returns:
            Dictionary mapping CMC to cards at that cost
        """
        cards_by_cmc = {}
        
        for card_name, card_entry in available_cards.items():
            # Estimate CMC from card name (simplified heuristic)
            estimated_cmc = self._estimate_cmc_from_name(card_entry.name)
            
            if estimated_cmc not in cards_by_cmc:
                cards_by_cmc[estimated_cmc] = {}
            
            cards_by_cmc[estimated_cmc][card_name] = card_entry
        
        return cards_by_cmc
    
    def _estimate_cmc_from_name(self, card_name: str) -> int:
        """
        Estimate CMC from card name using heuristics.
        
        Note: This is a simplified approach. Real implementation would
        use a card database to get actual CMC values.
        
        Args:
            card_name: Name of the card
            
        Returns:
            Estimated converted mana cost
        """
        card_lower = card_name.lower()
        
        # Basic heuristics based on common naming patterns
        if any(word in card_lower for word in ['sol ring', 'mana crypt']):
            return 0
        
        if any(word in card_lower for word in ['bolt', 'path', 'swords']):
            return 1
        
        if any(word in card_lower for word in ['rampant', 'signets', 'talisman']):
            return 2
        
        if any(word in card_lower for word in ['cultivate', 'kodama']):
            return 3
        
        # Default estimation based on card name length and complexity
        if len(card_name) < 10:
            return 2
        elif len(card_name) < 15:
            return 3
        elif len(card_name) < 20:
            return 4
        else:
            return 5
    
    def categorize_cards_by_function(
        self, 
        available_cards: Dict[str, CardEntry]
    ) -> Dict[str, List[str]]:
        """
        Categorize cards by their function (removal, ramp, draw, etc.).
        
        Args:
            available_cards: Cards to categorize
            
        Returns:
            Dictionary mapping function categories to card lists
        """
        categories = {
            'removal': [],
            'ramp': [],
            'card_draw': [],
            'creatures': [],
            'protection': [],
            'utility': [],
            'win_conditions': []
        }
        
        for card_name, card_entry in available_cards.items():
            card_lower = card_entry.name.lower()
            
            # Categorize based on name patterns
            if any(word in card_lower for word in [
                'destroy', 'exile', 'murder', 'wrath', 'board wipe', 'removal'
            ]):
                categories['removal'].append(card_name)
            elif any(word in card_lower for word in [
                'rampant', 'cultivate', 'sol ring', 'signet', 'talisman', 'mana'
            ]):
                categories['ramp'].append(card_name)
            elif any(word in card_lower for word in [
                'draw', 'divination', 'harmonize', 'rhystic study'
            ]):
                categories['card_draw'].append(card_name)
            elif any(word in card_lower for word in [
                'creature', 'beast', 'dragon', 'angel', 'demon', 'wizard'
            ]):
                categories['creatures'].append(card_name)
            elif any(word in card_lower for word in [
                'protection', 'indestructible', 'hexproof', 'counterspell'
            ]):
                categories['protection'].append(card_name)
            elif any(word in card_lower for word in [
                'win', 'victory', 'combo', 'infinite'
            ]):
                categories['win_conditions'].append(card_name)
            else:
                categories['utility'].append(card_name)
        
        return categories
    
    def enforce_singleton_rule(self, deck_cards: List[str]) -> List[str]:
        """
        Ensure no duplicate cards except basic lands.
        
        Args:
            deck_cards: List of cards in the deck
            
        Returns:
            Cleaned list with duplicates removed
        """
        seen_cards = set()
        cleaned_deck = []
        basic_land_counts = {}
        
        for card_name in deck_cards:
            card_lower = card_name.lower()
            
            # Handle basic lands specially (allow multiple copies)
            if self._is_basic_land_type(card_name):
                basic_type = self._get_basic_land_type(card_name)
                current_count = basic_land_counts.get(basic_type, 0)
                
                # Allow reasonable number of each basic land type
                if current_count < 15:  # Max 15 of each basic type
                    cleaned_deck.append(card_name)
                    basic_land_counts[basic_type] = current_count + 1
            else:
                # Non-basic cards: enforce singleton rule
                if card_lower not in seen_cards:
                    cleaned_deck.append(card_name)
                    seen_cards.add(card_lower)
                else:
                    self.logger.debug(f"Removed duplicate card: {card_name}")
        
        return cleaned_deck
    
    def optimize_deck_balance(
        self,
        selected_cards: List[str],
        available_cards: Dict[str, CardEntry],
        recommendations: Dict[str, CardRecommendation]
    ) -> List[str]:
        """
        Optimize deck for balanced gameplay across different categories.
        
        Args:
            selected_cards: Currently selected cards
            available_cards: All available cards
            recommendations: EDHREC recommendations
            
        Returns:
            Optimized list of cards
        """
        self.logger.info("Optimizing deck balance across card categories")
        
        # Categorize current selection
        current_categories = self._categorize_selected_cards(selected_cards)
        
        # Define target ratios for balanced gameplay
        target_ratios = {
            'removal': 0.08,      # 8% removal
            'ramp': 0.10,         # 10% ramp
            'card_draw': 0.08,    # 8% card draw
            'creatures': 0.35,    # 35% creatures
            'protection': 0.05,   # 5% protection
            'utility': 0.24,      # 24% utility
            'win_conditions': 0.10 # 10% win conditions
        }
        
        # Calculate current ratios
        total_nonland = len([c for c in selected_cards if not self._is_basic_land_type(c)])
        current_ratios = {}
        
        for category, cards in current_categories.items():
            current_ratios[category] = len(cards) / max(1, total_nonland)
        
        # Identify categories that need adjustment
        optimized_cards = selected_cards.copy()
        
        for category, target_ratio in target_ratios.items():
            current_ratio = current_ratios.get(category, 0)
            
            if current_ratio < target_ratio * 0.8:  # If significantly under target
                # Add more cards from this category
                needed_cards = int(total_nonland * target_ratio) - len(current_categories.get(category, []))
                
                if needed_cards > 0:
                    category_cards = self._get_cards_by_category(available_cards, category)
                    additional_cards = self._select_best_cards_from_category(
                        category_cards, recommendations, needed_cards, optimized_cards
                    )
                    optimized_cards.extend(additional_cards)
        
        return optimized_cards
    
    def _categorize_selected_cards(self, selected_cards: List[str]) -> Dict[str, List[str]]:
        """Categorize the currently selected cards by function."""
        # Create temporary CardEntry objects for categorization
        temp_cards = {name: CardEntry(name=name, quantity=1) for name in selected_cards}
        return self.categorize_cards_by_function(temp_cards)
    
    def _get_cards_by_category(
        self, 
        available_cards: Dict[str, CardEntry], 
        category: str
    ) -> Dict[str, CardEntry]:
        """Get all available cards in a specific category."""
        all_categories = self.categorize_cards_by_function(available_cards)
        category_card_names = all_categories.get(category, [])
        
        return {name: available_cards[name] for name in category_card_names 
                if name in available_cards}
    
    def _select_best_cards_from_category(
        self,
        category_cards: Dict[str, CardEntry],
        recommendations: Dict[str, CardRecommendation],
        count: int,
        existing_cards: List[str]
    ) -> List[str]:
        """Select the best cards from a category that aren't already in the deck."""
        # Score and sort cards
        scored_cards = []
        for card_name, card_entry in category_cards.items():
            if card_name not in existing_cards:
                score = self._calculate_card_score(card_entry, recommendations)
                scored_cards.append((card_name, score))
        
        scored_cards.sort(key=lambda x: x[1], reverse=True)
        
        # Return top cards up to requested count
        return [card_name for card_name, _ in scored_cards[:count]]
    
    def handle_insufficient_cards(
        self,
        commander: str,
        available_cards: Dict[str, CardEntry],
        recommendations: List[CardRecommendation],
        min_deck_size: int = 60
    ) -> Tuple[Deck, Dict[str, any]]:
        """
        Generate partial deck when collection lacks sufficient cards.
        
        Args:
            commander: Commander name
            available_cards: Available cards in collection
            recommendations: EDHREC recommendations
            min_deck_size: Minimum acceptable deck size
            
        Returns:
            Tuple of (partial_deck, generation_report)
        """
        self.logger.warning(f"Insufficient cards for full deck. Generating partial deck.")
        
        # Initialize generation report
        report = {
            'total_available': len(available_cards),
            'target_size': self.config.TARGET_DECK_SIZE + 1,  # +1 for commander
            'actual_size': 0,
            'missing_cards': 0,
            'categories_filled': {},
            'fallback_strategies_used': [],
            'recommendations_used': 0,
            'recommendations_available': len(recommendations)
        }
        
        # Extract color identity
        color_identity = self._extract_color_identity(commander)
        
        # Create deck with commander
        deck = Deck(commander=commander, color_identity=color_identity)
        
        # Filter available cards
        filtered_cards = self._filter_by_color_identity(available_cards, color_identity)
        filtered_cards = {k: v for k, v in filtered_cards.items() 
                         if v.normalized_name != commander.lower()}
        
        # Build recommendation lookup
        rec_lookup = {rec.name.lower(): rec for rec in recommendations}
        
        # Try to build deck with available cards
        selected_cards = self._select_cards_with_fallbacks(
            filtered_cards, rec_lookup, deck, report
        )
        
        # Add cards to deck
        for card_name in selected_cards:
            deck.add_card(card_name)
        
        # Update report
        report['actual_size'] = deck.total_cards
        report['missing_cards'] = report['target_size'] - report['actual_size']
        
        # Log generation decisions
        self._log_generation_decisions(deck, report)
        
        return deck, report
    
    def _select_cards_with_fallbacks(
        self,
        available_cards: Dict[str, CardEntry],
        recommendations: Dict[str, CardRecommendation],
        deck: Deck,
        report: Dict[str, any]
    ) -> List[str]:
        """
        Select cards using fallback strategies when insufficient cards available.
        
        Args:
            available_cards: Available cards
            recommendations: EDHREC recommendations lookup
            deck: Current deck being built
            report: Generation report to update
            
        Returns:
            List of selected card names
        """
        selected_cards = []
        
        # Strategy 1: Use all recommended cards that are available
        recommended_cards = self._get_available_recommended_cards(
            available_cards, recommendations
        )
        
        for card_name in recommended_cards:
            if len(selected_cards) < self.config.TARGET_DECK_SIZE:
                selected_cards.append(card_name)
                report['recommendations_used'] += 1
        
        if len(selected_cards) < self.config.TARGET_DECK_SIZE:
            report['fallback_strategies_used'].append('use_all_available_cards')
            
            # Strategy 2: Add all remaining available cards
            remaining_cards = [
                name for name, entry in available_cards.items()
                if name not in selected_cards
            ]
            
            # Sort by estimated quality
            remaining_cards.sort(key=lambda x: self._estimate_card_quality(x))
            
            for card_name in remaining_cards:
                if len(selected_cards) < self.config.TARGET_DECK_SIZE:
                    selected_cards.append(card_name)
        
        # Strategy 3: Fill with basic lands if still short
        if len(selected_cards) < self.config.TARGET_DECK_SIZE:
            report['fallback_strategies_used'].append('add_basic_lands')
            basic_lands = self._generate_basic_lands(deck.color_identity)
            
            needed_cards = self.config.TARGET_DECK_SIZE - len(selected_cards)
            selected_cards.extend(basic_lands[:needed_cards])
        
        return selected_cards
    
    def _get_available_recommended_cards(
        self,
        available_cards: Dict[str, CardEntry],
        recommendations: Dict[str, CardRecommendation]
    ) -> List[str]:
        """Get list of recommended cards that are available in collection."""
        available_recommended = []
        
        for card_name, card_entry in available_cards.items():
            if card_entry.normalized_name in recommendations:
                available_recommended.append(card_name)
        
        # Sort by recommendation score
        available_recommended.sort(
            key=lambda x: recommendations.get(
                available_cards[x].normalized_name, 
                CardRecommendation("", 0.0)
            ).synergy_score,
            reverse=True
        )
        
        return available_recommended
    
    def _estimate_card_quality(self, card_name: str) -> float:
        """
        Estimate card quality based on name patterns.
        
        Args:
            card_name: Name of the card
            
        Returns:
            Estimated quality score (higher is better)
        """
        card_lower = card_name.lower()
        quality = 0.5  # Base quality
        
        # High-quality indicators
        if any(word in card_lower for word in [
            'legendary', 'mythic', 'rare', 'powerful', 'ancient'
        ]):
            quality += 0.3
        
        # Utility indicators
        if any(word in card_lower for word in [
            'draw', 'search', 'tutor', 'ramp', 'removal'
        ]):
            quality += 0.2
        
        # Low-quality indicators
        if any(word in card_lower for word in [
            'token', 'basic', 'common', 'vanilla'
        ]):
            quality -= 0.2
        
        return max(0.0, min(1.0, quality))
    
    def _generate_basic_lands(self, color_identity: List[str]) -> List[str]:
        """
        Generate basic land names for the color identity.
        
        Args:
            color_identity: Commander's color identity
            
        Returns:
            List of basic land names
        """
        basic_lands = []
        color_to_land = {
            'W': 'Plains',
            'U': 'Island', 
            'B': 'Swamp',
            'R': 'Mountain',
            'G': 'Forest'
        }
        
        # Add basic lands for each color in identity
        for color in color_identity:
            if color in color_to_land:
                # Add multiple copies of each basic land type
                for _ in range(8):  # 8 of each basic land type
                    basic_lands.append(color_to_land[color])
        
        # If colorless or no colors, add Wastes
        if not color_identity or color_identity == ['C']:
            for _ in range(20):
                basic_lands.append('Wastes')
        
        return basic_lands
    
    def _log_generation_decisions(self, deck: Deck, report: Dict[str, any]) -> None:
        """
        Log detailed information about deck generation decisions.
        
        Args:
            deck: Generated deck
            report: Generation report with statistics
        """
        self.logger.info("=== Deck Generation Report ===")
        self.logger.info(f"Commander: {deck.commander}")
        self.logger.info(f"Target deck size: {report['target_size']} cards")
        self.logger.info(f"Actual deck size: {report['actual_size']} cards")
        self.logger.info(f"Missing cards: {report['missing_cards']}")
        self.logger.info(f"Available cards in collection: {report['total_available']}")
        self.logger.info(f"EDHREC recommendations used: {report['recommendations_used']}/{report['recommendations_available']}")
        
        if report['fallback_strategies_used']:
            self.logger.info("Fallback strategies used:")
            for strategy in report['fallback_strategies_used']:
                self.logger.info(f"  - {strategy}")
        
        # Log card categories if available
        if report['categories_filled']:
            self.logger.info("Card categories filled:")
            for category, count in report['categories_filled'].items():
                self.logger.info(f"  - {category}: {count} cards")
        
        # Log validation results
        validation_results = deck.validate()
        self.logger.info("Deck validation results:")
        for rule, passed in validation_results.items():
            status = "PASS" if passed else "FAIL"
            self.logger.info(f"  - {rule}: {status}")
        
        if not deck.is_valid():
            errors = deck.get_validation_errors()
            self.logger.warning("Deck validation errors:")
            for error in errors:
                self.logger.warning(f"  - {error}")
    
    def create_fallback_strategies(
        self, 
        missing_categories: List[str],
        available_cards: Dict[str, CardEntry]
    ) -> Dict[str, List[str]]:
        """
        Create fallback strategies for missing card categories.
        
        Args:
            missing_categories: Categories that are underrepresented
            available_cards: Available cards to choose from
            
        Returns:
            Dictionary mapping strategies to card suggestions
        """
        strategies = {}
        
        for category in missing_categories:
            if category == 'removal':
                # Suggest any cards that might serve as removal
                strategies[f'fallback_{category}'] = [
                    name for name, entry in available_cards.items()
                    if any(word in entry.name.lower() for word in [
                        'destroy', 'exile', 'damage', 'fight', 'bounce'
                    ])
                ]
            
            elif category == 'ramp':
                # Suggest mana acceleration alternatives
                strategies[f'fallback_{category}'] = [
                    name for name, entry in available_cards.items()
                    if any(word in entry.name.lower() for word in [
                        'mana', 'land', 'artifact', 'treasure', 'ritual'
                    ])
                ]
            
            elif category == 'card_draw':
                # Suggest card advantage alternatives
                strategies[f'fallback_{category}'] = [
                    name for name, entry in available_cards.items()
                    if any(word in entry.name.lower() for word in [
                        'draw', 'card', 'hand', 'library', 'search'
                    ])
                ]
        
        return strategies