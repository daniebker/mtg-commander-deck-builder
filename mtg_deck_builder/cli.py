"""Command-line interface for MTG Deck Builder."""

import argparse
import sys
import logging
import time
from pathlib import Path
from typing import Optional, Iterator
from contextlib import contextmanager

from .collection_parser import CollectionParser, CollectionParseError, CommanderNotFoundError
from .edhrec_service import EDHRECService, EDHRECAPIError
from .deck_builder import DeckBuilder, DeckBuildingConfig
from .output_manager import OutputManager
from .config import ConfigManager, apply_env_overrides
from .scryfall_service import ScryfallService


def parse_arguments() -> argparse.Namespace:
    """
    Parse command-line arguments for CSV path and commander name.
    
    Returns:
        Parsed arguments namespace
    """
    parser = argparse.ArgumentParser(
        prog='mtg-deck-builder',
        description='Generate MTG Commander deck recommendations from your card collection',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s collection.csv "Atraxa, Praetors' Voice"
  %(prog)s --verbose my_cards.csv "Edgar Markov"
  %(prog)s --output-dir ./decks cards.csv "Meren of Clan Nel Toth"
  %(prog)s --list-commanders collection.csv

For more information, visit: https://github.com/your-repo/mtg-deck-builder
        """
    )
    
    # Required arguments
    parser.add_argument(
        'csv_file',
        type=str,
        help='Path to CSV file containing your card collection'
    )
    
    parser.add_argument(
        'commander',
        type=str,
        nargs='?',
        help='Name of the commander card (required unless using --list-commanders)'
    )
    
    # Optional arguments
    parser.add_argument(
        '--output-dir', '-o',
        type=str,
        default='.',
        help='Directory to save the generated deck file (default: current directory)'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose output with detailed progress information'
    )
    
    parser.add_argument(
        '--quiet', '-q',
        action='store_true',
        help='Suppress all output except errors'
    )
    
    parser.add_argument(
        '--list-commanders',
        action='store_true',
        help='List all available commanders in the collection and exit'
    )
    
    parser.add_argument(
        '--check-legality',
        action='store_true',
        help='Check if the specified commander is legal in Commander format and exit'
    )
    
    parser.add_argument(
        '--no-cache',
        action='store_true',
        help='Disable EDHREC API response caching'
    )
    
    parser.add_argument(
        '--min-deck-size',
        type=int,
        default=60,
        help='Minimum acceptable deck size for partial deck generation (default: 60)'
    )
    
    # Deck composition customization arguments
    parser.add_argument(
        '--creature-count',
        type=int,
        metavar='N',
        help='Override target number of creatures in deck (default: auto-calculated based on strategy)'
    )
    
    parser.add_argument(
        '--instant-count',
        type=int,
        metavar='N',
        help='Override target number of instants in deck (default: auto-calculated)'
    )
    
    parser.add_argument(
        '--sorcery-count',
        type=int,
        metavar='N',
        help='Override target number of sorceries in deck (default: auto-calculated)'
    )
    
    parser.add_argument(
        '--artifact-count',
        type=int,
        metavar='N',
        help='Override target number of artifacts in deck (default: auto-calculated)'
    )
    
    parser.add_argument(
        '--enchantment-count',
        type=int,
        metavar='N',
        help='Override target number of enchantments in deck (default: auto-calculated)'
    )
    
    parser.add_argument(
        '--land-count',
        type=int,
        metavar='N',
        help='Override target number of lands in deck (default: 35-40 based on mana curve)'
    )
    
    parser.add_argument(
        '--strategy',
        choices=['balanced', 'aggro', 'control', 'combo', 'ramp'],
        default='balanced',
        help='Deck building strategy that affects card type ratios (default: balanced)'
    )
    
    parser.add_argument(
        '--version',
        action='version',
        version='%(prog)s 1.0.0'
    )
    
    args = parser.parse_args()
    
    # Validate arguments
    if not args.list_commanders and not args.check_legality and not args.commander:
        parser.error("Commander name is required unless using --list-commanders")
    
    if args.check_legality and not args.commander:
        parser.error("Commander name is required when using --check-legality")
    
    if args.verbose and args.quiet:
        parser.error("--verbose and --quiet cannot be used together")
    
    # Validate card count arguments
    card_count_args = [
        ('creature_count', args.creature_count),
        ('instant_count', args.instant_count),
        ('sorcery_count', args.sorcery_count),
        ('artifact_count', args.artifact_count),
        ('enchantment_count', args.enchantment_count),
        ('land_count', args.land_count)
    ]
    
    for arg_name, value in card_count_args:
        if value is not None:
            if value < 0:
                parser.error(f"--{arg_name.replace('_', '-')} must be non-negative")
            if value > 99:
                parser.error(f"--{arg_name.replace('_', '-')} cannot exceed 99 (deck size limit)")
    
    # Check if total specified counts don't exceed deck size
    specified_counts = [count for _, count in card_count_args if count is not None]
    if specified_counts and sum(specified_counts) > 99:
        parser.error("Total of all specified card counts cannot exceed 99")
    
    return args


def create_deck_building_config(args: argparse.Namespace) -> DeckBuildingConfig:
    """
    Create a DeckBuildingConfig from command line arguments.
    
    Args:
        args: Parsed command line arguments
        
    Returns:
        DeckBuildingConfig with user customizations
    """
    config = DeckBuildingConfig()
    
    # Apply strategy
    config.strategy = args.strategy
    
    # Apply card count overrides
    if args.creature_count is not None:
        config.creature_count = args.creature_count
    if args.instant_count is not None:
        config.instant_count = args.instant_count
    if args.sorcery_count is not None:
        config.sorcery_count = args.sorcery_count
    if args.artifact_count is not None:
        config.artifact_count = args.artifact_count
    if args.enchantment_count is not None:
        config.enchantment_count = args.enchantment_count
    if args.land_count is not None:
        config.land_count = args.land_count
    
    return config


def validate_inputs(csv_file: str, commander: Optional[str] = None) -> None:
    """
    Validate input file paths and commander names.
    
    Args:
        csv_file: Path to the CSV file
        commander: Optional commander name to validate
        
    Raises:
        FileNotFoundError: If CSV file doesn't exist
        ValueError: If inputs are invalid
    """
    # Validate CSV file path
    csv_path = Path(csv_file)
    
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_file}")
    
    if not csv_path.is_file():
        raise ValueError(f"Path is not a file: {csv_file}")
    
    if csv_path.stat().st_size == 0:
        raise ValueError(f"CSV file is empty: {csv_file}")
    
    # Check file extension (warn if not .csv)
    if csv_path.suffix.lower() not in ['.csv', '.txt']:
        logging.warning(f"File extension '{csv_path.suffix}' is not .csv - will attempt to parse anyway")
    
    # Validate commander name if provided
    if commander:
        if not commander.strip():
            raise ValueError("Commander name cannot be empty")
        
        if len(commander.strip()) < 2:
            raise ValueError("Commander name is too short")
        
        # Check for obviously invalid characters
        invalid_chars = ['<', '>', '|', '*', '?', '"']
        if any(char in commander for char in invalid_chars):
            raise ValueError(f"Commander name contains invalid characters: {commander}")


class ProgressIndicator:
    """Simple progress indicator for long-running operations."""
    
    def __init__(self, message: str, verbose: bool = False, quiet: bool = False):
        self.message = message
        self.verbose = verbose
        self.quiet = quiet
        self.start_time = None
        self.spinner_chars = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
        self.spinner_index = 0
    
    def __enter__(self):
        if not self.quiet:
            if self.verbose:
                print(f"[{time.strftime('%H:%M:%S')}] Starting: {self.message}")
            else:
                print(f"⏳ {self.message}...", end='', flush=True)
        
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time:
            duration = time.time() - self.start_time
            
            if not self.quiet:
                if exc_type is None:
                    if self.verbose:
                        print(f"[{time.strftime('%H:%M:%S')}] Completed: {self.message} ({duration:.1f}s)")
                    else:
                        print(f" ✓ ({duration:.1f}s)")
                else:
                    if self.verbose:
                        print(f"[{time.strftime('%H:%M:%S')}] Failed: {self.message} ({duration:.1f}s)")
                    else:
                        print(f" ✗ ({duration:.1f}s)")
    
    def update(self, status: str):
        """Update progress status."""
        if not self.quiet and self.verbose:
            print(f"[{time.strftime('%H:%M:%S')}] {self.message}: {status}")


def setup_logging(verbose: bool = False, quiet: bool = False) -> None:
    """
    Set up comprehensive logging system for debugging and user information.
    
    Args:
        verbose: Enable verbose logging with detailed operation reporting
        quiet: Enable quiet mode (errors only)
    """
    # Configure root logger
    if quiet:
        level = logging.ERROR
        format_str = '%(levelname)s: %(message)s'
    elif verbose:
        level = logging.DEBUG
        format_str = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    else:
        level = logging.INFO
        format_str = '%(levelname)s: %(message)s'
    
    # Create custom formatter that handles multiline messages nicely
    class MultilineFormatter(logging.Formatter):
        def format(self, record):
            formatted = super().format(record)
            if '\n' in formatted:
                lines = formatted.split('\n')
                return '\n'.join([lines[0]] + ['  ' + line for line in lines[1:]])
            return formatted
    
    # Set up logging configuration
    logging.basicConfig(
        level=level,
        format=format_str,
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=[logging.StreamHandler(sys.stderr)]
    )
    
    # Apply custom formatter
    for handler in logging.root.handlers:
        handler.setFormatter(MultilineFormatter(format_str, datefmt='%Y-%m-%d %H:%M:%S'))
    
    # Configure specific loggers
    app_logger = logging.getLogger('mtg_deck_builder')
    app_logger.setLevel(level)
    
    # Reduce noise from external libraries in non-verbose mode
    if not verbose:
        logging.getLogger('urllib3').setLevel(logging.WARNING)
        logging.getLogger('requests').setLevel(logging.WARNING)
        logging.getLogger('pyedhrec').setLevel(logging.WARNING)
    
    # Add file logging in verbose mode
    if verbose:
        try:
            log_dir = Path.home() / '.mtg_deck_builder' / 'logs'
            log_dir.mkdir(parents=True, exist_ok=True)
            
            log_file = log_dir / f"mtg_deck_builder_{time.strftime('%Y%m%d_%H%M%S')}.log"
            
            file_handler = logging.FileHandler(log_file)
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(MultilineFormatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            ))
            
            logging.root.addHandler(file_handler)
            logging.info(f"Detailed logs will be saved to: {log_file}")
            
        except Exception as e:
            logging.warning(f"Could not set up file logging: {e}")


@contextmanager
def progress_context(message: str, verbose: bool = False, quiet: bool = False):
    """
    Context manager for showing progress indicators during operations.
    
    Args:
        message: Description of the operation
        verbose: Whether to show detailed progress
        quiet: Whether to suppress output
    """
    indicator = ProgressIndicator(message, verbose, quiet)
    try:
        with indicator:
            yield indicator
    except Exception:
        raise


def log_deck_building_progress(step: str, details: str = "", verbose: bool = False):
    """
    Log progress during deck building with appropriate detail level.
    
    Args:
        step: Current step name
        details: Additional details about the step
        verbose: Whether to show verbose details
    """
    logger = logging.getLogger('mtg_deck_builder.progress')
    
    if verbose and details:
        logger.info(f"{step}: {details}")
    else:
        logger.info(step)


def create_debug_report(
    collection_size: int,
    commander: str,
    recommendations_count: int,
    deck_size: int,
    generation_time: float,
    errors: list = None
) -> str:
    """
    Create a detailed debug report for troubleshooting.
    
    Args:
        collection_size: Number of cards in collection
        commander: Commander name
        recommendations_count: Number of EDHREC recommendations
        deck_size: Final deck size
        generation_time: Time taken to generate deck
        errors: List of errors encountered
        
    Returns:
        Formatted debug report
    """
    report_lines = [
        "=== MTG Deck Builder Debug Report ===",
        f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"Commander: {commander}",
        f"Collection Size: {collection_size} cards",
        f"EDHREC Recommendations: {recommendations_count}",
        f"Final Deck Size: {deck_size} cards",
        f"Generation Time: {generation_time:.2f} seconds",
        ""
    ]
    
    if errors:
        report_lines.extend([
            "Errors Encountered:",
            *[f"  - {error}" for error in errors],
            ""
        ])
    
    # Add system information
    import platform
    report_lines.extend([
        "System Information:",
        f"  Platform: {platform.system()} {platform.release()}",
        f"  Python: {platform.python_version()}",
        ""
    ])
    
    return "\n".join(report_lines)


def check_commander_legality(commander: str) -> None:
    """
    Check if a commander is legal in Commander format using Scryfall API.
    
    Args:
        commander: Name of the commander to check
    """
    try:
        print(f"Checking Commander legality for: {commander}")
        print("-" * 50)
        
        # Initialize Scryfall service
        scryfall_service = ScryfallService()
        
        # Check if it can be a commander
        print("⏳ Checking if card can be a commander...")
        is_commander = scryfall_service.is_legal_commander(commander)
        
        # Check if it's legal in Commander format
        print("⏳ Checking Commander format legality...")
        is_format_legal = scryfall_service.is_legal_in_commander(commander)
        
        # Get additional card information
        print("⏳ Fetching card details...")
        card_data = scryfall_service.get_card_data(commander)
        
        print("\n📋 Results:")
        print(f"  Card Name: {card_data.name if card_data else commander}")
        
        if card_data:
            print(f"  Type Line: {card_data.type_line}")
            print(f"  Mana Cost: {card_data.mana_cost or 'N/A'}")
            print(f"  Color Identity: {', '.join(card_data.color_identity) if card_data.color_identity else 'Colorless'}")
        
        print(f"\n🎯 Commander Eligibility:")
        if is_commander:
            print("  ✅ Can be your commander")
            if card_data and 'legendary' in card_data.type_line.lower() and 'creature' in card_data.type_line.lower():
                print("     (Legendary Creature)")
            elif card_data and 'planeswalker' in card_data.type_line.lower():
                print("     (Planeswalker with commander ability)")
            elif card_data and 'partner' in card_data.oracle_text.lower():
                print("     (Has Partner ability)")
            else:
                print("     (Has special commander ability)")
        else:
            print("  ❌ Cannot be your commander")
            if card_data:
                if 'legendary' not in card_data.type_line.lower():
                    print("     (Not legendary)")
                elif 'creature' not in card_data.type_line.lower() and 'planeswalker' not in card_data.type_line.lower():
                    print("     (Not a creature or planeswalker)")
                elif 'can be your commander' not in card_data.oracle_text.lower() and 'partner' not in card_data.oracle_text.lower():
                    print("     (No commander ability)")
        
        print(f"\n⚖️ Format Legality:")
        if is_format_legal:
            print("  ✅ Legal in Commander format")
        else:
            print("  ❌ Not legal in Commander format")
            if card_data and card_data.legalities:
                commander_status = card_data.legalities.get('commander', 'unknown')
                if commander_status == 'banned':
                    print("     (Banned in Commander)")
                elif commander_status == 'restricted':
                    print("     (Restricted in Commander)")
                else:
                    print(f"     (Status: {commander_status})")
        
        # Overall verdict
        print(f"\n🏆 Overall Verdict:")
        if is_commander and is_format_legal:
            print("  ✅ This card is a legal commander!")
            print("     You can use it to build a Commander deck.")
        elif is_commander and not is_format_legal:
            print("  ⚠️  This card can be a commander but is not legal in the format.")
            print("     It may be banned or restricted in Commander.")
        elif not is_commander and is_format_legal:
            print("  ⚠️  This card is legal in Commander but cannot be your commander.")
            print("     You can include it in the 99 cards of your deck.")
        else:
            print("  ❌ This card cannot be used as a commander.")
            print("     It's either not eligible or not legal in the format.")
        
        # Show additional format legalities if available
        if card_data and card_data.legalities:
            other_formats = {k: v for k, v in card_data.legalities.items() 
                           if k != 'commander' and v == 'legal'}
            if other_formats:
                print(f"\n📜 Also legal in: {', '.join(other_formats.keys()).title()}")
        
    except Exception as e:
        logging.error(f"Failed to check commander legality: {e}")
        print(f"\n❌ Error checking legality: {e}")
        print("This might be due to:")
        print("  • Card name not found on Scryfall")
        print("  • Network connectivity issues")
        print("  • API rate limiting")
        sys.exit(1)


def list_available_commanders(csv_file: str) -> None:
    """
    List all available commanders in the collection.
    
    Args:
        csv_file: Path to the CSV collection file
    """
    try:
        print("Loading collection and identifying commanders...")
        
        # Parse collection
        parser = CollectionParser()
        collection = parser.load_collection(csv_file)
        
        # Get available commanders
        commanders = parser.list_available_commanders(collection)
        
        if not commanders:
            print("No potential commanders found in your collection.")
            print("Make sure your collection includes legendary creatures or planeswalkers that can be commanders.")
            return
        
        print(f"\nFound {len(commanders)} potential commanders in your collection:")
        print("-" * 50)
        
        for i, commander in enumerate(commanders, 1):
            print(f"{i:3d}. {commander}")
        
        print(f"\nTo build a deck, run:")
        print(f'mtg-deck-builder "{csv_file}" "<commander_name>"')
        
    except CollectionParseError as e:
        logging.error(f"Failed to parse collection: {e}")
        sys.exit(1)
    except Exception as e:
        logging.error(f"Unexpected error listing commanders: {e}")
        sys.exit(1)


def build_commander_deck(
    csv_file: str, 
    commander: str, 
    output_dir: str,
    min_deck_size: int = 60,
    use_cache: bool = True,
    verbose: bool = False,
    quiet: bool = False,
    config = None
) -> None:
    """
    Build a Commander deck using the specified parameters.
    
    Args:
        csv_file: Path to CSV collection file
        commander: Name of the commander
        output_dir: Directory to save deck file
        min_deck_size: Minimum acceptable deck size
        use_cache: Whether to use EDHREC API caching
        verbose: Whether to show detailed progress
        quiet: Whether to suppress non-essential output
        config: Optional DeckBuildingConfig with customization options
    """
    start_time = time.time()
    errors_encountered = []
    
    try:
        # Initialize components
        log_deck_building_progress("Initializing components", verbose=verbose)
        
        parser = CollectionParser()
        edhrec_service = EDHRECService(cache_dir=None if not use_cache else None)
        scryfall_service = ScryfallService()
        
        # Use provided config or create default
        if config is None:
            from .deck_builder import DeckBuildingConfig
            config = DeckBuildingConfig()
        
        deck_builder = DeckBuilder(config=config, scryfall_service=scryfall_service)
        output_manager = OutputManager(output_dir, scryfall_service=scryfall_service)
        
        # Step 1: Load and parse collection
        with progress_context("Loading card collection", verbose, quiet) as progress:
            collection = parser.load_collection(csv_file)
            progress.update(f"Loaded {len(collection)} unique cards")
        
        log_deck_building_progress(
            "Collection loaded", 
            f"{len(collection)} unique cards from {csv_file}",
            verbose
        )
        
        # Step 2: Validate commander
        with progress_context("Validating commander", verbose, quiet) as progress:
            try:
                parser.validate_commander(commander, collection)
                progress.update("Commander validated successfully")
            except CommanderNotFoundError as e:
                errors_encountered.append(str(e))
                
                if not quiet:
                    print(f"\n❌ {e}")
                    print("\nSearching for similar commanders in your collection...")
                
                commanders = parser.list_available_commanders(collection)
                if commanders:
                    if not quiet:
                        print("Available commanders:")
                        for cmd in commanders[:10]:  # Show top 10
                            print(f"  • {cmd}")
                else:
                    if not quiet:
                        print("No potential commanders found in your collection.")
                
                raise e
        
        log_deck_building_progress(
            "Commander validated", 
            f"'{commander}' found in collection",
            verbose
        )
        
        # Step 3: Fetch EDHREC recommendations
        with progress_context("Fetching EDHREC recommendations", verbose, quiet) as progress:
            try:
                recommendations = edhrec_service.get_commander_recommendations_with_fallback(commander)
                progress.update(f"Retrieved {len(recommendations)} recommendations")
                
                log_deck_building_progress(
                    "EDHREC data retrieved",
                    f"{len(recommendations)} card recommendations",
                    verbose
                )
            except Exception as e:
                errors_encountered.append(f"EDHREC API issue: {e}")
                logging.warning(f"EDHREC API issue: {e}")
                
                progress.update("Using fallback recommendations")
                recommendations = edhrec_service.get_fallback_recommendations(commander)
                
                log_deck_building_progress(
                    "Using fallback recommendations",
                    f"{len(recommendations)} generic recommendations",
                    verbose
                )
        
        # Step 4: Build deck
        with progress_context("Building optimized deck", verbose, quiet) as progress:
            try:
                deck = deck_builder.build_deck(commander, collection, recommendations)
                
                if deck.total_cards < min_deck_size:
                    progress.update(f"Deck has {deck.total_cards} cards, generating partial deck")
                    
                    if not quiet:
                        print(f"\n⚠ Warning: Generated deck has only {deck.total_cards} cards (minimum: {min_deck_size})")
                    
                    deck, report = deck_builder.handle_insufficient_cards(
                        commander, collection, recommendations, min_deck_size
                    )
                    
                    log_deck_building_progress(
                        "Partial deck generated",
                        f"{deck.total_cards} cards with available collection",
                        verbose
                    )
                    
                    if verbose and report and not quiet:
                        print("\nGeneration Report:")
                        for key, value in report.items():
                            if isinstance(value, list) and value:
                                print(f"  {key}: {', '.join(map(str, value))}")
                            elif not isinstance(value, (list, dict)):
                                print(f"  {key}: {value}")
                else:
                    progress.update(f"Generated complete {deck.total_cards}-card deck")
                    log_deck_building_progress(
                        "Deck generation completed",
                        f"{deck.total_cards} cards selected",
                        verbose
                    )
            
            except ValueError as e:
                errors_encountered.append(f"Deck building failed: {e}")
                raise e
        
        # Step 5: Generate statistics
        with progress_context("Analyzing deck composition", verbose, quiet) as progress:
            statistics = output_manager.generate_deck_statistics(deck, recommendations)
            progress.update("Statistics generated")
            
            log_deck_building_progress(
                "Deck analysis completed",
                f"Average CMC: {statistics.average_cmc:.2f}, Synergy: {statistics.synergy_score:.2f}",
                verbose
            )
        
        # Step 6: Generate purchase suggestions
        purchase_suggestions = []
        try:
            if recommendations:
                # Get normalized card names from collection
                collection_card_names = set(card_entry.normalized_name for card_entry in collection.values())
                
                # Generate purchase suggestions
                purchase_suggestions = scryfall_service.get_purchase_suggestions(
                    recommendations, collection_card_names, max_suggestions=10
                )
                
                if verbose and purchase_suggestions:
                    print(f"Generated {len(purchase_suggestions)} purchase suggestions")
        except Exception as e:
            if verbose:
                print(f"Warning: Could not generate purchase suggestions: {e}")
        
        # Step 7: Write output file
        with progress_context("Saving deck file", verbose, quiet) as progress:
            output_path = output_manager.write_deck_file(deck, statistics=statistics, purchase_suggestions=purchase_suggestions)
            progress.update(f"Saved to {output_path}")
            
            log_deck_building_progress(
                "Deck file written",
                f"Output saved to {output_path}",
                verbose
            )
        
        # Show summary
        generation_time = time.time() - start_time
        
        if not quiet:
            print(f"\n🎉 Deck building completed successfully! ({generation_time:.1f}s)")
            print(f"📁 Deck saved to: {output_path}")
            
            print(f"\n📊 Deck Summary:")
            print(f"  🎯 Commander: {deck.commander}")
            print(f"  📋 Total Cards: {deck.total_cards}")
            print(f"  ⚡ Average CMC: {statistics.average_cmc:.2f}")
            print(f"  👹 Creatures: {statistics.card_types.get('creature', 0)} ({statistics.creature_percentage:.1f}%)")
            print(f"  🏞️  Lands: {statistics.card_types.get('land', 0)} ({statistics.land_percentage:.1f}%)")
            
            if statistics.synergy_score > 0:
                synergy_emoji = "🔥" if statistics.synergy_score >= 0.8 else "👍" if statistics.synergy_score >= 0.6 else "👌"
                print(f"  {synergy_emoji} Synergy Score: {statistics.synergy_score:.2f}/1.0")
            
            # Validation status
            if deck.is_valid():
                print("  ✅ Status: Passes all Commander format rules")
            else:
                print("  ⚠️  Status: Has validation issues")
                if verbose:
                    for error in deck.get_validation_errors():
                        print(f"    • {error}")
        
        # Create debug report in verbose mode
        if verbose:
            debug_report = create_debug_report(
                collection_size=len(collection),
                commander=commander,
                recommendations_count=len(recommendations),
                deck_size=deck.total_cards,
                generation_time=generation_time,
                errors=errors_encountered if errors_encountered else None
            )
            
            logging.debug("Debug Report:\n" + debug_report)
        
    except (CollectionParseError, CommanderNotFoundError, ValueError) as e:
        errors_encountered.append(str(e))
        raise e
    except EDHRECAPIError as e:
        errors_encountered.append(f"EDHREC API error: {e}")
        logging.error(f"EDHREC API error: {e}")
        raise e
    except OSError as e:
        errors_encountered.append(f"File system error: {e}")
        logging.error(f"File system error: {e}")
        raise e
    except Exception as e:
        errors_encountered.append(f"Unexpected error: {e}")
        logging.error(f"Unexpected error during deck building: {e}")
        
        if verbose:
            import traceback
            logging.debug("Full traceback:\n" + traceback.format_exc())
        
        raise e


def show_progress_feedback(message: str, verbose: bool = False) -> None:
    """
    Show progress feedback for long-running operations.
    
    Args:
        message: Progress message to display
        verbose: Whether to show detailed progress
    """
    if verbose:
        timestamp = logging.Formatter().formatTime(logging.LogRecord(
            '', 0, '', 0, '', (), None
        ))
        print(f"[{timestamp}] {message}")
    else:
        print(f"⏳ {message}")


def handle_user_friendly_errors(error: Exception, verbose: bool = False) -> str:
    """
    Convert technical errors into user-friendly error messages.
    
    Args:
        error: Exception to convert
        verbose: Whether to include technical details
        
    Returns:
        User-friendly error message
    """
    if isinstance(error, FileNotFoundError):
        return f"File not found: {error}"
    
    elif isinstance(error, CollectionParseError):
        return f"Could not parse your collection file: {error}"
    
    elif isinstance(error, CommanderNotFoundError):
        return f"Commander issue: {error}"
    
    elif isinstance(error, EDHRECAPIError):
        return f"EDHREC service error: {error}. The deck builder will use fallback recommendations."
    
    elif isinstance(error, ValueError):
        return f"Invalid input: {error}"
    
    elif isinstance(error, OSError):
        return f"File system error: {error}"
    
    else:
        if verbose:
            return f"Unexpected error: {error}"
        else:
            return f"An unexpected error occurred. Use --verbose for more details."


def main():
    """Main entry point for the MTG Deck Builder CLI."""
    args = None
    
    try:
        # Parse command-line arguments
        args = parse_arguments()
        
        # Load configuration
        config_manager = ConfigManager()
        config = config_manager.get_config()
        config = apply_env_overrides(config)
        
        # Set up logging
        setup_logging(args.verbose, args.quiet)
        
        # Validate inputs
        validate_inputs(args.csv_file, args.commander)
        
        if not args.quiet:
            print("MTG Commander Deck Builder v1.0.0")
            print("=" * 40)
        
        # Handle list commanders mode
        if args.list_commanders:
            list_available_commanders(args.csv_file)
            return
        
        # Handle check legality mode
        if args.check_legality:
            check_commander_legality(args.commander)
            return
        
        # Create deck building configuration from command line arguments
        deck_config = create_deck_building_config(args)
        
        # Build commander deck
        build_commander_deck(
            csv_file=args.csv_file,
            commander=args.commander,
            output_dir=args.output_dir or config.default_output_dir,
            min_deck_size=args.min_deck_size or config.min_deck_size,
            use_cache=(not args.no_cache) and config.edhrec_cache_enabled,
            verbose=args.verbose or config.verbose_output,
            quiet=args.quiet,
            config=deck_config
        )
        
    except KeyboardInterrupt:
        if not (args and args.quiet):
            print("\n⚠ Operation cancelled by user")
        sys.exit(1)
    
    except (FileNotFoundError, ValueError, CollectionParseError, CommanderNotFoundError) as e:
        # User-facing errors - show friendly message
        if args and args.verbose:
            logging.error(f"Error: {e}")
        else:
            print(f"Error: {handle_user_friendly_errors(e, args.verbose if args else False)}")
        sys.exit(1)
    
    except Exception as e:
        # Unexpected errors - show appropriate level of detail
        error_msg = handle_user_friendly_errors(e, args.verbose if args else False)
        
        if args and args.verbose:
            logging.error(f"Unexpected error: {e}")
            import traceback
            traceback.print_exc()
        else:
            print(f"Error: {error_msg}")
        
        sys.exit(1)


if __name__ == "__main__":
    main()