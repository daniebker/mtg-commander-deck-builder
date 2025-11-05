"""
Scryfall API service for fetching card data with local caching.

This module provides functionality to query the Scryfall API for card information,
particularly color identity data, with a local filesystem cache to minimize API calls.
"""

import json
import time
import logging
import hashlib
import random
from pathlib import Path
from typing import Dict, List, Optional, Any, Set
import requests
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed


@dataclass
class CardData:
    """Represents card data from Scryfall API."""
    name: str
    color_identity: List[str]
    mana_cost: str
    type_line: str
    oracle_text: str
    cmc: float
    colors: List[str]
    legalities: Dict[str, str] = None
    prices: Dict[str, str] = None
    purchase_uris: Dict[str, str] = None
    cardmarket_id: Optional[int] = None
    scryfall_uri: str = ""
    image_uris: Dict[str, str] = None
    
    def __post_init__(self):
        """Initialize optional fields if not provided."""
        if self.legalities is None:
            self.legalities = {}
        if self.prices is None:
            self.prices = {}
        if self.purchase_uris is None:
            self.purchase_uris = {}
        if self.image_uris is None:
            self.image_uris = {}
    
    @classmethod
    def from_scryfall_data(cls, data: Dict[str, Any]) -> 'CardData':
        """Create CardData from Scryfall API response."""
        return cls(
            name=data.get('name', ''),
            color_identity=data.get('color_identity', []),
            mana_cost=data.get('mana_cost', ''),
            type_line=data.get('type_line', ''),
            oracle_text=data.get('oracle_text', ''),
            cmc=float(data.get('cmc', 0)),
            colors=data.get('colors', []),
            legalities=data.get('legalities', {}),
            prices=data.get('prices', {}),
            purchase_uris=data.get('purchase_uris', {}),
            cardmarket_id=data.get('cardmarket_id'),
            scryfall_uri=data.get('scryfall_uri', ''),
            image_uris=data.get('image_uris', {})
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'name': self.name,
            'color_identity': self.color_identity,
            'mana_cost': self.mana_cost,
            'type_line': self.type_line,
            'oracle_text': self.oracle_text,
            'cmc': self.cmc,
            'colors': self.colors,
            'legalities': self.legalities,
            'prices': self.prices,
            'purchase_uris': self.purchase_uris,
            'cardmarket_id': self.cardmarket_id,
            'scryfall_uri': self.scryfall_uri,
            'image_uris': self.image_uris
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CardData':
        """Create CardData from dictionary."""
        return cls(
            name=data.get('name', ''),
            color_identity=data.get('color_identity', []),
            mana_cost=data.get('mana_cost', ''),
            type_line=data.get('type_line', ''),
            oracle_text=data.get('oracle_text', ''),
            cmc=float(data.get('cmc', 0)),
            colors=data.get('colors', []),
            legalities=data.get('legalities', {}),
            prices=data.get('prices', {}),
            purchase_uris=data.get('purchase_uris', {}),
            cardmarket_id=data.get('cardmarket_id'),
            scryfall_uri=data.get('scryfall_uri', ''),
            image_uris=data.get('image_uris', {})
        )
    
    def is_legal_in_format(self, format_name: str) -> bool:
        """
        Check if the card is legal in a specific format.
        
        Args:
            format_name: Name of the format (e.g., 'commander', 'standard', 'modern')
            
        Returns:
            True if the card is legal in the format
        """
        if not self.legalities:
            return False
        
        legality = self.legalities.get(format_name.lower(), 'not_legal')
        return legality.lower() == 'legal'


class ScryfallAPIError(Exception):
    """Raised when Scryfall API calls fail."""
    pass


class ScryfallService:
    """Service for interacting with Scryfall API with local caching."""
    
    BASE_URL = "https://api.scryfall.com"
    CACHE_VERSION = "1.0"
    
    def __init__(self, cache_dir: Optional[Path] = None, cache_duration_days: int = 30):
        """
        Initialize Scryfall service with caching.
        
        Args:
            cache_dir: Directory for cache files. If None, uses default.
            cache_duration_days: How long to keep cached data (default: 30 days)
        """
        self.logger = logging.getLogger(__name__)
        
        # Set up cache directory
        if cache_dir is None:
            cache_dir = Path.home() / '.mtg_deck_builder' / 'scryfall_cache'
        
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        self.cache_duration_seconds = cache_duration_days * 24 * 60 * 60
        
        # Rate limiting (Scryfall allows ~10 requests per second, we'll be more conservative)
        self.last_request_time = 0
        self.min_request_interval = 0.15  # 150ms between requests (6.67 req/sec)
        self.max_concurrent_requests = 3  # Limit concurrent requests
        
        # Exponential backoff settings
        self.base_delay = 1.0  # Base delay in seconds
        self.max_delay = 60.0  # Maximum delay in seconds
        self.backoff_factor = 2.0  # Exponential backoff multiplier
        self.max_retries = 5  # Maximum number of retries
        
        # Batch processing settings
        self.batch_size = 100  # Process cards in batches
        self.batch_delay = 0.2  # Delay between batches in seconds
        
        # Session for connection pooling
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'MTG-Commander-Deck-Builder/1.0.0'
        })
        
        # Track failed requests to avoid repeated failures
        self.failed_cards: Set[str] = set()
        
        self.logger.info(f"Scryfall service initialized with cache dir: {self.cache_dir}")
        self.logger.info(f"Rate limiting: {1/self.min_request_interval:.1f} req/sec max, {self.max_concurrent_requests} concurrent")
    
    def get_card_data(self, card_name: str) -> Optional[CardData]:
        """
        Get card data from cache or Scryfall API.
        
        Args:
            card_name: Name of the card to look up
            
        Returns:
            CardData object if found, None otherwise
        """
        # Normalize card name for consistent caching
        normalized_name = self._normalize_card_name(card_name)
        
        # Try cache first
        cached_data = self._get_from_cache(normalized_name)
        if cached_data:
            self.logger.debug(f"Cache hit for card: {card_name}")
            return cached_data
        
        # Fetch from API
        self.logger.debug(f"Cache miss for card: {card_name}, fetching from Scryfall")
        try:
            card_data = self._fetch_from_api(normalized_name)
            if card_data:
                self._save_to_cache(normalized_name, card_data)
                return card_data
        except ScryfallAPIError as e:
            self.logger.warning(f"Failed to fetch card data for '{card_name}': {e}")
        
        return None
    
    def get_color_identity(self, card_name: str) -> List[str]:
        """
        Get color identity for a card.
        
        Args:
            card_name: Name of the card
            
        Returns:
            List of color identity letters (W, U, B, R, G)
        """
        card_data = self.get_card_data(card_name)
        if card_data:
            return card_data.color_identity
        
        # Fallback: return empty list (colorless)
        self.logger.warning(f"Could not determine color identity for '{card_name}', assuming colorless")
        return []
    
    def is_legal_commander(self, card_name: str) -> bool:
        """
        Check if a card can be a commander using Scryfall API data.
        
        Args:
            card_name: Name of the card
            
        Returns:
            True if the card can be a commander
        """
        card_data = self.get_card_data(card_name)
        if not card_data:
            self.logger.warning(f"Could not fetch card data for '{card_name}' - assuming not legal commander")
            return False
        
        type_line = card_data.type_line.lower()
        oracle_text = card_data.oracle_text.lower()
        
        # Check if it's a legendary creature
        if 'legendary' in type_line and 'creature' in type_line:
            self.logger.debug(f"'{card_name}' is a legendary creature - legal commander")
            return True
        
        # Check if it's a planeswalker that can be a commander
        if 'planeswalker' in type_line:
            # Some planeswalkers have explicit commander text
            if 'can be your commander' in oracle_text:
                self.logger.debug(f"'{card_name}' is a planeswalker with commander ability - legal commander")
                return True
            
            # Check for specific planeswalkers that can be commanders
            # (This list includes planeswalkers from Commander products)
            commander_planeswalkers = [
                'freyalise, llanowar\'s fury',
                'nahiri, the lithomancer',
                'ob nixilis of the black oath',
                'teferi, temporal archmage',
                'daretti, scrap savant'
            ]
            
            if card_data.name.lower() in commander_planeswalkers:
                self.logger.debug(f"'{card_name}' is a known commander planeswalker - legal commander")
                return True
        
        # Check for specific commander abilities in oracle text
        commander_text_patterns = [
            'can be your commander',
            'partner',  # Partner commanders
            'partner with',  # Specific partner pairs
            'friends forever',  # Un-set partner variant
            'choose a background'  # Background commanders from CLB
        ]
        
        for pattern in commander_text_patterns:
            if pattern in oracle_text:
                self.logger.debug(f"'{card_name}' has commander ability '{pattern}' - legal commander")
                return True
        
        self.logger.debug(f"'{card_name}' is not a legal commander")
        return False
    
    def is_legal_in_commander(self, card_name: str) -> bool:
        """
        Check if a card is legal in the Commander format using Scryfall API with caching.
        
        Args:
            card_name: Name of the card to check
            
        Returns:
            True if the card is legal in Commander format
        """
        normalized_name = self._normalize_card_name(card_name)
        
        # Check cache first
        cached_legality_data = self._get_legality_from_cache(normalized_name)
        if cached_legality_data:
            legalities = cached_legality_data.get('legalities', {})
            commander_legality = legalities.get('commander', 'not_legal').lower()
            is_legal = commander_legality == 'legal'
            
            if is_legal:
                self.logger.debug(f"'{card_name}' is legal in Commander format (cached)")
            else:
                self.logger.debug(f"'{card_name}' is not legal in Commander format (cached, status: {commander_legality})")
            
            return is_legal
        
        # Not in cache, fetch from API
        try:
            # Fetch card data with legalities (this will cache the result)
            api_data = self._fetch_card_with_legalities(card_name)
            if not api_data:
                self.logger.warning(f"Could not fetch legality data for '{card_name}' - assuming not legal")
                return False
            
            # Check Commander format legality
            legalities = api_data.get('legalities', {})
            commander_legality = legalities.get('commander', 'not_legal').lower()
            
            is_legal = commander_legality == 'legal'
            
            if is_legal:
                self.logger.debug(f"'{card_name}' is legal in Commander format")
            else:
                self.logger.debug(f"'{card_name}' is not legal in Commander format (status: {commander_legality})")
            
            return is_legal
            
        except Exception as e:
            self.logger.error(f"Error checking Commander legality for '{card_name}': {e}")
            return False
    
    def batch_check_commander_legality(self, card_names: List[str]) -> Dict[str, bool]:
        """
        Check Commander format legality for multiple cards efficiently with caching.
        
        Args:
            card_names: List of card names to check
            
        Returns:
            Dictionary mapping card names to legality status
        """
        if not card_names:
            return {}
        
        self.logger.info(f"Batch checking Commander legality for {len(card_names)} cards")
        
        results = {}
        unique_cards = list(set(card_names))  # Remove duplicates
        
        # First, check cache for all cards
        cached_results, uncached_cards = self._batch_check_legality_cache(unique_cards)
        results.update(cached_results)
        
        if not uncached_cards:
            self.logger.info(f"All {len(unique_cards)} cards found in legality cache")
            return {name: results.get(name, False) for name in card_names}
        
        self.logger.info(f"Found {len(cached_results)} cards in legality cache, fetching {len(uncached_cards)} from API")
        
        # Process uncached cards in batches to respect rate limits
        for i in range(0, len(uncached_cards), self.batch_size):
            batch = uncached_cards[i:i + self.batch_size]
            batch_num = (i // self.batch_size) + 1
            total_batches = (len(uncached_cards) + self.batch_size - 1) // self.batch_size
            
            self.logger.info(f"Processing legality batch {batch_num}/{total_batches} ({len(batch)} cards)")
            
            # Process batch with concurrent requests
            batch_results = self._process_legality_batch_concurrent(batch)
            results.update(batch_results)
            
            # Delay between batches (except for the last batch)
            if i + self.batch_size < len(uncached_cards):
                self.logger.debug(f"Waiting {self.batch_delay}s before next batch...")
                time.sleep(self.batch_delay)
        
        # Return results for all requested cards (including duplicates)
        return {name: results.get(name, False) for name in card_names}
    
    def _fetch_card_with_legalities(self, card_name: str) -> Optional[Dict[str, Any]]:
        """
        Fetch card data including legalities from Scryfall API.
        
        Args:
            card_name: Name of the card
            
        Returns:
            Card data with legalities if found, None otherwise
        """
        normalized_name = self._normalize_card_name(card_name)
        
        # Check cache first (but we need legalities, so check if cached data has them)
        cached_data = self._get_legality_from_cache(normalized_name)
        if cached_data is not None:
            return cached_data
        
        # Fetch from API
        try:
            self._rate_limit_with_jitter()
            
            url = f"{self.BASE_URL}/cards/named"
            params = {
                'fuzzy': normalized_name,
                'format': 'json'
            }
            
            response = self.session.get(url, params=params, timeout=15)
            
            if response.status_code == 429:
                retry_after = int(response.headers.get('Retry-After', 1))
                raise ScryfallAPIError(f"Rate limited, retry after {retry_after}s")
            
            if response.status_code == 200:
                api_data = response.json()
                # Cache the result with legalities
                self._save_legality_to_cache(normalized_name, api_data)
                return api_data
            elif response.status_code == 404:
                self.logger.debug(f"Card not found on Scryfall: {card_name}")
                return None
            else:
                raise ScryfallAPIError(f"API request failed with status {response.status_code}")
                
        except requests.RequestException as e:
            raise ScryfallAPIError(f"Network error: {e}")
    
    def _process_legality_batch_concurrent(self, card_names: List[str]) -> Dict[str, bool]:
        """
        Process a batch of cards for legality checking with limited concurrency.
        
        Args:
            card_names: List of card names in this batch
            
        Returns:
            Dictionary mapping card names to legality status
        """
        results = {}
        
        with ThreadPoolExecutor(max_workers=self.max_concurrent_requests) as executor:
            # Submit all requests
            future_to_card = {
                executor.submit(self._check_single_card_legality_with_retry, card_name): card_name
                for card_name in card_names
            }
            
            # Collect results as they complete
            for future in as_completed(future_to_card):
                card_name = future_to_card[future]
                try:
                    is_legal = future.result()
                    results[card_name] = is_legal
                except Exception as e:
                    self.logger.warning(f"Failed to check legality for {card_name}: {e}")
                    results[card_name] = False
        
        return results
    
    def _check_single_card_legality_with_retry(self, card_name: str) -> bool:
        """
        Check legality for a single card with retry logic and caching.
        
        Args:
            card_name: Name of the card to check
            
        Returns:
            True if legal in Commander format
        """
        normalized_name = self._normalize_card_name(card_name)
        
        # Check cache first
        cached_legality_data = self._get_legality_from_cache(normalized_name)
        if cached_legality_data:
            legalities = cached_legality_data.get('legalities', {})
            commander_legality = legalities.get('commander', 'not_legal').lower()
            is_legal = commander_legality == 'legal'
            self.logger.debug(f"Legality cache hit for {card_name}: {is_legal}")
            return is_legal
        
        # Not in cache, fetch from API with retry
        for attempt in range(self.max_retries + 1):
            try:
                # Use the method that caches legality data
                api_data = self._fetch_card_with_legalities(card_name)
                if not api_data:
                    # Card not found, cache negative result
                    negative_result = {
                        'name': card_name,
                        'legalities': {'commander': 'not_legal'}
                    }
                    self._save_legality_to_cache(normalized_name, negative_result)
                    return False
                
                # Extract legality and return result (data is already cached by _fetch_card_with_legalities)
                legalities = api_data.get('legalities', {})
                commander_legality = legalities.get('commander', 'not_legal').lower()
                is_legal = commander_legality == 'legal'
                
                self.logger.debug(f"Fetched legality for {card_name}: {is_legal}")
                return is_legal
                
            except ScryfallAPIError as e:
                if "404" in str(e):
                    # Card not found, cache negative result and don't retry
                    negative_result = {
                        'name': card_name,
                        'legalities': {'commander': 'not_legal'}
                    }
                    self._save_legality_to_cache(normalized_name, negative_result)
                    return False
                
                if attempt < self.max_retries:
                    delay = self._calculate_backoff_delay(attempt)
                    self.logger.warning(f"Legality check failed for {card_name} (attempt {attempt + 1}): {e}. Retrying in {delay:.1f}s")
                    time.sleep(delay)
                else:
                    self.logger.error(f"Failed to check legality for {card_name} after {self.max_retries + 1} attempts: {e}")
                    # Mark as failed to avoid future attempts
                    self.failed_cards.add(normalized_name)
                    return False
            except Exception as e:
                if attempt < self.max_retries:
                    delay = self._calculate_backoff_delay(attempt)
                    self.logger.warning(f"Unexpected error checking legality for {card_name} (attempt {attempt + 1}): {e}. Retrying in {delay:.1f}s")
                    time.sleep(delay)
                else:
                    self.logger.error(f"Failed to check legality for {card_name} after {self.max_retries + 1} attempts: {e}")
                    # Mark as failed to avoid future attempts
                    self.failed_cards.add(normalized_name)
                    return False
        
        return False
    
    def _get_legality_cache_path(self, card_name: str) -> Path:
        """Get cache file path for legality data."""
        name_hash = hashlib.md5(card_name.encode('utf-8')).hexdigest()
        safe_name = "".join(c for c in card_name if c.isalnum() or c in (' ', '-', '_')).strip()
        safe_name = safe_name.replace(' ', '_')[:50]
        
        filename = f"legality_{safe_name}_{name_hash}.json"
        return self.cache_dir / filename
    
    def _get_legality_from_cache(self, card_name: str) -> Optional[Dict[str, Any]]:
        """Get legality data from cache if available and not expired."""
        cache_path = self._get_legality_cache_path(card_name)
        
        if not cache_path.exists():
            return None
        
        try:
            # Check if cache is expired
            cache_age = time.time() - cache_path.stat().st_mtime
            if cache_age > self.cache_duration_seconds:
                cache_path.unlink()
                return None
            
            # Load cached data
            with open(cache_path, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            
            # Verify cache version and that it has legalities
            if (cache_data.get('version') != self.CACHE_VERSION or 
                'legalities' not in cache_data.get('data', {})):
                cache_path.unlink()
                return None
            
            return cache_data['data']
            
        except (json.JSONDecodeError, KeyError, OSError):
            try:
                cache_path.unlink()
            except OSError:
                pass
            return None
    
    def _save_legality_to_cache(self, card_name: str, api_data: Dict[str, Any]) -> None:
        """Save legality data to cache."""
        cache_path = self._get_legality_cache_path(card_name)
        
        try:
            cache_data = {
                'version': self.CACHE_VERSION,
                'timestamp': time.time(),
                'card_name': card_name,
                'data': api_data
            }
            
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, indent=2, ensure_ascii=False)
                
        except OSError as e:
            self.logger.warning(f"Failed to save legality cache for {card_name}: {e}")
    
    def batch_get_color_identities(self, card_names: List[str]) -> Dict[str, List[str]]:
        """
        Get color identities for multiple cards efficiently with batching and rate limiting.
        
        Args:
            card_names: List of card names
            
        Returns:
            Dictionary mapping card names to color identities
        """
        if not card_names:
            return {}
        
        self.logger.info(f"Batch processing {len(card_names)} cards for color identity")
        
        results = {}
        unique_cards = list(set(card_names))  # Remove duplicates
        
        # First, check cache for all cards
        cached_results, uncached_cards = self._batch_check_cache(unique_cards)
        results.update(cached_results)
        
        if not uncached_cards:
            self.logger.info(f"All {len(unique_cards)} cards found in cache")
            return {name: results.get(name, []) for name in card_names}
        
        self.logger.info(f"Found {len(cached_results)} cards in cache, fetching {len(uncached_cards)} from API")
        
        # Process uncached cards in batches
        api_results = self._batch_fetch_from_api(uncached_cards)
        results.update(api_results)
        
        # Return results in original order, including duplicates
        return {name: results.get(name, []) for name in card_names}
    
    def _batch_check_cache(self, card_names: List[str]) -> tuple[Dict[str, List[str]], List[str]]:
        """
        Check cache for multiple cards at once.
        
        Args:
            card_names: List of card names to check
            
        Returns:
            Tuple of (cached_results, uncached_card_names)
        """
        cached_results = {}
        uncached_cards = []
        
        for card_name in card_names:
            normalized_name = self._normalize_card_name(card_name)
            
            # Skip cards that previously failed
            if normalized_name in self.failed_cards:
                self.logger.debug(f"Skipping previously failed card: {card_name}")
                cached_results[card_name] = []
                continue
            
            cached_data = self._get_from_cache(normalized_name)
            if cached_data:
                cached_results[card_name] = cached_data.color_identity
            else:
                uncached_cards.append(card_name)
        
        return cached_results, uncached_cards
    
    def _batch_check_legality_cache(self, card_names: List[str]) -> tuple[Dict[str, bool], List[str]]:
        """
        Check legality cache for multiple cards at once.
        
        Args:
            card_names: List of card names to check
            
        Returns:
            Tuple of (cached_results, uncached_card_names)
        """
        cached_results = {}
        uncached_cards = []
        
        for card_name in card_names:
            normalized_name = self._normalize_card_name(card_name)
            
            # Skip cards that previously failed
            if normalized_name in self.failed_cards:
                self.logger.debug(f"Skipping previously failed card for legality: {card_name}")
                cached_results[card_name] = False
                continue
            
            cached_legality_data = self._get_legality_from_cache(normalized_name)
            if cached_legality_data:
                # Extract Commander legality from cached data
                legalities = cached_legality_data.get('legalities', {})
                commander_legality = legalities.get('commander', 'not_legal').lower()
                is_legal = commander_legality == 'legal'
                cached_results[card_name] = is_legal
                self.logger.debug(f"Legality cache hit for {card_name}: {is_legal}")
            else:
                uncached_cards.append(card_name)
        
        return cached_results, uncached_cards
    
    def _batch_fetch_from_api(self, card_names: List[str]) -> Dict[str, List[str]]:
        """
        Fetch multiple cards from API with batching and rate limiting.
        
        Args:
            card_names: List of card names to fetch
            
        Returns:
            Dictionary mapping card names to color identities
        """
        results = {}
        
        # Process cards in batches
        for i in range(0, len(card_names), self.batch_size):
            batch = card_names[i:i + self.batch_size]
            batch_num = (i // self.batch_size) + 1
            total_batches = (len(card_names) + self.batch_size - 1) // self.batch_size
            
            self.logger.info(f"Processing batch {batch_num}/{total_batches} ({len(batch)} cards)")
            
            # Process batch with concurrent requests (but limited)
            batch_results = self._process_batch_concurrent(batch)
            results.update(batch_results)
            
            # Delay between batches (except for the last batch)
            if i + self.batch_size < len(card_names):
                self.logger.debug(f"Waiting {self.batch_delay}s before next batch...")
                time.sleep(self.batch_delay)
        
        return results
    
    def _process_batch_concurrent(self, card_names: List[str]) -> Dict[str, List[str]]:
        """
        Process a batch of cards with limited concurrency.
        
        Args:
            card_names: List of card names in this batch
            
        Returns:
            Dictionary mapping card names to color identities
        """
        results = {}
        
        with ThreadPoolExecutor(max_workers=self.max_concurrent_requests) as executor:
            # Submit all requests
            future_to_card = {
                executor.submit(self._fetch_single_card_with_retry, card_name): card_name
                for card_name in card_names
            }
            
            # Collect results as they complete
            for future in as_completed(future_to_card):
                card_name = future_to_card[future]
                try:
                    card_data = future.result()
                    if card_data:
                        results[card_name] = card_data.color_identity
                        # Cache the successful result
                        normalized_name = self._normalize_card_name(card_name)
                        self._save_to_cache(normalized_name, card_data)
                    else:
                        results[card_name] = []
                        # Mark as failed to avoid future attempts
                        normalized_name = self._normalize_card_name(card_name)
                        self.failed_cards.add(normalized_name)
                        
                except Exception as e:
                    self.logger.warning(f"Failed to fetch {card_name}: {e}")
                    results[card_name] = []
                    normalized_name = self._normalize_card_name(card_name)
                    self.failed_cards.add(normalized_name)
        
        return results
    
    def _fetch_single_card_with_retry(self, card_name: str) -> Optional[CardData]:
        """
        Fetch a single card with exponential backoff retry logic.
        
        Args:
            card_name: Name of the card to fetch
            
        Returns:
            CardData if successful, None otherwise
        """
        normalized_name = self._normalize_card_name(card_name)
        
        for attempt in range(self.max_retries + 1):
            try:
                # Rate limiting with jitter
                self._rate_limit_with_jitter()
                
                api_data = self._fetch_from_api_raw(normalized_name)
                if api_data:
                    return CardData.from_scryfall_data(api_data)
                else:
                    # Card not found, don't retry
                    return None
                    
            except ScryfallAPIError as e:
                if "404" in str(e):
                    # Card not found, don't retry
                    self.logger.debug(f"Card not found: {card_name}")
                    return None
                
                if attempt < self.max_retries:
                    delay = self._calculate_backoff_delay(attempt)
                    self.logger.warning(f"API error for {card_name} (attempt {attempt + 1}): {e}. Retrying in {delay:.1f}s")
                    time.sleep(delay)
                else:
                    self.logger.error(f"Failed to fetch {card_name} after {self.max_retries + 1} attempts: {e}")
                    raise
            
            except Exception as e:
                if attempt < self.max_retries:
                    delay = self._calculate_backoff_delay(attempt)
                    self.logger.warning(f"Unexpected error for {card_name} (attempt {attempt + 1}): {e}. Retrying in {delay:.1f}s")
                    time.sleep(delay)
                else:
                    self.logger.error(f"Failed to fetch {card_name} after {self.max_retries + 1} attempts: {e}")
                    return None
        
        return None
    
    def _rate_limit_with_jitter(self):
        """Apply rate limiting with jitter to avoid thundering herd."""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        if time_since_last < self.min_request_interval:
            sleep_time = self.min_request_interval - time_since_last
            # Add small random jitter (±20%)
            jitter = sleep_time * 0.2 * (random.random() - 0.5)
            sleep_time += jitter
            time.sleep(max(0, sleep_time))
        
        self.last_request_time = time.time()
    
    def _calculate_backoff_delay(self, attempt: int) -> float:
        """Calculate exponential backoff delay with jitter."""
        delay = self.base_delay * (self.backoff_factor ** attempt)
        delay = min(delay, self.max_delay)
        
        # Add jitter (±25% of delay)
        jitter = delay * 0.25 * (random.random() - 0.5)
        delay += jitter
        
        return max(0.1, delay)  # Minimum 100ms delay
    
    def _normalize_card_name(self, card_name: str) -> str:
        """Normalize card name for consistent API queries and caching."""
        # Remove extra whitespace and convert to lowercase
        normalized = card_name.strip().lower()
        
        # Handle double-faced cards - use only the front face
        if '//' in normalized:
            normalized = normalized.split('//')[0].strip()
        
        return normalized
    
    def _get_cache_path(self, card_name: str) -> Path:
        """Get cache file path for a card."""
        # Create a safe filename using hash
        name_hash = hashlib.md5(card_name.encode('utf-8')).hexdigest()
        safe_name = "".join(c for c in card_name if c.isalnum() or c in (' ', '-', '_')).strip()
        safe_name = safe_name.replace(' ', '_')[:50]  # Limit length
        
        filename = f"{safe_name}_{name_hash}.json"
        return self.cache_dir / filename
    
    def _get_from_cache(self, card_name: str) -> Optional[CardData]:
        """Get card data from cache if available and not expired."""
        cache_path = self._get_cache_path(card_name)
        
        if not cache_path.exists():
            return None
        
        try:
            # Check if cache is expired
            cache_age = time.time() - cache_path.stat().st_mtime
            if cache_age > self.cache_duration_seconds:
                self.logger.debug(f"Cache expired for {card_name}, age: {cache_age/86400:.1f} days")
                cache_path.unlink()  # Remove expired cache
                return None
            
            # Load cached data
            with open(cache_path, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            
            # Verify cache version
            if cache_data.get('version') != self.CACHE_VERSION:
                self.logger.debug(f"Cache version mismatch for {card_name}")
                cache_path.unlink()
                return None
            
            return CardData.from_dict(cache_data['data'])
            
        except (json.JSONDecodeError, KeyError, OSError) as e:
            self.logger.warning(f"Failed to load cache for {card_name}: {e}")
            # Remove corrupted cache file
            try:
                cache_path.unlink()
            except OSError:
                pass
            return None
    
    def _save_to_cache(self, card_name: str, card_data: CardData) -> None:
        """Save card data to cache."""
        cache_path = self._get_cache_path(card_name)
        
        try:
            cache_data = {
                'version': self.CACHE_VERSION,
                'timestamp': time.time(),
                'card_name': card_name,
                'data': card_data.to_dict()
            }
            
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, indent=2, ensure_ascii=False)
                
            self.logger.debug(f"Cached data for card: {card_name}")
            
        except OSError as e:
            self.logger.warning(f"Failed to save cache for {card_name}: {e}")
    
    def _fetch_from_api(self, card_name: str) -> Optional[Dict[str, Any]]:
        """Fetch card data from Scryfall API (legacy method for single requests)."""
        return self._fetch_single_card_with_retry(card_name)
    
    def _fetch_from_api_raw(self, card_name: str) -> Optional[Dict[str, Any]]:
        """Fetch card data from Scryfall API without retry logic."""
        try:
            # Use named search endpoint
            url = f"{self.BASE_URL}/cards/named"
            params = {
                'fuzzy': card_name,
                'format': 'json'
            }
            
            self.logger.debug(f"Fetching from Scryfall: {card_name}")
            response = self.session.get(url, params=params, timeout=15)
            
            # Check for rate limiting
            if response.status_code == 429:
                retry_after = int(response.headers.get('Retry-After', 1))
                raise ScryfallAPIError(f"Rate limited, retry after {retry_after}s")
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 404:
                self.logger.debug(f"Card not found on Scryfall: {card_name}")
                return None
            elif response.status_code >= 500:
                raise ScryfallAPIError(f"Server error {response.status_code}: {response.text}")
            else:
                raise ScryfallAPIError(f"API request failed with status {response.status_code}: {response.text}")
                
        except requests.Timeout:
            raise ScryfallAPIError("Request timeout")
        except requests.ConnectionError as e:
            raise ScryfallAPIError(f"Connection error: {e}")
        except requests.RequestException as e:
            raise ScryfallAPIError(f"Network error: {e}")
        except json.JSONDecodeError as e:
            raise ScryfallAPIError(f"Invalid JSON response: {e}")
    
    def clear_cache(self) -> None:
        """Clear all cached data."""
        try:
            for cache_file in self.cache_dir.glob("*.json"):
                cache_file.unlink()
            self.logger.info("Cache cleared successfully")
        except OSError as e:
            self.logger.error(f"Failed to clear cache: {e}")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics including legality cache."""
        cache_files = list(self.cache_dir.glob("*.json"))
        legality_files = list(self.cache_dir.glob("legality_*.json"))
        color_identity_files = [f for f in cache_files if not f.name.startswith("legality_")]
        
        total_size = sum(f.stat().st_size for f in cache_files)
        legality_size = sum(f.stat().st_size for f in legality_files)
        color_identity_size = sum(f.stat().st_size for f in color_identity_files)
        
        return {
            'cache_dir': str(self.cache_dir),
            'total_cached_cards': len(cache_files),
            'color_identity_cached': len(color_identity_files),
            'legality_cached': len(legality_files),
            'total_size_bytes': total_size,
            'total_size_mb': total_size / (1024 * 1024),
            'legality_cache_size_mb': legality_size / (1024 * 1024),
            'color_identity_cache_size_mb': color_identity_size / (1024 * 1024)
        }
    
    def get_purchase_suggestions(self, recommendations: List, collection_cards: Set[str], max_suggestions: int = 10) -> List[CardData]:
        """
        Get purchase suggestions for cards not in collection with pricing data.
        
        Args:
            recommendations: List of CardRecommendation objects from EDHREC
            collection_cards: Set of normalized card names in collection
            max_suggestions: Maximum number of suggestions to return
            
        Returns:
            List of CardData objects with pricing information
        """
        suggestions = []
        
        # Sort recommendations by synergy score (highest first)
        sorted_recs = sorted(recommendations, key=lambda x: x.synergy_score, reverse=True)
        
        for rec in sorted_recs:
            if len(suggestions) >= max_suggestions:
                break
                
            # Skip if card is already in collection
            normalized_name = rec.name.lower().strip()
            if normalized_name in collection_cards:
                continue
            
            # Get full card data with pricing
            card_data = self.get_card_data(rec.name)
            if card_data and card_data.is_legal_in_format('commander'):
                suggestions.append(card_data)
        
        return suggestions