#!/usr/bin/env python3
"""
Demonstration of the new Commander legality checking functionality.
This script shows how the feature works with various types of cards.
"""

import time
from mtg_deck_builder.scryfall_service import ScryfallService

def print_separator(title=""):
    """Print a nice separator with optional title."""
    if title:
        print(f"\n{'='*20} {title} {'='*20}")
    else:
        print("="*60)

def check_card_legality(scryfall, card_name, description=""):
    """Check and display legality for a single card."""
    print(f"\n🔍 Checking: {card_name}")
    if description:
        print(f"   ({description})")
    print("-" * 50)
    
    try:
        # Get basic legality info
        can_be_commander = scryfall.is_legal_commander(card_name)
        is_format_legal = scryfall.is_legal_in_commander(card_name)
        
        # Get detailed card data
        card_data = scryfall.get_card_data(card_name)
        
        if card_data:
            print(f"📋 Type: {card_data.type_line}")
            print(f"💰 Mana Cost: {card_data.mana_cost or 'N/A'}")
            colors = ', '.join(card_data.color_identity) if card_data.color_identity else 'Colorless'
            print(f"🎨 Color Identity: {colors}")
        
        # Show results
        commander_status = "✅ Yes" if can_be_commander else "❌ No"
        format_status = "✅ Yes" if is_format_legal else "❌ No"
        
        print(f"🎯 Can be commander: {commander_status}")
        print(f"⚖️ Format legal: {format_status}")
        
        # Overall verdict
        if can_be_commander and is_format_legal:
            print("🏆 Verdict: ✅ Legal Commander!")
        elif can_be_commander and not is_format_legal:
            print("🏆 Verdict: ⚠️ Can be commander but banned in format")
        elif not can_be_commander and is_format_legal:
            print("🏆 Verdict: ⚠️ Legal in format but can't be commander")
        else:
            print("🏆 Verdict: ❌ Not legal as commander")
            
    except Exception as e:
        print(f"❌ Error: {e}")

def main():
    """Run the demonstration."""
    print("MTG Commander Legality Checker - Live Demo")
    print_separator()
    
    print("This demo shows the new Commander legality checking functionality")
    print("using the Scryfall API to verify card eligibility and format legality.")
    
    # Initialize Scryfall service
    print("\n⏳ Initializing Scryfall service...")
    scryfall = ScryfallService()
    print("✅ Ready!")
    
    # Test cases with different types of cards
    test_cases = [
        ("Atraxa, Praetors' Voice", "Popular 4-color legendary creature"),
        ("Edgar Markov", "Vampire tribal commander"),
        ("Freyalise, Llanowar's Fury", "Planeswalker commander from C14"),
        ("Thrasios, Triton Hero", "Partner commander"),
        ("Lightning Bolt", "Non-legendary spell"),
        ("Jace, the Mind Sculptor", "Planeswalker without commander ability"),
        ("Black Lotus", "Banned card"),
        ("Sol Ring", "Legal artifact but not a commander"),
    ]
    
    print_separator("Individual Card Checks")
    
    for card_name, description in test_cases:
        check_card_legality(scryfall, card_name, description)
        time.sleep(0.2)  # Small delay to be nice to the API
    
    # Demonstrate batch checking
    print_separator("Batch Legality Check")
    
    print("\n🔍 Batch checking multiple cards at once...")
    batch_cards = [card[0] for card in test_cases[:5]]  # First 5 cards
    
    try:
        results = scryfall.batch_check_commander_legality(batch_cards)
        
        print(f"\n📊 Batch Results ({len(results)} cards):")
        for card_name, is_legal in results.items():
            status = "✅ Legal" if is_legal else "❌ Not Legal"
            print(f"   {status} - {card_name}")
            
    except Exception as e:
        print(f"❌ Batch check failed: {e}")
    
    # Show cache statistics
    print_separator("Cache Statistics")
    
    try:
        cache_stats = scryfall.get_cache_stats()
        print(f"📁 Cache Directory: {cache_stats['cache_dir']}")
        print(f"💾 Cached Cards: {cache_stats['cached_cards']}")
        print(f"📏 Cache Size: {cache_stats['total_size_mb']:.2f} MB")
    except Exception as e:
        print(f"❌ Could not get cache stats: {e}")
    
    print_separator("Demo Complete")
    print("🎉 The Commander legality checking feature is working!")
    print("\nKey benefits:")
    print("• ✅ Real-time validation using Scryfall API")
    print("• 🚀 Batch processing for efficiency")
    print("• 💾 Local caching to reduce API calls")
    print("• 🎯 Comprehensive commander type support")
    print("• ⚖️ Format legality verification")
    
    print(f"\nTo use in CLI:")
    print(f"  mtg-deck-builder --check-legality \"Atraxa, Praetors' Voice\"")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n⚠ Demo interrupted by user")
    except Exception as e:
        print(f"\n❌ Demo failed: {e}")
        print("This might be due to network issues or API rate limiting.")