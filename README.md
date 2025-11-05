# MTG Commander Deck Builder

A command-line tool that generates optimized MTG Commander deck recommendations based on your card collection and a specified commander. The tool leverages the EDHREC database to fetch card synergy data and builds legal, playable decks using only cards available in your collection.

## Features

- 🎯 **Commander-focused**: Build decks around any legendary creature or planeswalker
- 📊 **EDHREC Integration**: Uses real synergy data from EDHREC for optimal card selection
- 📋 **Collection-based**: Only uses cards you actually own
- ⚖️ **Format Legal**: Ensures all Commander format rules are followed using Scryfall API
- 🔍 **Legality Checking**: Verify commander eligibility and format legality in real-time
- 📈 **Smart Algorithm**: Balances mana curve, card types, and synergy scores
- 🔧 **Configurable**: Customizable preferences for deck building
- 📁 **Multiple Formats**: Supports various CSV collection formats

## Installation

### From PyPI (Recommended)

```bash
pip install mtg-commander-deck-builder
```

### From Source

```bash
git clone https://github.com/your-repo/mtg-commander-deck-builder.git
cd mtg-commander-deck-builder
pip install -e .
```

### Development Installation

```bash
git clone https://github.com/your-repo/mtg-commander-deck-builder.git
cd mtg-commander-deck-builder
pip install -e ".[dev]"
```

## Quick Start

1. **Prepare your collection CSV** (see [CSV Format](#csv-format) below)
2. **Choose a commander** from your collection
3. **Generate your deck**:

```bash
mtg-deck-builder my_collection.csv "Atraxa, Praetors' Voice"
```

That's it! Your optimized Commander deck will be saved as a text file.

## Usage

### Basic Usage

```bash
mtg-deck-builder <csv_file> <commander_name>
```

### Examples

```bash
# Basic deck building
mtg-deck-builder collection.csv "Edgar Markov"

# With custom output directory
mtg-deck-builder --output-dir ./decks collection.csv "Meren of Clan Nel Toth"

# Verbose output for debugging
mtg-deck-builder --verbose collection.csv "Atraxa, Praetors' Voice"

# List available commanders in your collection
mtg-deck-builder --list-commanders collection.csv

# Check if a card is a legal commander
mtg-deck-builder --check-legality "Atraxa, Praetors' Voice"

# Quiet mode (errors only)
mtg-deck-builder --quiet collection.csv "Kaalia of the Vast"

# Disable EDHREC caching
mtg-deck-builder --no-cache collection.csv "Prossh, Skyraider of Kher"
```

### Command-Line Options

| Option | Description |
|--------|-------------|
| `csv_file` | Path to your card collection CSV file |
| `commander` | Name of the commander card (in quotes if it contains spaces) |
| `--output-dir, -o` | Directory to save the generated deck file (default: current directory) |
| `--verbose, -v` | Enable detailed progress information and debug output |
| `--quiet, -q` | Suppress all output except errors |
| `--list-commanders` | List all potential commanders in your collection and exit |
| `--check-legality` | Check if the specified commander is legal in Commander format and exit |
| `--no-cache` | Disable EDHREC API response caching |
| `--min-deck-size` | Minimum acceptable deck size for partial generation (default: 60) |
| `--version` | Show version information |
| `--help, -h` | Show help message |

## CSV Format

Your collection CSV file should contain your Magic cards with the following supported columns:

### Required Columns
- **Name** or **Card Name**: The name of the card
- **Quantity** or **Count**: How many copies you own

### Optional Columns
- **Set** or **Set Code**: The set the card is from
- **Collector Number**: Card's collector number
- **Condition**: Card condition (NM, LP, etc.)
- **Foil**: Whether the card is foil (True/False)

### Supported CSV Formats

The tool automatically detects and handles various CSV formats:

#### Format 1: Basic Collection
```csv
Name,Quantity
"Atraxa, Praetors' Voice",1
"Sol Ring",1
"Command Tower",1
"Swamp",10
```

#### Format 2: Detailed Collection
```csv
Card Name,Count,Set,Condition
"Edgar Markov",1,"C17","NM"
"Anguished Unmaking",1,"SOI","LP"
"Godless Shrine",1,"GTC","NM"
```

#### Format 3: MTGO Export Format
```csv
Card Name,Quantity,Set Code,Collector Number,Premium
"Kaalia of the Vast",1,"CMD","042","No"
"Lightning Greaves",1,"CMD","199","No"
```

### Sample CSV Files

Example CSV files are included in the `examples/` directory:

- `examples/sample_collection_basic.csv` - Basic format example
- `examples/sample_collection_detailed.csv` - Detailed format with set info
- `examples/sample_collection_large.csv` - Larger collection example

## Configuration

The tool supports configuration files for customizing default behavior.

### Configuration File Location

- **Linux/macOS**: `~/.mtg_deck_builder/config.json`
- **Windows**: `%USERPROFILE%\.mtg_deck_builder\config.json`

### Configuration Options

```json
{
  "min_lands": 35,
  "max_lands": 40,
  "preferred_creature_count": 25,
  "preferred_noncreature_spells": 35,
  "synergy_weight": 0.7,
  "availability_weight": 0.3,
  "edhrec_cache_enabled": true,
  "edhrec_cache_duration_hours": 24,
  "default_output_dir": ".",
  "include_statistics": true,
  "min_deck_size": 60,
  "enforce_singleton": true,
  "enforce_color_identity": true
}
```

### Environment Variables

You can also override settings using environment variables:

```bash
export MTG_DECK_BUILDER_MIN_LANDS=38
export MTG_DECK_BUILDER_SYNERGY_WEIGHT=0.8
export MTG_DECK_BUILDER_VERBOSE=true
mtg-deck-builder collection.csv "Atraxa, Praetors' Voice"
```

## Output

The tool generates a text file containing your optimized deck list with the following sections:

### Deck File Format

```
Commander: Atraxa, Praetors' Voice

=== CREATURES (25) ===
1x Acidic Slime
1x Avenger of Zendikar
...

=== INSTANTS (8) ===
1x Counterspell
1x Swords to Plowshares
...

=== SORCERIES (12) ===
1x Cultivate
1x Kodama's Reach
...

=== ARTIFACTS (10) ===
1x Sol Ring
1x Arcane Signet
...

=== ENCHANTMENTS (6) ===
1x Rhystic Study
1x Smothering Tithe
...

=== PLANESWALKERS (2) ===
1x Jace, the Mind Sculptor
...

=== LANDS (36) ===
1x Command Tower
1x Exotic Orchard
4x Forest
3x Island
4x Plains
3x Swamp
...

=== DECK STATISTICS ===
Total Cards: 100
Average CMC: 3.2
Creatures: 25 (25.0%)
Lands: 36 (36.0%)
Synergy Score: 0.78/1.0

Mana Curve:
0 CMC: ████ 4 cards
1 CMC: ██████ 6 cards
2 CMC: ████████ 8 cards
3 CMC: ████████████ 12 cards
4 CMC: ██████████ 10 cards
5 CMC: ████████ 8 cards
6+ CMC: ██████ 6 cards

Color Distribution:
White: ████████ 18 cards
Blue: ██████ 15 cards
Black: ██████ 14 cards
Green: ████████ 19 cards
Colorless: ████████████ 34 cards
```

## Troubleshooting

### Common Issues

#### "Commander not found in collection"
- Ensure the commander name is spelled exactly as it appears in your CSV
- Use quotes around commander names with spaces or special characters
- Use `--list-commanders` to see available commanders in your collection

#### "Could not parse CSV file"
- Check that your CSV file has proper headers (Name/Card Name and Quantity/Count)
- Ensure the file is saved in UTF-8 encoding
- Verify there are no empty rows or malformed entries

#### "EDHREC API error"
- Check your internet connection
- The tool will automatically use fallback recommendations if EDHREC is unavailable
- Use `--no-cache` if you suspect cached data is causing issues

#### "Insufficient cards for complete deck"
- This is normal for smaller collections
- The tool will generate the best possible deck with available cards
- Consider trading or purchasing additional cards to complete the deck

### Debug Mode

Use `--verbose` for detailed information about the deck building process:

```bash
mtg-deck-builder --verbose collection.csv "Atraxa, Praetors' Voice"
```

This will show:
- Collection parsing details
- EDHREC API calls and responses
- Card selection reasoning
- Deck validation results
- Performance timing information

### Log Files

In verbose mode, detailed logs are saved to:
- **Linux/macOS**: `~/.mtg_deck_builder/logs/`
- **Windows**: `%USERPROFILE%\.mtg_deck_builder\logs\`

## Commander Legality Checking

The tool includes comprehensive Commander legality checking using the Scryfall API to ensure your commanders are legal and your deck follows format rules.

### Check Commander Legality

Verify if a card can be used as a commander:

```bash
mtg-deck-builder --check-legality "Atraxa, Praetors' Voice"
```

This will show:
- ✅/❌ Whether the card can be your commander
- ✅/❌ Whether the card is legal in Commander format
- 📋 Card details (type, mana cost, color identity)
- 🏆 Overall verdict and explanation

### Example Output

```
Checking Commander legality for: Atraxa, Praetors' Voice
--------------------------------------------------

📋 Results:
  Card Name: Atraxa, Praetors' Voice
  Type Line: Legendary Creature — Phyrexian Angel Horror
  Mana Cost: {G}{W}{U}{B}
  Color Identity: W, U, B, G

🎯 Commander Eligibility:
  ✅ Can be your commander
     (Legendary Creature)

⚖️ Format Legality:
  ✅ Legal in Commander format

🏆 Overall Verdict:
  ✅ This card is a legal commander!
     You can use it to build a Commander deck.
```

### Automatic Legality Filtering

When building decks, the tool automatically:

1. **Validates the commander** using Scryfall API data
2. **Filters collection cards** to only include Commander-legal cards
3. **Checks color identity** to ensure deck compliance
4. **Enforces format rules** like singleton restrictions

### Supported Commander Types

The legality checker recognizes:

- **Legendary Creatures** - Traditional commanders
- **Planeswalkers** - With "can be your commander" text
- **Partner Commanders** - Cards with Partner abilities
- **Background Commanders** - From Commander Legends: Battle for Baldur's Gate
- **Special Cases** - Cards with unique commander abilities

### API Integration

The tool uses the [Scryfall API](https://scryfall.com/docs/api) for:

- Real-time legality checking
- Accurate card data and rulings
- Format-specific ban list updates
- Color identity verification

All API responses are cached locally to improve performance and reduce API calls.

## Advanced Usage

### Batch Processing

Generate multiple decks from a script:

```bash
#!/bin/bash
commanders=("Atraxa, Praetors' Voice" "Edgar Markov" "Meren of Clan Nel Toth")
for commander in "${commanders[@]}"; do
    mtg-deck-builder collection.csv "$commander"
done
```

### Integration with Other Tools

The tool can be integrated with collection management software:

```python
import subprocess
import json

def build_deck(collection_file, commander):
    result = subprocess.run([
        'mtg-deck-builder', 
        collection_file, 
        commander
    ], capture_output=True, text=True)
    
    if result.returncode == 0:
        print(f"Deck built successfully for {commander}")
    else:
        print(f"Error: {result.stderr}")

# Build decks for multiple commanders
commanders = ["Atraxa, Praetors' Voice", "Edgar Markov"]
for commander in commanders:
    build_deck("my_collection.csv", commander)
```

## Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

### Development Setup

```bash
git clone https://github.com/your-repo/mtg-commander-deck-builder.git
cd mtg-commander-deck-builder
pip install -e ".[dev]"
```

### Running Tests

```bash
pytest
```

### Code Style

We use Black for code formatting:

```bash
black mtg_deck_builder/
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- [EDHREC](https://edhrec.com/) for providing card synergy data
- [pyedhrec](https://github.com/your-repo/pyedhrec) for the Python EDHREC API wrapper
- The Magic: The Gathering community for inspiration and feedback

## Support

- 🐛 **Bug Reports**: [GitHub Issues](https://github.com/your-repo/mtg-commander-deck-builder/issues)
- 💡 **Feature Requests**: [GitHub Discussions](https://github.com/your-repo/mtg-commander-deck-builder/discussions)
- 📧 **Email**: support@mtg-deck-builder.com

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for version history and changes.