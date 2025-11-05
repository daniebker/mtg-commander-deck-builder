#!/usr/bin/env python3
"""
Test script to demonstrate the new Commander legality checking functionality.
"""

import sys
import logging
from mtg_deck_builder.scryfall_service import ScryfallService

def test_commander_legality():
    """Test the Commander legality checking functionality."""
    
    # Set up logging
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    
    print("MTG Commander Legality Checker Test")
    print("=" * 40)
    
    # Initialize Scryfall service
    print("Initializing Scryfall service...")
    scryfall = ScryfallService()
    
    # Test cases: mix of legal commanders, illegal cards, and edge cases
    test_cards = [
        # Legal legendary creatures
        "Atraxa, Praetors' Voice",
        "Edgar Markov", 
        "The Ur-Dragon",
        "Meren of Clan Nel Toth",
        
        # Legal planeswalker commanders
        "Freyalise, Llanowar's Fury",
        "Daretti, Scrap Savant",
        
        # Partner commanders
        "Thrasios, Triton Hero",
        "Tymna the Weaver",
        
        # Non-legendary creatures (should fail)
        "Lightning Bolt",
        "Grizzly Bears",
        
        # Banned cards (should fail format legality)
        "Black Lotus",
        "Ancestral Recall",
        
        # Edge cases
        "Jace, the Mind Sculptor",  # Planeswalker without commander ability
        "Griselbrand",  # Legendary but banned
    ]
    
    print(f"\nTesting {len(test_cards)} cards...\n")
    
    results = []
    
    for i, card_name in enumerate(test_cards, 1):
        print(f"{i:2d}. Testing: {card_name}")
        print("-" * 50)
        
        try:
            # Check commander eligibility
            is_commander = scryfall.is_legal_commander(card_name)
            
            # Check format legality
            is_format_legal = scryfall.is_legal_in_commander(card_name)
            
            # Get card data for additional info
            card_data = scryfall.get_card_data(card_name)
            
            # Store results
            result = {
                'name': card_name,
                'can_be_commander': is_commander,
                'format_legal': is_format_legal,
                'type_line': card_data.type_line if card_data else 'Unknown',
                'overall_legal': is_commander and is_format_legal
            }
            results.append(result)
            
            # Display results
            print(f"   Type: {result['type_line']}")
            print(f"   Can be commander: {'✅ Yes' if is_commander else '❌ No'}")
            print(f"   Format legal: {'✅ Yes' if is_format_legal else '❌ No'}")
            print(f"   Overall: {'✅ Legal Commander' if result['overall_legal'] else '❌ Not Legal'}")
            
        except Exception as e:
            print(f"   ❌ Error: {e}")
            results.append({
                'name': card_name,
                'can_be_commander': False,
                'format_legal': False,
                'type_line': 'Error',
                'overall_legal': False,
                'error': str(e)
            })
        
        print()
    
    # Summary
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    legal_commanders = [r for r in results if r['overall_legal']]
    can_be_commanders = [r for r in results if r['can_be_commander']]
    format_legal = [r for r in results if r['format_legal']]
    errors = [r for r in results if 'error' in r]
    
    print(f"Total cards tested: {len(results)}")
    print(f"Legal commanders: {len(legal_commanders)}")
    print(f"Can be commanders: {len(can_be_commanders)}")
    print(f"Format legal: {len(format_legal)}")
    print(f"Errors: {len(errors)}")
    
    if legal_commanders:
        print(f"\n✅ Legal Commanders:")
        for result in legal_commanders:
            print(f"   • {result['name']}")
    
    if errors:
        print(f"\n❌ Errors encountered:")
        for result in errors:
            print(f"   • {result['name']}: {result['error']}")
    
    print(f"\n🎯 Success rate: {(len(results) - len(errors)) / len(results) * 100:.1f}%")


def test_batch_legality():
    """Test batch legality checking functionality."""
    
    print("\n" + "=" * 60)
    print("BATCH LEGALITY TEST")
    print("=" * 60)
    
    scryfall = ScryfallService()
    
    # Test batch checking
    test_cards = [
        "Atraxa, Praetors' Voice",
        "Lightning Bolt", 
        "Sol Ring",
        "Black Lotus",
        "Edgar Markov"
    ]
    
    print(f"Batch checking {len(test_cards)} cards...")
    
    try:
        results = scryfall.batch_check_commander_legality(test_cards)
        
        print("\nBatch Results:")
        for card_name, is_legal in results.items():
            status = "✅ Legal" if is_legal else "❌ Not Legal"
            print(f"   {card_name}: {status}")
            
    except Exception as e:
        print(f"❌ Batch test failed: {e}")


if __name__ == "__main__":
    try:
        test_commander_legality()
        test_batch_legality()
        print("\n🎉 All tests completed!")
        
    except KeyboardInterrupt:
        print("\n⚠ Tests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        sys.exit(1)