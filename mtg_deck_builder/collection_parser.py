"""
Collection parser module for handling CSV card collection data.

This module provides functionality to parse MTG card collection CSV files,
normalize card names, and validate commanders for deck building.
"""

import csv
import re
import logging
from pathlib import Path
from typing import Dict, List, Optional, Set
from .models import CardEntry


class CollectionParseError(Exception):
    """Raised when CSV parsing fails."""
    pass


class CommanderNotFoundError(Exception):
    """Raised when commander is not found in collection."""
    pass


class CollectionParser:
    """Handles parsing and processing of MTG card collection CSV files."""
    
    # Common CSV column headers that might contain card names
    CARD_NAME_HEADERS = {
        'name', 'card_name', 'cardname', 'card name', 'title',
        'card', 'card_title', 'cardtitle'
    }
    
    # Common CSV column headers that might contain quantities
    QUANTITY_HEADERS = {
        'quantity', 'qty', 'count', 'amount', 'copies', 'owned'
    }
    
    # Common CSV column headers that might contain set codes
    SET_HEADERS = {
        'set', 'set_code', 'setcode', 'set code', 'expansion',
        'edition', 'set_name', 'setname'
    }
    
    def __init__(self, scryfall_service=None):
        """Initialize the collection parser."""
        self.logger = logging.getLogger(__name__)
        self._legendary_creatures = self._load_known_commanders()
        # Import here to avoid circular imports
        if scryfall_service is None:
            from .scryfall_service import ScryfallService
            scryfall_service = ScryfallService()
        self.scryfall = scryfall_service
    
    def load_collection(self, csv_path: str) -> Dict[str, CardEntry]:
        """
        Load and parse a CSV file containing card collection data.
        
        Args:
            csv_path: Path to the CSV file
            
        Returns:
            Dictionary mapping normalized card names to CardEntry objects
            
        Raises:
            CollectionParseError: If CSV parsing fails
            FileNotFoundError: If CSV file doesn't exist
        """
        csv_file = Path(csv_path)
        
        if not csv_file.exists():
            raise FileNotFoundError(f"CSV file not found: {csv_path}")
        
        if not csv_file.is_file():
            raise CollectionParseError(f"Path is not a file: {csv_path}")
        
        try:
            with open(csv_file, 'r', encoding='utf-8', newline='') as file:
                # Try to detect delimiter
                sample = file.read(1024)
                file.seek(0)
                
                delimiter = self._detect_delimiter(sample)
                
                reader = csv.DictReader(file, delimiter=delimiter)
                
                # Validate headers
                original_headers = reader.fieldnames or []
                headers = [h.lower().strip() if h else '' for h in original_headers]
                name_col, qty_col, set_col = self._identify_columns(headers, original_headers)
                
                if not name_col:
                    raise CollectionParseError(
                        f"Could not identify card name column. Available headers: {reader.fieldnames}"
                    )
                
                collection = {}
                line_number = 1  # Header is line 1, data starts at line 2
                
                for row in reader:
                    line_number += 1
                    try:
                        card_entry = self._parse_row(row, name_col, qty_col, set_col, line_number)
                        if card_entry:
                            # Use normalized name as key to handle duplicates
                            existing = collection.get(card_entry.normalized_name)
                            if existing:
                                # Combine quantities for duplicate entries
                                existing.quantity += card_entry.quantity
                            else:
                                collection[card_entry.normalized_name] = card_entry
                    except Exception as e:
                        raise CollectionParseError(
                            f"Error parsing line {line_number}: {str(e)}"
                        )
                
                if not collection:
                    raise CollectionParseError("No valid card entries found in CSV file")
                
                return collection
                
        except UnicodeDecodeError as e:
            raise CollectionParseError(f"File encoding error: {str(e)}")
        except csv.Error as e:
            raise CollectionParseError(f"CSV parsing error: {str(e)}")
    
    def _detect_delimiter(self, sample: str) -> str:
        """
        Detect the CSV delimiter from a sample of the file.
        
        Args:
            sample: Sample text from the CSV file
            
        Returns:
            Detected delimiter character
        """
        # Common delimiters in order of preference
        delimiters = [',', ';', '\t', '|']
        
        for delimiter in delimiters:
            if delimiter in sample:
                # Count occurrences in first few lines
                lines = sample.split('\n')[:3]  # Check first 3 lines
                counts = [line.count(delimiter) for line in lines if line.strip()]
                
                # If delimiter appears consistently, it's likely correct
                if len(counts) >= 2 and len(set(counts)) == 1 and counts[0] > 0:
                    return delimiter
        
        # Default to comma
        return ','
    
    def _identify_columns(self, headers: List[str], original_headers: List[str]) -> tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Identify which columns contain card names, quantities, and set codes.
        
        Args:
            headers: List of column headers (lowercase)
            original_headers: List of original column headers (with original case)
            
        Returns:
            Tuple of (name_column, quantity_column, set_column) using original case
        """
        name_col = None
        qty_col = None
        set_col = None
        
        for i, header in enumerate(headers):
            header_clean = header.lower().strip()
            original_header = original_headers[i] if i < len(original_headers) else header
            
            if not name_col and header_clean in self.CARD_NAME_HEADERS:
                name_col = original_header
            elif not qty_col and header_clean in self.QUANTITY_HEADERS:
                qty_col = original_header
            elif not set_col and header_clean in self.SET_HEADERS:
                set_col = original_header
        
        # If we couldn't find specific headers, make educated guesses
        if not name_col and original_headers:
            # Look for any header containing 'name'
            for i, header in enumerate(headers):
                if 'name' in header and not any(x in header for x in ['binder', 'set', 'file']):
                    name_col = original_headers[i]
                    break
            
            # If still not found, use first column
            if not name_col:
                name_col = original_headers[0]
        
        return name_col, qty_col, set_col
    
    def _parse_row(self, row: Dict[str, str], name_col: str, qty_col: Optional[str], 
                   set_col: Optional[str], line_number: int) -> Optional[CardEntry]:
        """
        Parse a single CSV row into a CardEntry.
        
        Args:
            row: Dictionary representing a CSV row
            name_col: Column name containing card names
            qty_col: Column name containing quantities (optional)
            set_col: Column name containing set codes (optional)
            line_number: Current line number for error reporting
            
        Returns:
            CardEntry object or None if row should be skipped
            
        Raises:
            CollectionParseError: If row parsing fails
        """
        # Get card name
        card_name = row.get(name_col, '').strip()
        if not card_name:
            # Skip empty rows
            return None
        
        # Get quantity
        quantity = 1  # Default quantity
        if qty_col and qty_col in row:
            qty_str = row[qty_col].strip()
            if qty_str:
                try:
                    quantity = int(float(qty_str))  # Handle "1.0" format
                    if quantity <= 0:
                        raise CollectionParseError(f"Invalid quantity '{qty_str}' (must be positive)")
                except ValueError:
                    raise CollectionParseError(f"Invalid quantity format: '{qty_str}'")
        
        # Get set code
        set_code = ""
        if set_col and set_col in row:
            set_code = row[set_col].strip()
        
        card_entry = CardEntry(
            name=card_name,
            quantity=quantity,
            set_code=set_code
        )
        
        # Override the normalized name with our more comprehensive normalization
        card_entry.normalized_name = self.normalize_card_name(card_name)
        
        return card_entry
    
    def _load_known_commanders(self) -> Set[str]:
        """
        Load a set of known legendary creatures that can be commanders.
        
        Returns:
            Set of normalized commander names
            
        Note: In a full implementation, this would load from a comprehensive
        card database. For now, we'll use a basic set of common commanders.
        """
        # Basic set of well-known commanders for validation
        # In production, this would be loaded from a card database
        known_commanders = {
            'atraxa, praetors\' voice',
            'edgar markov',
            'the ur-dragon',
            'meren of clan nel toth',
            'karador, ghost chieftain',
            'prossh, skyraider of kher',
            'derevi, empyrial tactician',
            'oloro, ageless ascetic',
            'nekusar, the mindrazer',
            'ghave, guru of spores',
            'animar, soul of elements',
            'zur the enchanter',
            'rafiq of the many',
            'sharuum the hegemon',
            'mayael the anima'
        }
        
        return known_commanders 
   
    def normalize_card_name(self, name: str) -> str:
        """
        Normalize card name for consistent lookups and matching.
        
        This function handles various card name variations and formats to ensure
        consistent matching with EDHREC and other card databases.
        
        Args:
            name: Raw card name from collection
            
        Returns:
            Normalized card name
        """
        if not name or not isinstance(name, str):
            return ""
        
        # Start with the original name
        normalized = name.strip()
        
        # Remove extra whitespace and normalize spacing
        normalized = re.sub(r'\s+', ' ', normalized)
        
        # Handle common card name variations
        normalized = self._handle_special_characters(normalized)
        normalized = self._handle_alternate_printings(normalized)
        normalized = self._handle_double_faced_cards(normalized)
        normalized = self._handle_split_cards(normalized)
        normalized = self._handle_common_abbreviations(normalized)
        
        # Final cleanup
        normalized = normalized.strip().lower()
        
        return normalized
    
    def _handle_special_characters(self, name: str) -> str:
        """Handle special characters and punctuation in card names."""
        # Replace smart quotes with regular quotes
        name = name.replace('"', '"').replace('"', '"')
        name = name.replace(''', "'").replace(''', "'")
        
        # Handle æ character (common in Magic cards)
        name = name.replace('Æ', 'Ae').replace('æ', 'ae')
        
        # Handle ö and other accented characters
        name = name.replace('ö', 'o').replace('Ö', 'O')
        name = name.replace('ä', 'a').replace('Ä', 'A')
        name = name.replace('ü', 'u').replace('Ü', 'U')
        
        # Normalize dashes and hyphens
        name = re.sub(r'[–—−]', '-', name)
        
        # Remove or normalize other special characters
        name = name.replace('™', '').replace('®', '')
        
        return name
    
    def _handle_alternate_printings(self, name: str) -> str:
        """Remove alternate printing indicators and collector info."""
        # Remove parenthetical information (often alternate art or collector info)
        name = re.sub(r'\s*\([^)]*\)\s*', ' ', name)
        
        # Remove square bracket information
        name = re.sub(r'\s*\[[^\]]*\]\s*', ' ', name)
        
        # Remove version numbers and suffixes
        name = re.sub(r'\s*v\d+\s*$', '', name, flags=re.IGNORECASE)
        name = re.sub(r'\s*#\d+.*$', '', name)
        
        return name.strip()
    
    def _handle_double_faced_cards(self, name: str) -> str:
        """Handle double-faced and transform cards."""
        # For double-faced cards, use only the front face name
        if '//' in name:
            name = name.split('//')[0].strip()
        
        # Handle transform cards with " // " separator
        if ' // ' in name:
            name = name.split(' // ')[0].strip()
        
        return name
    
    def _handle_split_cards(self, name: str) -> str:
        """Handle split cards and fuse cards."""
        # Split cards often use " // " or " / " as separators
        # For consistency, we'll use the full name as-is for split cards
        # unless it's clearly a transform card (handled above)
        
        # Handle aftermath cards (use full name)
        if ' // ' in name and not self._is_transform_card(name):
            # Keep the full split card name for split/fuse cards
            pass
        
        return name
    
    def _handle_common_abbreviations(self, name: str) -> str:
        """Expand common abbreviations in card names."""
        # Common abbreviations that might appear in collection data
        abbreviations = {
            r'\bst\b': 'saint',
            r'\bmt\b': 'mount',
            r'\bdr\b': 'doctor',
            r'\bmr\b': 'mister',
            r'\bms\b': 'miss',
            r'\bprof\b': 'professor',
        }
        
        for abbrev, expansion in abbreviations.items():
            name = re.sub(abbrev, expansion, name, flags=re.IGNORECASE)
        
        return name
    
    def _is_transform_card(self, name: str) -> bool:
        """
        Determine if a card with '//' is a transform card vs split card.
        
        This is a heuristic - in a full implementation, this would
        reference a card database.
        """
        # Transform cards typically have very different names on each side
        # Split cards typically have related names
        if '//' not in name:
            return False
        
        parts = [part.strip() for part in name.split('//')]
        if len(parts) != 2:
            return False
        
        # Simple heuristic: if the names share no common words (except articles),
        # it's likely a transform card
        words1 = set(parts[0].lower().split())
        words2 = set(parts[1].lower().split())
        
        # Remove common articles and conjunctions
        common_words = {'the', 'a', 'an', 'of', 'and', 'or', 'to', 'in', 'on', 'at'}
        words1 -= common_words
        words2 -= common_words
        
        # If no words in common, likely a transform card
        return len(words1.intersection(words2)) == 0
    
    def create_name_lookup_table(self, collection: Dict[str, CardEntry]) -> Dict[str, str]:
        """
        Create a lookup table for resolving card name variations.
        
        Args:
            collection: Dictionary of normalized names to CardEntry objects
            
        Returns:
            Dictionary mapping various name formats to normalized names
        """
        lookup_table = {}
        
        for normalized_name, card_entry in collection.items():
            original_name = card_entry.name
            
            # Add the original name as a lookup
            lookup_table[original_name.lower()] = normalized_name
            
            # Add the normalized name as a lookup to itself
            lookup_table[normalized_name] = normalized_name
            
            # Add variations without punctuation
            no_punct = re.sub(r'[^\w\s]', '', original_name).lower()
            if no_punct != normalized_name:
                lookup_table[no_punct] = normalized_name
            
            # Add variations without "the" at the beginning
            if original_name.lower().startswith('the '):
                without_the = original_name[4:].lower()
                lookup_table[without_the] = normalized_name
            
            # Add variations with common misspellings or alternate spellings
            lookup_table.update(self._generate_common_variations(original_name, normalized_name))
        
        return lookup_table
    
    def _generate_common_variations(self, original_name: str, normalized_name: str) -> Dict[str, str]:
        """Generate common variations and misspellings for a card name."""
        variations = {}
        
        # Handle common character substitutions
        name_lower = original_name.lower()
        
        # Common substitutions in card names
        substitutions = [
            ('ae', 'e'),  # Aether -> Ether
            ('ou', 'o'),  # Colour -> Color
            ('ise', 'ize'),  # Realise -> Realize
            ("'", ''),  # Remove apostrophes
            ('-', ' '),  # Hyphens to spaces
            (' ', ''),  # Remove all spaces
        ]
        
        for old, new in substitutions:
            if old in name_lower:
                variation = name_lower.replace(old, new)
                if variation != normalized_name:
                    variations[variation] = normalized_name
        
        return variations
    
    def resolve_card_name(self, name: str, lookup_table: Dict[str, str]) -> Optional[str]:
        """
        Resolve a card name using the lookup table.
        
        Args:
            name: Card name to resolve
            lookup_table: Lookup table created by create_name_lookup_table()
            
        Returns:
            Normalized card name if found, None otherwise
        """
        if not name:
            return None
        
        # Try exact match first
        normalized_input = self.normalize_card_name(name)
        if normalized_input in lookup_table:
            return lookup_table[normalized_input]
        
        # Try original name
        if name.lower() in lookup_table:
            return lookup_table[name.lower()]
        
        # Try fuzzy matching for close matches
        return self._fuzzy_match_name(name, lookup_table)
    
    def _fuzzy_match_name(self, name: str, lookup_table: Dict[str, str]) -> Optional[str]:
        """
        Attempt fuzzy matching for card names.
        
        This is a simple implementation - in production, you might use
        more sophisticated fuzzy matching algorithms.
        """
        name_lower = name.lower().strip()
        
        # Try matching without punctuation and extra spaces
        clean_name = re.sub(r'[^\w\s]', '', name_lower)
        clean_name = re.sub(r'\s+', ' ', clean_name).strip()
        
        for lookup_key, normalized_name in lookup_table.items():
            clean_key = re.sub(r'[^\w\s]', '', lookup_key)
            clean_key = re.sub(r'\s+', ' ', clean_key).strip()
            
            if clean_name == clean_key:
                return normalized_name
        
        # Try partial matching (for cases where input has extra info)
        for lookup_key, normalized_name in lookup_table.items():
            if lookup_key in name_lower or name_lower in lookup_key:
                # Only match if the similarity is high enough
                if len(lookup_key) > 3 and len(name_lower) > 3:
                    return normalized_name
        
        return None
    
    def validate_commander(self, commander_name: str, collection: Dict[str, CardEntry]) -> bool:
        """
        Validate that a commander exists in the collection and is legal.
        
        Args:
            commander_name: Name of the proposed commander
            collection: Dictionary of normalized names to CardEntry objects
            
        Returns:
            True if commander is valid and available
            
        Raises:
            CommanderNotFoundError: If commander is not found or invalid
        """
        if not commander_name or not isinstance(commander_name, str):
            raise CommanderNotFoundError("Commander name cannot be empty")
        
        # Normalize the commander name for lookup
        normalized_commander = self.normalize_card_name(commander_name)
        
        # Check if commander exists in collection
        if normalized_commander not in collection:
            # Try to find it using fuzzy matching
            lookup_table = self.create_name_lookup_table(collection)
            resolved_name = self.resolve_card_name(commander_name, lookup_table)
            
            if not resolved_name:
                available_commanders = self._suggest_similar_commanders(
                    commander_name, collection
                )
                suggestion_text = ""
                if available_commanders:
                    suggestion_text = f" Did you mean one of: {', '.join(available_commanders[:3])}?"
                
                raise CommanderNotFoundError(
                    f"Commander '{commander_name}' not found in collection.{suggestion_text}"
                )
            
            normalized_commander = resolved_name
        
        # Verify commander legality using Scryfall API
        if not self._is_legal_commander_with_scryfall(commander_name):
            raise CommanderNotFoundError(
                f"'{commander_name}' is not a legal commander (must be a legendary creature "
                "or have rules text allowing it to be your commander)"
            )
        
        return True
    
    def _is_legal_commander(self, normalized_name: str, card_entry: CardEntry) -> bool:
        """
        Check if a card is legal as a commander.
        
        Args:
            normalized_name: Normalized card name
            card_entry: CardEntry object for the card
            
        Returns:
            True if the card can legally be a commander
        """
        # Check against known commanders list
        if normalized_name in self._legendary_creatures:
            return True
        
        # Check for common commander indicators in the name
        # This is a heuristic approach - in production, this would
        # reference a comprehensive card database
        commander_indicators = [
            'legendary creature',
            'legendary artifact creature',
            'legendary enchantment creature',
            'planeswalker',  # Some planeswalkers can be commanders
        ]
        
        # For now, we'll use name-based heuristics and the known list
        # In a full implementation, this would check the card's actual type line
        
        # Check if name suggests it's a legendary creature
        name_lower = card_entry.name.lower()
        
        # Many legendary creatures have titles or descriptive names
        legendary_patterns = [
            r'\b(king|queen|lord|lady|prince|princess|emperor|empress)\b',
            r'\b(captain|general|admiral|commander|chief)\b',
            r'\b(master|mistress|sage|elder|ancient)\b',
            r'\b(the|of|from)\b.*\b(the|of|from)\b',  # Often have "X of Y" or "X the Y" pattern
        ]
        
        for pattern in legendary_patterns:
            if re.search(pattern, name_lower):
                return True
        
        # Check for planeswalker names (often single names or "Name, Title")
        if ',' in card_entry.name and len(card_entry.name.split(',')) == 2:
            # Pattern like "Jace, the Mind Sculptor"
            return True
        
        # If we can't determine from heuristics, be conservative
        # In production, this would always check against a card database
        return False
    
    def _is_legal_commander_with_scryfall(self, commander_name: str) -> bool:
        """
        Check if a card is a legal commander using Scryfall API.
        
        Args:
            commander_name: Name of the commander to check
            
        Returns:
            True if the card can legally be a commander
        """
        try:
            # Use Scryfall service to check commander legality
            is_legal = self.scryfall.is_legal_commander(commander_name)
            
            if is_legal:
                # Also verify the card is legal in Commander format
                is_format_legal = self.scryfall.is_legal_in_commander(commander_name)
                if not is_format_legal:
                    self.logger.warning(f"'{commander_name}' can be a commander but is not legal in Commander format")
                    return False
            
            return is_legal
            
        except Exception as e:
            self.logger.warning(f"Error checking commander legality for '{commander_name}' via Scryfall: {e}")
            # Fall back to heuristic method if we have the card entry
            # For now, return False if Scryfall check fails
            return False
    
    def _suggest_similar_commanders(self, commander_name: str, 
                                   collection: Dict[str, CardEntry]) -> List[str]:
        """
        Suggest similar commander names from the collection.
        
        Args:
            commander_name: The commander name that wasn't found
            collection: Dictionary of available cards
            
        Returns:
            List of suggested commander names
        """
        suggestions = []
        commander_lower = commander_name.lower()
        
        # Look for cards that might be commanders
        for normalized_name, card_entry in collection.items():
            # Check if it's a potential commander
            if self._is_legal_commander(normalized_name, card_entry):
                original_name = card_entry.name
                
                # Calculate similarity
                if self._names_are_similar(commander_lower, original_name.lower()):
                    suggestions.append(original_name)
        
        # Sort by similarity (simple length difference for now)
        suggestions.sort(key=lambda x: abs(len(x) - len(commander_name)))
        
        return suggestions[:5]  # Return top 5 suggestions
    
    def _names_are_similar(self, name1: str, name2: str) -> bool:
        """
        Check if two names are similar enough to suggest as alternatives.
        
        Args:
            name1: First name (lowercase)
            name2: Second name (lowercase)
            
        Returns:
            True if names are similar
        """
        # Simple similarity checks
        
        # Check if one name contains the other (with minimum length)
        if len(name1) >= 4 and len(name2) >= 4:
            if name1 in name2 or name2 in name1:
                return True
        
        # Check if they share significant words
        words1 = set(name1.split())
        words2 = set(name2.split())
        
        # Remove common words and punctuation
        common_words = {'the', 'a', 'an', 'of', 'and', 'or', 'to', 'in', 'on', 'at', ','}
        words1 = {word.strip('.,;:') for word in words1} - common_words
        words2 = {word.strip('.,;:') for word in words2} - common_words
        
        if not words1 or not words2:
            return False
        
        # If they share at least one significant word (minimum 3 characters)
        shared_words = words1.intersection(words2)
        significant_shared = [word for word in shared_words if len(word) >= 3]
        return len(significant_shared) > 0
    
    def get_commander_from_collection(self, commander_name: str, 
                                    collection: Dict[str, CardEntry]) -> CardEntry:
        """
        Get the CardEntry for a commander from the collection.
        
        Args:
            commander_name: Name of the commander to find
            collection: Dictionary of normalized names to CardEntry objects
            
        Returns:
            CardEntry object for the commander
            
        Raises:
            CommanderNotFoundError: If commander is not found or invalid
        """
        # Validate the commander first
        self.validate_commander(commander_name, collection)
        
        # Get the normalized name
        normalized_commander = self.normalize_card_name(commander_name)
        
        # If direct lookup fails, use fuzzy matching (validation ensures it exists)
        if normalized_commander not in collection:
            lookup_table = self.create_name_lookup_table(collection)
            resolved_name = self.resolve_card_name(commander_name, lookup_table)
            if resolved_name:
                normalized_commander = resolved_name
        
        return collection[normalized_commander]
    
    def list_available_commanders(self, collection: Dict[str, CardEntry]) -> List[str]:
        """
        List all potential commanders available in the collection.
        
        Args:
            collection: Dictionary of normalized names to CardEntry objects
            
        Returns:
            List of commander names available in the collection
        """
        commanders = []
        
        for normalized_name, card_entry in collection.items():
            if self._is_legal_commander(normalized_name, card_entry):
                commanders.append(card_entry.name)
        
        # Sort alphabetically
        commanders.sort()
        
        return commanders