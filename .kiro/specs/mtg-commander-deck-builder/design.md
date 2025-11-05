# Design Document

## Overview

The MTG Commander Deck Builder is a Python command-line application that generates optimized Commander deck lists from a user's card collection. The tool integrates with EDHREC through the pyedhrec package to fetch card synergy data and builds legal, playable decks using only available cards.

## Architecture

The application follows a modular architecture with clear separation of concerns:

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   CLI Interface │────│  Deck Builder    │────│  Output Manager │
│                 │    │     Engine       │    │                 │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                              │
                    ┌─────────┼─────────┐
                    │                   │
            ┌───────▼────────┐  ┌───────▼────────┐
            │ Collection     │  │ EDHREC Service │
            │   Parser       │  │                │
            └────────────────┘  └────────────────┘
```

## Components and Interfaces

### 1. CLI Interface (`cli.py`)
**Purpose:** Handle command-line argument parsing and user interaction

**Key Methods:**
- `parse_arguments()` - Parse CSV file path and commander name
- `validate_inputs()` - Check file existence and accessibility
- `main()` - Entry point orchestrating the deck building process

**Dependencies:** argparse, pathlib

### 2. Collection Parser (`collection_parser.py`)
**Purpose:** Parse and normalize card collection data from CSV

**Key Methods:**
- `load_collection(csv_path: str) -> Dict[str, CardEntry]` - Load and parse CSV
- `normalize_card_name(name: str) -> str` - Standardize card names
- `validate_commander(commander: str, collection: Dict) -> bool` - Check commander availability

**Data Structures:**
```python
@dataclass
class CardEntry:
    name: str
    quantity: int
    set_code: str
    normalized_name: str
```

### 3. EDHREC Service (`edhrec_service.py`)
**Purpose:** Interface with pyedhrec package for card recommendations

**Key Methods:**
- `get_commander_recommendations(commander: str) -> List[CardRecommendation]` - Fetch EDHREC data
- `get_card_synergy_score(card: str, commander: str) -> float` - Calculate synergy ratings
- `handle_api_errors()` - Manage network and API failures

**Data Structures:**
```python
@dataclass
class CardRecommendation:
    name: str
    synergy_score: float
    category: str  # 'staple', 'synergy', 'budget', etc.
    inclusion_percentage: float
```

### 4. Deck Builder Engine (`deck_builder.py`)
**Purpose:** Core logic for generating legal Commander decks

**Key Methods:**
- `build_deck(commander: str, collection: Dict, recommendations: List) -> Deck` - Main deck building logic
- `select_mana_base(colors: List[str], collection: Dict) -> List[str]` - Choose lands
- `balance_mana_curve(available_cards: List, target_curve: Dict) -> List[str]` - Optimize curve
- `enforce_singleton_rule(deck: List[str]) -> List[str]` - Ensure no duplicates

**Algorithm Flow:**
1. Validate commander and extract color identity
2. Filter collection by color identity restrictions
3. Categorize available cards (removal, ramp, draw, etc.)
4. Select cards based on EDHREC synergy scores and deck balance
5. Fill remaining slots with best available options
6. Validate final deck meets all format rules

### 5. Output Manager (`output_manager.py`)
**Purpose:** Handle file output and naming conventions

**Key Methods:**
- `generate_filename(commander: str) -> str` - Create unique filenames with timestamps
- `format_deck_list(deck: Deck) -> str` - Format deck for text output
- `write_deck_file(deck: Deck, filename: str)` - Write deck to file
- `generate_deck_statistics(deck: Deck) -> str` - Create summary statistics

## Data Models

### Core Data Structures

```python
@dataclass
class Deck:
    commander: str
    cards: List[str]  # 99 non-commander cards
    mana_base: List[str]
    color_identity: List[str]
    total_cmc: float
    
    def validate(self) -> bool:
        """Ensure deck meets Commander format rules"""
        return len(self.cards) + len([self.commander]) == 100

@dataclass
class DeckStatistics:
    card_types: Dict[str, int]  # creature, instant, sorcery, etc.
    mana_curve: Dict[int, int]  # CMC distribution
    color_distribution: Dict[str, int]
    average_cmc: float
    synergy_score: float
```

### Configuration

```python
class DeckBuildingConfig:
    MIN_LANDS = 35
    MAX_LANDS = 40
    PREFERRED_CREATURE_COUNT = 25
    PREFERRED_NONCREATURE_SPELLS = 35
    SYNERGY_WEIGHT = 0.7
    AVAILABILITY_WEIGHT = 0.3
```

## Error Handling

### Exception Hierarchy
```python
class DeckBuilderError(Exception):
    """Base exception for deck builder errors"""

class CollectionParseError(DeckBuilderError):
    """Raised when CSV parsing fails"""

class CommanderNotFoundError(DeckBuilderError):
    """Raised when commander is not in collection"""

class InsufficientCardsError(DeckBuilderError):
    """Raised when collection lacks enough cards for full deck"""

class EDHRECAPIError(DeckBuilderError):
    """Raised when EDHREC API calls fail"""
```

### Error Recovery Strategies
- **Network failures:** Retry with exponential backoff, fallback to cached data
- **Insufficient cards:** Generate partial deck with clear reporting
- **Invalid CSV:** Provide specific parsing error messages with line numbers
- **Missing commander:** Suggest similar commanders from collection

## Testing Strategy

### Unit Tests
- **Collection Parser:** Test CSV parsing with various formats and edge cases
- **EDHREC Service:** Mock API responses to test data processing
- **Deck Builder:** Test deck generation logic with known card sets
- **Output Manager:** Verify file naming and formatting

### Integration Tests
- **End-to-end:** Full workflow with sample collection and known commanders
- **API Integration:** Test actual pyedhrec package integration
- **File I/O:** Test CSV reading and deck file writing

### Test Data
- Sample CSV files with various formats and card collections
- Mock EDHREC responses for consistent testing
- Known good deck outputs for regression testing

## Performance Considerations

### Optimization Strategies
- **Caching:** Cache EDHREC API responses to reduce network calls
- **Lazy Loading:** Load collection data incrementally for large CSV files
- **Parallel Processing:** Fetch multiple card recommendations concurrently
- **Memory Management:** Stream large CSV files rather than loading entirely into memory

### Scalability
- Support collections up to 50,000+ cards
- Handle multiple concurrent deck generations
- Efficient card name normalization using pre-computed lookup tables

## Security and Reliability

### Input Validation
- Sanitize all file paths to prevent directory traversal
- Validate CSV structure before processing
- Limit file sizes to prevent resource exhaustion

### Data Integrity
- Verify card names against known Magic card database
- Validate deck legality before output
- Ensure output files are properly formatted and complete