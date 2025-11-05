#!/usr/bin/env python3
"""
Example usage of the new Commander legality checking functionality.
"""

from mtg_deck_builder.scryfall_service import ScryfallService

def main():
    """Demonstrate the new Commander legality checking features."""
    
    print("MTG Commander Legality Checker - Example Usage")
    print("=" * 50)
    
    # Initialize the Scryfall service
    scryfall = ScryfallService()
    
    # Example 1: Check if a single card can be a commander
    print("Example 1: Single Commander Check")
    print("-" * 30)
    
    commander_name = "Atraxa, Praetors' Voice"
    print(f"Checking: {commander_name}")
    
    # Check if it can be a commander
    can_be_commander = scryfall.is_legal_commander(commander_name)
    print(f"Can be commander: {'Yes' if can_be_commander else 'No'}")
    
    # Check if it's legal in Commander format
    is_format_legal = scryfall.is_legal_in_commander(commander_name)
    print(f"Legal in Commander: {'Yes' if is_format_legal else 'No'}")
    
    # Get detailed card information
    card_data = scryfall.get_card_data(commander_name)
    if card_data:
        print(f"Type: {card_data.type_line}")
        print(f"Color Identity: {', '.join(card_data.color_identity) if card_data.color_identity else 'Colorless'}")
    
    print()
    
    # Example 2: Batch check multiple cards
    print("Example 2: Batch Legality Check")
    print("-" * 30)
    
    cards_to_check = [
        "Edgar Markov",
        "Lightning Bolt", 
        "Sol Ring",
        "The Ur-Dragon",
        "Black Lotus"
    ]
    
    print(f"Batch checking {len(cards_to_check)} cards...")
    legality_results = scryfall.batch_check_commander_legality(cards_to_check)
    
    for card_name, is_legal in legality_results.items():
        status = "✅" if is_legal else "❌"
        print(f"{status} {card_name}: {'Legal' if is_legal else 'Not Legal'}")
    
    print()
    
    # Example 3: Check a non-legendary creature
    print("Example 3: Non-Commander Card")
    print("-" * 30)
    
    non_commander = "Lightning Bolt"
    print(f"Checking: {non_commander}")
    
    can_be_commander = scryfall.is_legal_commander(non_commander)
    is_format_legal = scryfall.is_legal_in_commander(non_commander)
    
    print(f"Can be commander: {'Yes' if can_be_commander else 'No'}")
    print(f"Legal in Commander: {'Yes' if is_format_legal else 'No'}")
    
    if is_format_legal and not can_be_commander:
        print("→ This card can be included in the 99 cards of a Commander deck!")
    
    print()
    
    # Example 4: Check color identity
    print("Example 4: Color Identity Check")
    print("-" * 30)
    
    multicolor_commander = "Atraxa, Praetors' Voice"
    color_identity = scryfall.get_color_identity(multicolor_commander)
    
    print(f"Commander: {multicolor_commander}")
    print(f"Color Identity: {', '.join(color_identity) if color_identity else 'Colorless'}")
    print(f"Colors: {len(color_identity)}-color commander")
    
    print("\n🎉 Examples completed!")

if __name__ == "__main__":
    main()