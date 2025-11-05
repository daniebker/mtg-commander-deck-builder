"""EDHREC service module for fetching card recommendations."""

import time
import logging
from typing import List, Dict, Optional, Any
from functools import wraps
import json
import os
from pathlib import Path

try:
    import pyedhrec
except ImportError:
    pyedhrec = None

from .models import CardRecommendation


class EDHRECAPIError(Exception):
    """Raised when EDHREC API calls fail."""
    pass


class EDHRECService:
    """Service for interacting with EDHREC API via pyedhrec package."""
    
    def __init__(self, cache_dir: Optional[str] = None):
        """
        Initialize EDHREC service.
        
        Args:
            cache_dir: Directory for caching API responses. If None, uses default.
        """
        if pyedhrec is None:
            raise ImportError("pyedhrec package is required but not installed")
        
        self.logger = logging.getLogger(__name__)
        
        # Initialize pyedhrec client
        self.edhrec_client = pyedhrec.EDHRec()
        
        # Set up caching directory
        if cache_dir is None:
            cache_dir = os.path.join(os.path.expanduser("~"), ".mtg_deck_builder", "cache")
        
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Cache settings
        self.cache_ttl = 3600 * 24  # 24 hours in seconds
        
        # Retry settings
        self.max_retries = 3
        self.base_delay = 1.0
        self.max_delay = 30.0
    
    def get_commander_recommendations(self, commander: str) -> List[CardRecommendation]:
        """
        Get card recommendations for a specific commander from EDHREC.
        
        Args:
            commander: Name of the commander card
            
        Returns:
            List of CardRecommendation objects
            
        Raises:
            EDHRECAPIError: If API call fails after retries
        """
        cache_key = f"commander_{commander.lower().replace(' ', '_')}"
        
        # Try to get from cache first
        cached_data = self._get_from_cache(cache_key)
        if cached_data is not None:
            self.logger.info(f"Using cached recommendations for {commander}")
            return self._parse_recommendations(cached_data)
        
        # Fetch from API with retry logic
        try:
            raw_data = self._fetch_with_retry(
                lambda: self._fetch_commander_data(commander)
            )
            
            # Cache the raw data
            self._save_to_cache(cache_key, raw_data)
            
            # Parse and return recommendations
            return self._parse_recommendations(raw_data)
            
        except Exception as e:
            self.logger.error(f"Failed to fetch recommendations for {commander}: {e}")
            raise EDHRECAPIError(f"Could not fetch recommendations for {commander}: {e}")
    
    def get_card_synergy_score(self, card: str, commander: str) -> float:
        """
        Get synergy score for a specific card with a commander.
        
        Args:
            card: Name of the card to score
            commander: Name of the commander
            
        Returns:
            Synergy score between 0.0 and 1.0
        """
        try:
            # Get all recommendations for the commander
            recommendations = self.get_commander_recommendations(commander)
            
            # Find the specific card in recommendations
            card_lower = card.lower()
            for rec in recommendations:
                if rec.name.lower() == card_lower:
                    return rec.synergy_score
            
            # If card not found in recommendations, return low score
            return 0.1
            
        except EDHRECAPIError:
            # If we can't get recommendations, return neutral score
            return 0.5
    
    def _fetch_commander_data(self, commander: str) -> Dict[str, Any]:
        """
        Fetch raw commander data from pyedhrec.
        
        Args:
            commander: Commander name
            
        Returns:
            Raw API response data
        """
        try:
            # Use pyedhrec client to fetch commander data
            self.logger.debug(f"Fetching EDHREC data for commander: {commander}")
            commander_data = self.edhrec_client.get_commander_data(commander)
            
            if not commander_data:
                raise EDHRECAPIError(f"No data returned for commander: {commander}")
            
            return commander_data
            
        except Exception as e:
            raise EDHRECAPIError(f"pyedhrec API call failed: {e}")
    
    def _parse_recommendations(self, raw_data: Dict[str, Any]) -> List[CardRecommendation]:
        """
        Parse raw EDHREC data into CardRecommendation objects.
        
        Args:
            raw_data: Raw API response data from pyedhrec
            
        Returns:
            List of parsed CardRecommendation objects
        """
        recommendations = []
        
        try:
            # Navigate to the cardlists in the pyedhrec response structure
            container = raw_data.get('container', {})
            json_dict = container.get('json_dict', {})
            cardlists = json_dict.get('cardlists', [])
            
            self.logger.debug(f"Found {len(cardlists)} cardlists in EDHREC data")
            
            for cardlist in cardlists:
                header = cardlist.get('header', '')
                tag = cardlist.get('tag', '')
                cardviews = cardlist.get('cardviews', [])
                
                # Determine category based on header/tag
                category = self._determine_category(header, tag)
                
                # Parse cards in this list
                for card_view in cardviews:
                    card_name = card_view.get('name', '')
                    if not card_name:
                        continue
                    
                    # Extract synergy information
                    synergy_score = self._calculate_synergy_score(card_view, category)
                    inclusion_percentage = card_view.get('inclusion_percentage', 0.0)
                    
                    # Convert percentage if it's in decimal form
                    if isinstance(inclusion_percentage, (int, float)) and inclusion_percentage <= 1.0:
                        inclusion_percentage *= 100
                    
                    rec = CardRecommendation(
                        name=card_name,
                        synergy_score=synergy_score,
                        category=category,
                        inclusion_percentage=float(inclusion_percentage)
                    )
                    recommendations.append(rec)
            
            self.logger.info(f"Parsed {len(recommendations)} card recommendations")
            
        except Exception as e:
            self.logger.warning(f"Error parsing EDHREC recommendations: {e}")
            # Return fallback recommendations if parsing fails
            return self.get_fallback_recommendations("Unknown")
        
        return recommendations
    
    def _determine_category(self, header: str, tag: str) -> str:
        """
        Determine card category based on EDHREC section header and tag.
        
        Args:
            header: Section header from EDHREC
            tag: Section tag from EDHREC
            
        Returns:
            Category string
        """
        header_lower = header.lower()
        tag_lower = tag.lower()
        
        # Map EDHREC sections to categories
        if 'high synergy' in header_lower or 'synergy' in tag_lower:
            return 'synergy'
        elif 'top cards' in header_lower or 'staple' in tag_lower:
            return 'staple'
        elif 'creature' in header_lower or 'creature' in tag_lower:
            return 'creature'
        elif 'instant' in header_lower or 'instant' in tag_lower:
            return 'instant'
        elif 'sorcery' in header_lower or 'sorcery' in tag_lower:
            return 'sorcery'
        elif 'artifact' in header_lower or 'artifact' in tag_lower:
            return 'artifact'
        elif 'enchantment' in header_lower or 'enchantment' in tag_lower:
            return 'enchantment'
        elif 'land' in header_lower or 'land' in tag_lower:
            return 'land'
        elif 'planeswalker' in header_lower or 'planeswalker' in tag_lower:
            return 'planeswalker'
        elif 'budget' in header_lower or 'budget' in tag_lower:
            return 'budget'
        else:
            return 'other'
    
    def _calculate_synergy_score(self, card_view: Dict[str, Any], category: str) -> float:
        """
        Calculate synergy score based on card data and category.
        
        Args:
            card_view: Card data from EDHREC
            category: Card category
            
        Returns:
            Synergy score between 0.0 and 1.0
        """
        # Base score by category
        category_scores = {
            'synergy': 0.85,
            'staple': 0.90,
            'creature': 0.75,
            'instant': 0.70,
            'sorcery': 0.70,
            'artifact': 0.80,
            'enchantment': 0.75,
            'land': 0.65,
            'planeswalker': 0.80,
            'budget': 0.60,
            'other': 0.50
        }
        
        base_score = category_scores.get(category, 0.50)
        
        # Adjust based on inclusion percentage if available
        inclusion_pct = card_view.get('inclusion_percentage', 0)
        if isinstance(inclusion_pct, (int, float)):
            # Convert to 0-1 range if needed
            if inclusion_pct > 1.0:
                inclusion_pct = inclusion_pct / 100.0
            
            # Higher inclusion percentage = higher synergy
            inclusion_bonus = inclusion_pct * 0.2  # Up to 0.2 bonus
            base_score = min(1.0, base_score + inclusion_bonus)
        
        return base_score
    
    def _fetch_with_retry(self, fetch_func) -> Any:
        """
        Execute a function with exponential backoff retry logic.
        
        Args:
            fetch_func: Function to execute with retries
            
        Returns:
            Result of successful function execution
            
        Raises:
            EDHRECAPIError: If all retries fail
        """
        last_exception = None
        
        for attempt in range(self.max_retries):
            try:
                return fetch_func()
                
            except Exception as e:
                last_exception = e
                
                if attempt < self.max_retries - 1:
                    # Calculate delay with exponential backoff
                    delay = min(
                        self.base_delay * (2 ** attempt),
                        self.max_delay
                    )
                    
                    self.logger.warning(
                        f"API call failed (attempt {attempt + 1}/{self.max_retries}), "
                        f"retrying in {delay:.1f}s: {e}"
                    )
                    
                    time.sleep(delay)
                else:
                    self.logger.error(f"All retry attempts failed: {e}")
        
        raise EDHRECAPIError(f"API call failed after {self.max_retries} attempts: {last_exception}")
    
    def _get_cache_path(self, cache_key: str) -> Path:
        """Get the file path for a cache key."""
        return self.cache_dir / f"{cache_key}.json"
    
    def _get_from_cache(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve data from cache if it exists and is not expired.
        
        Args:
            cache_key: Key to look up in cache
            
        Returns:
            Cached data if valid, None otherwise
        """
        cache_path = self._get_cache_path(cache_key)
        
        try:
            if not cache_path.exists():
                return None
            
            # Check if cache is expired
            cache_age = time.time() - cache_path.stat().st_mtime
            if cache_age > self.cache_ttl:
                self.logger.debug(f"Cache expired for {cache_key}")
                cache_path.unlink()  # Remove expired cache
                return None
            
            # Load and return cached data
            with open(cache_path, 'r', encoding='utf-8') as f:
                return json.load(f)
                
        except Exception as e:
            self.logger.warning(f"Error reading cache for {cache_key}: {e}")
            return None
    
    def _save_to_cache(self, cache_key: str, data: Dict[str, Any]) -> None:
        """
        Save data to cache.
        
        Args:
            cache_key: Key to store data under
            data: Data to cache
        """
        cache_path = self._get_cache_path(cache_key)
        
        try:
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            
            self.logger.debug(f"Cached data for {cache_key}")
            
        except Exception as e:
            self.logger.warning(f"Error saving cache for {cache_key}: {e}")
    
    def clear_cache(self) -> None:
        """Clear all cached data."""
        try:
            for cache_file in self.cache_dir.glob("*.json"):
                cache_file.unlink()
            self.logger.info("Cache cleared")
        except Exception as e:
            self.logger.warning(f"Error clearing cache: {e}")
    
    def get_fallback_recommendations(self, commander: str) -> List[CardRecommendation]:
        """
        Provide fallback recommendations when API is unavailable.
        
        Args:
            commander: Commander name
            
        Returns:
            List of generic recommendations based on commander colors
        """
        self.logger.info(f"Using fallback recommendations for {commander}")
        
        # Generic staple cards that work in most decks
        fallback_cards = [
            ("Sol Ring", 0.95, "staple", 85.0),
            ("Command Tower", 0.90, "staple", 80.0),
            ("Lightning Greaves", 0.85, "staple", 70.0),
            ("Swiftfoot Boots", 0.80, "staple", 65.0),
            ("Arcane Signet", 0.85, "staple", 75.0),
            ("Cultivate", 0.75, "ramp", 60.0),
            ("Kodama's Reach", 0.75, "ramp", 58.0),
            ("Swords to Plowshares", 0.80, "removal", 55.0),
            ("Path to Exile", 0.78, "removal", 52.0),
            ("Counterspell", 0.70, "control", 45.0),
            ("Rhystic Study", 0.88, "draw", 68.0),
            ("Mystic Remora", 0.82, "draw", 62.0),
        ]
        
        recommendations = []
        for name, score, category, inclusion in fallback_cards:
            rec = CardRecommendation(
                name=name,
                synergy_score=score,
                category=category,
                inclusion_percentage=inclusion
            )
            recommendations.append(rec)
        
        return recommendations
    
    def is_api_available(self) -> bool:
        """
        Check if EDHREC API is currently available.
        
        Returns:
            True if API is available, False otherwise
        """
        try:
            # Try a simple API call to test availability
            # Use a well-known commander for testing
            test_data = self.edhrec_client.get_commander_data("Atraxa, Praetors' Voice")
            return test_data is not None
        except Exception as e:
            self.logger.debug(f"EDHREC API availability check failed: {e}")
            return False
    
    def get_commander_recommendations_with_fallback(self, commander: str) -> List[CardRecommendation]:
        """
        Get recommendations with automatic fallback to generic recommendations.
        
        Args:
            commander: Commander name
            
        Returns:
            List of recommendations (from API or fallback)
        """
        try:
            return self.get_commander_recommendations(commander)
        except EDHRECAPIError:
            self.logger.warning(f"API unavailable, using fallback for {commander}")
            return self.get_fallback_recommendations(commander)
    
    def handle_api_errors(self, func):
        """
        Decorator for handling API errors gracefully.
        
        Args:
            func: Function to wrap with error handling
            
        Returns:
            Wrapped function with error handling
        """
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except EDHRECAPIError as e:
                self.logger.error(f"EDHREC API error in {func.__name__}: {e}")
                # Return appropriate fallback results
                if 'recommendations' in func.__name__:
                    commander = args[1] if len(args) > 1 else kwargs.get('commander', 'Unknown')
                    return self.get_fallback_recommendations(commander)
                else:
                    return 0.5  # Neutral synergy score
            except Exception as e:
                self.logger.error(f"Unexpected error in {func.__name__}: {e}")
                # Return appropriate fallback results
                if 'recommendations' in func.__name__:
                    commander = args[1] if len(args) > 1 else kwargs.get('commander', 'Unknown')
                    return self.get_fallback_recommendations(commander)
                else:
                    return 0.5
        
        return wrapper