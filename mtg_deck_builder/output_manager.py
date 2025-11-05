"""Output manager for handling deck file generation and formatting."""

import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List
from .models import Deck, DeckStatistics
from .scryfall_service import ScryfallService


class OutputManager:
    """Handles deck file output, formatting, and statistics generation."""
    
    def __init__(self, output_directory: str = ".", scryfall_service: ScryfallService = None):
        """
        Initialize output manager.
        
        Args:
            output_directory: Directory where deck files will be written
            scryfall_service: Optional Scryfall service for card images
        """
        self.output_directory = Path(output_directory)
        self.output_directory.mkdir(parents=True, exist_ok=True)
        self.scryfall_service = scryfall_service or ScryfallService()
    
    def generate_filename(self, commander: str) -> str:
        """
        Generate unique filename for deck output with timestamp handling.
        
        Args:
            commander: Name of the commander card
            
        Returns:
            Unique filename with timestamp if needed
        """
        # Sanitize commander name for filename
        safe_name = self._sanitize_filename(commander)
        base_filename = f"{safe_name}_deck.txt"
        full_path = self.output_directory / base_filename
        
        # If file doesn't exist, use base name
        if not full_path.exists():
            return base_filename
        
        # If file exists, append timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        timestamped_filename = f"{safe_name}_deck_{timestamp}.txt"
        return timestamped_filename
    
    def _sanitize_filename(self, name: str) -> str:
        """
        Sanitize a string to be safe for use as a filename.
        
        Args:
            name: Raw string to sanitize
            
        Returns:
            Sanitized filename-safe string
        """
        # Replace spaces with underscores and remove special characters
        sanitized = name.lower().replace(" ", "_")
        sanitized = "".join(c for c in sanitized if c.isalnum() or c in "_-")
        
        # Ensure it's not empty and not too long
        if not sanitized:
            sanitized = "unknown_commander"
        
        # Limit length to avoid filesystem issues
        return sanitized[:50]
    
    def format_deck_list(self, deck: Deck, statistics: DeckStatistics = None, purchase_suggestions: List = None) -> str:
        """
        Format deck list in readable text format.
        
        Args:
            deck: Deck object to format
            statistics: Optional deck statistics to include
            
        Returns:
            Formatted deck list as string
        """
        lines = []
        
        # Header
        lines.append("=" * 60)
        lines.append(f"MTG Commander Deck: {deck.commander}")
        lines.append("=" * 60)
        lines.append("")
        
        # Commander section
        lines.append("COMMANDER:")
        lines.append(f"1 {deck.commander}")
        lines.append("")
        
        # Main deck section
        lines.append(f"MAIN DECK ({len(deck.cards)} cards):")
        
        # Sort cards alphabetically for consistent output
        sorted_cards = sorted(deck.cards)
        for card in sorted_cards:
            lines.append(f"1 {card}")
        
        lines.append("")
        
        # Deck summary
        lines.append("DECK SUMMARY:")
        lines.append(f"Total Cards: {deck.total_cards}")
        lines.append(f"Commander: {deck.commander}")
        
        if deck.color_identity:
            colors = ", ".join(deck.color_identity)
            lines.append(f"Color Identity: {colors}")
        
        # Add statistics if provided
        if statistics:
            lines.append("")
            lines.append("DECK STATISTICS:")
            lines.append(f"Average CMC: {statistics.average_cmc:.2f}")
            lines.append("")
            
            # Card type breakdown
            lines.append("CARD TYPE BREAKDOWN:")
            card_types_order = ['creature', 'enchantment', 'artifact', 'instant', 'sorcery', 'planeswalker', 'land']
            for card_type in card_types_order:
                count = statistics.card_types.get(card_type, 0)
                if count > 0:
                    percentage = (count / statistics.total_cards) * 100
                    lines.append(f"  {card_type.title()}: {count} ({percentage:.1f}%)")
            
            lines.append("")
            
            # Mana curve
            lines.append("MANA CURVE:")
            for cmc in range(0, 8):
                count = statistics.mana_curve.get(cmc, 0)
                if count > 0:
                    bar = "█" * min(count, 15)  # Visual bar representation
                    lines.append(f"  CMC {cmc}: {count:2d} {bar}")
            
            # High CMC cards (8+)
            high_cmc_count = sum(statistics.mana_curve.get(i, 0) for i in range(8, 16))
            if high_cmc_count > 0:
                bar = "█" * min(high_cmc_count, 15)
                lines.append(f"  CMC 8+: {high_cmc_count:2d} {bar}")
            
            if statistics.synergy_score > 0:
                lines.append("")
                lines.append(f"Synergy Score: {statistics.synergy_score:.2f}")
        
        # Validation status
        lines.append("")
        validation_results = deck.validate()
        if deck.is_valid():
            lines.append("✓ Deck passes all Commander format validation checks")
        else:
            lines.append("⚠ Deck validation issues found:")
            for error in deck.get_validation_errors():
                lines.append(f"  - {error}")
        
        # Add purchase suggestions if provided
        if purchase_suggestions:
            lines.append("")
            lines.append("PURCHASE SUGGESTIONS:")
            lines.append("Cards to improve deck synergy:")
            lines.append("")
            
            total_price = 0.0
            for i, card_data in enumerate(purchase_suggestions, 1):
                prices = card_data.prices or {}
                price_eur = prices.get('eur')
                price_usd = prices.get('usd')
                
                price_str = "Price unavailable"
                if price_eur:
                    try:
                        price_val = float(price_eur)
                        price_str = f"€{price_val:.2f}"
                        total_price += price_val
                    except (ValueError, TypeError):
                        pass
                elif price_usd:
                    try:
                        price_val = float(price_usd)
                        price_str = f"${price_val:.2f}"
                        total_price += price_val * 0.85  # Rough EUR conversion
                    except (ValueError, TypeError):
                        pass
                
                # Generate purchase link
                import urllib.parse
                encoded_name = urllib.parse.quote(card_data.name)
                purchase_link = f"https://www.cardmarket.com/en/Magic/Products/Search?category=-1&searchString={encoded_name}&searchMode=v1"
                
                lines.append(f"{i:2d}. {card_data.name}")
                lines.append(f"    Type: {card_data.type_line}")
                lines.append(f"    Mana Cost: {card_data.mana_cost or 'N/A'}")
                lines.append(f"    Price: {price_str}")
                if purchase_link:
                    lines.append(f"    Buy: {purchase_link}")
                lines.append("")
            
            if total_price > 0:
                lines.append(f"Total estimated cost: €{total_price:.2f}")
                lines.append("")
        
        lines.append("")
        lines.append("Generated by MTG Commander Deck Builder")
        lines.append(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        return "\n".join(lines)
    
    def format_deck_html(self, deck: Deck, statistics: DeckStatistics = None, purchase_suggestions: List = None) -> str:
        """
        Format deck as beautiful HTML with purchase suggestions.
        
        Args:
            deck: Deck object to format
            statistics: Optional deck statistics
            purchase_suggestions: Optional purchase suggestions
            
        Returns:
            HTML formatted deck list
        """
        html_parts = []
        
        # HTML header with CSS
        html_parts.append("""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MTG Commander Deck: {commander}</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.6;
            margin: 0;
            padding: 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 15px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.3);
            overflow: hidden;
        }}
        .header {{
            background: linear-gradient(135deg, #2c3e50 0%, #34495e 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }}
        .header h1 {{
            margin: 0;
            font-size: 2.5em;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        }}
        .content {{
            padding: 30px;
        }}
        .section {{
            margin-bottom: 30px;
            background: #f8f9fa;
            border-radius: 10px;
            padding: 20px;
            border-left: 5px solid #3498db;
        }}
        .section h2 {{
            color: #2c3e50;
            margin-top: 0;
            border-bottom: 2px solid #3498db;
            padding-bottom: 10px;
        }}
        .deck-list {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
        }}
        .card-item {{
            background: white;
            padding: 15px;
            border-radius: 8px;
            border-left: 4px solid #e74c3c;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
            transition: transform 0.2s;
            display: flex;
            align-items: center;
            gap: 15px;
        }}
        .card-item:hover {{
            transform: translateY(-2px);
            box-shadow: 0 4px 10px rgba(0,0,0,0.15);
        }}
        .deck-card-image {{
            width: 60px;
            height: 84px;
            border-radius: 4px;
            box-shadow: 0 1px 4px rgba(0,0,0,0.3);
            object-fit: cover;
            flex-shrink: 0;
        }}
        .card-name {{
            font-weight: bold;
            flex: 1;
        }}
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
        }}
        .stat-card {{
            background: white;
            padding: 20px;
            border-radius: 10px;
            text-align: center;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        .stat-number {{
            font-size: 2em;
            font-weight: bold;
            color: #3498db;
        }}
        .mana-curve {{
            display: flex;
            align-items: end;
            gap: 5px;
            height: 150px;
            margin: 20px 0;
        }}
        .mana-bar {{
            background: linear-gradient(to top, #3498db, #5dade2);
            border-radius: 4px 4px 0 0;
            min-width: 30px;
            display: flex;
            flex-direction: column;
            justify-content: end;
            align-items: center;
            color: white;
            font-weight: bold;
            text-shadow: 1px 1px 2px rgba(0,0,0,0.5);
        }}
        .purchase-suggestions {{
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
            color: white;
            border-left-color: #e74c3c;
        }}
        .purchase-suggestions h2 {{
            color: white;
            border-bottom-color: rgba(255,255,255,0.3);
        }}
        .suggestion-card {{
            background: rgba(255,255,255,0.95);
            color: #2c3e50;
            margin: 15px 0;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.2);
            display: flex;
            gap: 20px;
            align-items: flex-start;
        }}
        .card-image {{
            width: 120px;
            height: 168px;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.3);
            object-fit: cover;
            flex-shrink: 0;
        }}
        .card-info {{
            flex: 1;
        }}
        .suggestion-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 10px;
        }}
        .card-name {{
            font-size: 1.2em;
            font-weight: bold;
            color: #2c3e50;
        }}
        .card-price {{
            font-size: 1.1em;
            font-weight: bold;
            color: #27ae60;
        }}
        .card-details {{
            font-size: 0.9em;
            color: #7f8c8d;
            margin: 5px 0;
        }}
        .buy-button {{
            display: inline-block;
            background: linear-gradient(135deg, #27ae60, #2ecc71);
            color: white;
            padding: 8px 16px;
            text-decoration: none;
            border-radius: 5px;
            font-weight: bold;
            transition: transform 0.2s;
        }}
        .buy-button:hover {{
            transform: scale(1.05);
            text-decoration: none;
            color: white;
        }}
        .total-cost {{
            background: rgba(255,255,255,0.2);
            padding: 15px;
            border-radius: 10px;
            text-align: center;
            font-size: 1.2em;
            font-weight: bold;
            margin-top: 20px;
        }}
        .commander-card {{
            background: linear-gradient(135deg, #f39c12, #e67e22);
            color: white;
            border-left-color: #d35400;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>MTG Commander Deck</h1>
            <h2>{commander}</h2>
        </div>
        <div class="content">""".format(commander=deck.commander))
        
        # Commander section
        html_parts.append(f"""
            <div class="section commander-card">
                <h2>Commander</h2>
                <div class="card-item">""")
        
        # Get commander image
        try:
            commander_data = self.scryfall_service.get_card_data(deck.commander)
            if commander_data and commander_data.image_uris:
                image_uris = commander_data.image_uris or {}
                commander_image = (image_uris.get('normal') or 
                                 image_uris.get('large') or "")
                if commander_image:
                    html_parts.append(f'                    <img src="{commander_image}" alt="{deck.commander}" class="deck-card-image" style="width: 80px; height: 112px;" loading="lazy">')
        except:
            pass  # If we can't get commander image, just skip it
        
        html_parts.append(f"""                    <div class="card-name"><strong>1 {deck.commander}</strong></div>
                </div>
            </div>""")
        
        # Main deck section
        html_parts.append(f"""
            <div class="section">
                <h2>Main Deck ({len(deck.cards)} cards)</h2>
                <div class="deck-list">""")
        
        # Sort cards alphabetically and get their images
        sorted_cards = sorted(deck.cards)
        
        # Get card images for deck cards (batch process for efficiency)
        card_images = self._get_card_images_for_deck(sorted_cards)
        
        for card in sorted_cards:
            image_url = card_images.get(card, "")
            
            html_parts.append(f'                    <div class="card-item">')
            
            if image_url:
                html_parts.append(f'                        <img src="{image_url}" alt="{card}" class="deck-card-image" loading="lazy">')
            
            html_parts.append(f'                        <div class="card-name">1 {card}</div>')
            html_parts.append(f'                    </div>')
        
        html_parts.append("                </div>\n            </div>")
        
        # Statistics section
        if statistics:
            html_parts.append("""
            <div class="section">
                <h2>Deck Statistics</h2>
                <div class="stats-grid">""")
            
            # Basic stats
            html_parts.append(f"""
                    <div class="stat-card">
                        <div class="stat-number">{statistics.average_cmc:.2f}</div>
                        <div>Average CMC</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-number">{deck.total_cards}</div>
                        <div>Total Cards</div>
                    </div>""")
            
            if statistics.synergy_score > 0:
                html_parts.append(f"""
                    <div class="stat-card">
                        <div class="stat-number">{statistics.synergy_score:.2f}</div>
                        <div>Synergy Score</div>
                    </div>""")
            
            html_parts.append("                </div>")
            
            # Card type breakdown
            html_parts.append("""
                <h3>Card Type Breakdown</h3>
                <div class="stats-grid">""")
            
            card_types_order = ['creature', 'enchantment', 'artifact', 'instant', 'sorcery', 'planeswalker', 'land']
            for card_type in card_types_order:
                count = statistics.card_types.get(card_type, 0)
                if count > 0:
                    percentage = (count / statistics.total_cards) * 100
                    html_parts.append(f"""
                    <div class="stat-card">
                        <div class="stat-number">{count}</div>
                        <div>{card_type.title()} ({percentage:.1f}%)</div>
                    </div>""")
            
            html_parts.append("                </div>")
            
            # Mana curve
            html_parts.append("""
                <h3>Mana Curve</h3>
                <div class="mana-curve">""")
            
            max_count = max(statistics.mana_curve.values()) if statistics.mana_curve.values() else 1
            for cmc in range(0, 8):
                count = statistics.mana_curve.get(cmc, 0)
                height = (count / max_count * 120) if max_count > 0 else 0
                html_parts.append(f"""
                    <div class="mana-bar" style="height: {height}px;">
                        <div style="margin-bottom: 5px;">{count}</div>
                        <div style="font-size: 0.8em;">{cmc}</div>
                    </div>""")
            
            # High CMC cards (8+)
            high_cmc_count = sum(statistics.mana_curve.get(i, 0) for i in range(8, 16))
            if high_cmc_count > 0:
                height = (high_cmc_count / max_count * 120) if max_count > 0 else 0
                html_parts.append(f"""
                    <div class="mana-bar" style="height: {height}px;">
                        <div style="margin-bottom: 5px;">{high_cmc_count}</div>
                        <div style="font-size: 0.8em;">8+</div>
                    </div>""")
            
            html_parts.append("                </div>\n            </div>")
        
        # Purchase suggestions section
        if purchase_suggestions:
            html_parts.append("""
            <div class="section purchase-suggestions">
                <h2>💰 Purchase Suggestions</h2>
                <p>Cards to improve your deck's synergy:</p>""")
            
            total_price = 0.0
            for i, card_data in enumerate(purchase_suggestions, 1):
                prices = card_data.prices or {}
                price_eur = prices.get('eur')
                price_usd = prices.get('usd')
                
                price_str = "Price unavailable"
                price_val = 0.0
                if price_eur:
                    try:
                        price_val = float(price_eur)
                        price_str = f"€{price_val:.2f}"
                        total_price += price_val
                    except (ValueError, TypeError):
                        pass
                elif price_usd:
                    try:
                        price_val = float(price_usd)
                        price_str = f"${price_val:.2f}"
                        total_price += price_val * 0.85  # Rough EUR conversion
                    except (ValueError, TypeError):
                        pass
                
                # Generate purchase link
                import urllib.parse
                encoded_name = urllib.parse.quote(card_data.name)
                purchase_link = f"https://www.cardmarket.com/en/Magic/Products/Search?category=-1&searchString={encoded_name}&searchMode=v1"
                
                # Get card image URL
                image_url = ""
                if card_data.image_uris:
                    image_uris = card_data.image_uris or {}
                    # Prefer small image for faster loading
                    image_url = (image_uris.get('small') or 
                               image_uris.get('normal') or 
                               image_uris.get('large') or "")
                
                html_parts.append(f"""
                <div class="suggestion-card">""")
                
                # Add card image if available
                if image_url:
                    html_parts.append(f"""
                    <img src="{image_url}" alt="{card_data.name}" class="card-image" loading="lazy">""")
                
                html_parts.append(f"""
                    <div class="card-info">
                        <div class="suggestion-header">
                            <div class="card-name">{i}. {card_data.name}</div>
                            <div class="card-price">{price_str}</div>
                        </div>
                        <div class="card-details">Type: {card_data.type_line}</div>
                        <div class="card-details">Mana Cost: {card_data.mana_cost or 'N/A'}</div>""")
                
                if card_data.oracle_text:
                    # Truncate long oracle text
                    oracle_text = card_data.oracle_text[:200] + "..." if len(card_data.oracle_text) > 200 else card_data.oracle_text
                    html_parts.append(f'                    <div class="card-details">{oracle_text}</div>')
                
                if purchase_link:
                    html_parts.append(f'                        <a href="{purchase_link}" class="buy-button" target="_blank">Buy Now</a>')
                
                html_parts.append("                    </div>\n                </div>")
            
            if total_price > 0:
                html_parts.append(f"""
                <div class="total-cost">
                    Total estimated cost: €{total_price:.2f}
                </div>""")
            
            html_parts.append("            </div>")
        
        # Footer
        html_parts.append(f"""
        </div>
    </div>
    <div style="text-align: center; padding: 20px; color: white;">
        Generated by MTG Commander Deck Builder on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
    </div>
</body>
</html>""")
        
        return "\n".join(html_parts)
    
    def _get_card_images_for_deck(self, card_names: List[str]) -> Dict[str, str]:
        """
        Get card images for deck cards efficiently.
        
        Args:
            card_names: List of card names to get images for
            
        Returns:
            Dictionary mapping card names to image URLs
        """
        card_images = {}
        
        # Limit the number of cards we fetch images for to avoid too many API calls
        # We'll prioritize the first 50 cards for images
        limited_cards = card_names[:50]
        
        for card_name in limited_cards:
            try:
                card_data = self.scryfall_service.get_card_data(card_name)
                if card_data and card_data.image_uris:
                    image_uris = card_data.image_uris or {}
                    # Prefer small image for faster loading in deck list
                    image_url = (image_uris.get('small') or 
                               image_uris.get('normal') or "")
                    if image_url:
                        card_images[card_name] = image_url
            except Exception as e:
                # If we can't get an image, just skip it
                continue
        
        return card_images
    
    def write_deck_file(self, deck: Deck, filename: str = None, statistics: DeckStatistics = None, purchase_suggestions: List = None) -> str:
        """
        Write deck to file with proper error handling and permissions.
        
        Args:
            deck: Deck object to write
            filename: Optional custom filename (will generate if not provided)
            statistics: Optional deck statistics to include
            purchase_suggestions: Optional list of CardData objects for purchase suggestions
            
        Returns:
            Path to the written file
            
        Raises:
            OSError: If file cannot be written due to permissions or disk space
            ValueError: If deck is invalid or empty
        """
        if not deck.commander:
            raise ValueError("Cannot write deck file: deck has no commander")
        
        if len(deck.cards) == 0:
            raise ValueError("Cannot write deck file: deck has no cards")
        
        # Generate filename if not provided
        if filename is None:
            filename = self.generate_filename(deck.commander)
        
        file_path = self.output_directory / filename
        
        try:
            # Format the deck list
            formatted_deck = self.format_deck_list(deck, statistics, purchase_suggestions)
            
            # Write text file
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(formatted_deck)
            
            # Set readable permissions (644)
            os.chmod(file_path, 0o644)
            
            # Generate HTML file
            html_path = file_path.with_suffix('.html')
            html_content = self.format_deck_html(deck, statistics, purchase_suggestions)
            
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            os.chmod(html_path, 0o644)
            
            return str(file_path)
            
        except OSError as e:
            raise OSError(f"Failed to write deck file '{file_path}': {e}")
        except Exception as e:
            raise OSError(f"Unexpected error writing deck file '{file_path}': {e}")
    
    def generate_deck_statistics(self, deck: Deck, card_recommendations: List = None) -> DeckStatistics:
        """
        Generate comprehensive deck statistics for analysis.
        
        Args:
            deck: Deck object to analyze
            card_recommendations: Optional list of card recommendations with synergy scores
            
        Returns:
            DeckStatistics object with complete analysis
        """
        stats = DeckStatistics()
        stats.total_cards = deck.total_cards
        
        # Analyze all cards including commander
        all_cards = [deck.commander] + deck.cards
        
        # Initialize counters
        total_cmc = 0
        card_count_for_cmc = 0
        
        # Process each card for statistics
        for card in all_cards:
            # Get card type and CMC (simplified analysis based on card name patterns)
            card_type, cmc = self._analyze_card(card)
            
            # Update card type counts
            if card_type in stats.card_types:
                stats.card_types[card_type] += 1
            
            # Update mana curve (exclude lands from CMC calculation)
            if card_type != 'land':
                if cmc < 16:
                    stats.mana_curve[cmc] += 1
                else:
                    stats.mana_curve[15] += 1  # 15+ category
                
                total_cmc += cmc
                card_count_for_cmc += 1
        
        # Calculate average CMC (excluding lands)
        if card_count_for_cmc > 0:
            stats.average_cmc = total_cmc / card_count_for_cmc
        
        # Analyze color distribution (simplified)
        stats.color_distribution = self._analyze_color_distribution(all_cards)
        
        # Calculate synergy score if recommendations provided
        if card_recommendations:
            stats.synergy_score = self._calculate_synergy_score(deck, card_recommendations)
        
        return stats
    
    def _analyze_card(self, card_name: str) -> tuple[str, int]:
        """
        Analyze card to determine type and CMC based on name patterns.
        
        Note: This is a simplified analysis. In a full implementation,
        this would query a card database for accurate type and CMC data.
        
        Args:
            card_name: Name of the card to analyze
            
        Returns:
            Tuple of (card_type, converted_mana_cost)
        """
        name_lower = card_name.lower()
        
        # Basic land detection
        basic_lands = {
            'plains', 'island', 'swamp', 'mountain', 'forest', 'wastes',
            'snow-covered plains', 'snow-covered island', 'snow-covered swamp',
            'snow-covered mountain', 'snow-covered forest'
        }
        
        if name_lower in basic_lands:
            return 'land', 0
        
        # Common land name patterns
        land_keywords = [
            'command tower', 'castle', 'temple', 'guild', 'shock', 'fetch', 'village',
            'haven', 'crossroads', 'sanctum', 'tower', 'land'
        ]
        if any(keyword in name_lower for keyword in land_keywords):
            return 'land', 0
        
        # Artifact patterns - more comprehensive
        artifact_keywords = [
            'sol ring', 'signet', 'talisman', 'mox', 'vault', 'crypt', 'sphere',
            'rod', 'lance', 'glove', 'horn', 'copter', 'airship', 'scarecrow',
            'golem', 'welding jar', 'ruin', 'pala', 'basket', 'pot', 'pandora',
            'auracite', 'down', 'tub', 'masamune'
        ]
        
        # Check for specific artifacts first
        if name_lower in ['sol ring', 'arcane signet', 'commander\'s sphere']:
            return 'artifact', 2
        elif 'signet' in name_lower or 'talisman' in name_lower:
            return 'artifact', 2
        elif any(keyword in name_lower for keyword in artifact_keywords):
            # Estimate CMC based on common artifact patterns
            if any(x in name_lower for x in ['mox', 'welding jar']):
                return 'artifact', 0
            elif any(x in name_lower for x in ['sol ring', 'signet']):
                return 'artifact', 2
            elif any(x in name_lower for x in ['sphere', 'horn', 'copter']):
                return 'artifact', 3
            else:
                return 'artifact', 4
        
        # Enchantment patterns
        enchantment_keywords = [
            'honden', 'pacifism', 'vigilance', 'fetters', 'breath', 'haze',
            'offering', 'purity', 'valor', 'vengeance', 'court', 'case'
        ]
        if any(keyword in name_lower for keyword in enchantment_keywords):
            if any(x in name_lower for x in ['pacifism', 'vigilance', 'breath']):
                return 'enchantment', 1
            elif any(x in name_lower for x in ['honden', 'court']):
                return 'enchantment', 4
            else:
                return 'enchantment', 3
        
        # Instant patterns
        instant_keywords = [
            'path to exile', 'swords to plowshares', 'counterspell', 'clever concealment', 
            'hold the line', 'slash of light', 'candles\' glow', 'blessed breath', 
            'ethereal haze', 'divine offering', 'cleanfall', 'first come, first served'
        ]
        if any(keyword in name_lower for keyword in instant_keywords):
            if 'path to exile' in name_lower or 'swords to plowshares' in name_lower:
                return 'instant', 1
            elif 'counterspell' in name_lower:
                return 'instant', 2
            elif any(x in name_lower for x in ['breath', 'glow', 'haze']):
                return 'instant', 1
            else:
                return 'instant', 2
        
        # Sorcery patterns
        sorcery_keywords = [
            'wrath of god', 'day of judgment', 'cultivate', 'battle screech', 
            'call the coppercoats', 'collective effort', 'battle menu', 
            'rescue mission', 'inspiration'
        ]
        if any(keyword in name_lower for keyword in sorcery_keywords):
            if 'wrath' in name_lower or 'day of judgment' in name_lower:
                return 'sorcery', 4
            elif 'cultivate' in name_lower:
                return 'sorcery', 3
            elif 'battle' in name_lower:
                return 'sorcery', 3
            else:
                return 'sorcery', 4
        
        # Planeswalker patterns
        if any(keyword in name_lower for keyword in ['planeswalker', 'jace', 'chandra', 'garruk', 'liliana', 'ajani']):
            return 'planeswalker', 4
        
        # Creature patterns - more specific detection
        creature_keywords = [
            'steiner', 'liberator', 'dragon', 'moogle', 'coeurl', 'packbeasts',
            'retainer', 'guard', 'moth', 'deceiver', 'seeker', 'kami', 'samurai',
            'skyhunter', 'girl', 'infantry', 'dawnbreaker', 'zubera', 'army',
            'blademaster', 'diviner', 'healer', 'riftwalker', 'hatamoto'
        ]
        
        # Check if it's likely a creature
        if any(keyword in name_lower for keyword in creature_keywords):
            # Estimate CMC based on creature type
            if any(x in name_lower for x in ['girl', 'moth', 'seeker']):
                return 'creature', 1
            elif any(x in name_lower for x in ['kami', 'guard', 'retainer']):
                return 'creature', 2
            elif any(x in name_lower for x in ['samurai', 'liberator', 'moogle']):
                return 'creature', 3
            elif any(x in name_lower for x in ['dragon', 'steiner']):
                return 'creature', 5
            else:
                return 'creature', 3
        
        # Default classification based on common patterns
        # If it has specific action words, likely instant/sorcery
        if any(word in name_lower for word in ['you\'re', 'fate', 'hero', 'heart']):
            return 'sorcery', 3
        
        # Default to creature with estimated CMC
        estimated_cmc = min(max(len(card_name.split()) - 1, 1), 8)
        return 'creature', estimated_cmc
    
    def _analyze_color_distribution(self, cards: List[str]) -> Dict[str, int]:
        """
        Analyze color distribution of cards in the deck.
        
        Note: This is a simplified analysis based on card name patterns.
        In a full implementation, this would query a card database.
        
        Args:
            cards: List of card names to analyze
            
        Returns:
            Dictionary with color distribution counts
        """
        color_dist = {
            'white': 0,
            'blue': 0,
            'black': 0,
            'red': 0,
            'green': 0,
            'colorless': 0
        }
        
        # Color keyword associations (simplified)
        color_keywords = {
            'white': ['angel', 'knight', 'soldier', 'cleric', 'plains', 'white'],
            'blue': ['wizard', 'merfolk', 'counter', 'draw', 'island', 'blue'],
            'black': ['demon', 'zombie', 'vampire', 'destroy', 'swamp', 'black'],
            'red': ['dragon', 'goblin', 'bolt', 'burn', 'mountain', 'red'],
            'green': ['elf', 'beast', 'ramp', 'forest', 'green', 'mana']
        }
        
        for card in cards:
            card_lower = card.lower()
            colors_found = []
            
            # Check for color keywords
            for color, keywords in color_keywords.items():
                if any(keyword in card_lower for keyword in keywords):
                    colors_found.append(color)
            
            # If no colors found, assume colorless
            if not colors_found:
                color_dist['colorless'] += 1
            else:
                # If multiple colors found, count for each (multicolored cards)
                for color in colors_found:
                    color_dist[color] += 1
        
        return color_dist
    
    def _calculate_synergy_score(self, deck: Deck, card_recommendations: List) -> float:
        """
        Calculate overall synergy score for the deck.
        
        Args:
            deck: Deck object to analyze
            card_recommendations: List of CardRecommendation objects
            
        Returns:
            Average synergy score (0.0 to 1.0)
        """
        if not card_recommendations:
            return 0.0
        
        # Create lookup for synergy scores
        synergy_lookup = {}
        for rec in card_recommendations:
            if hasattr(rec, 'name') and hasattr(rec, 'synergy_score'):
                synergy_lookup[rec.name.lower()] = rec.synergy_score
        
        # Calculate average synergy for cards in deck
        total_synergy = 0.0
        cards_with_synergy = 0
        
        for card in deck.cards:
            card_lower = card.lower()
            if card_lower in synergy_lookup:
                total_synergy += synergy_lookup[card_lower]
                cards_with_synergy += 1
        
        if cards_with_synergy == 0:
            return 0.0
        
        return total_synergy / cards_with_synergy
    
    def create_summary_report(self, deck: Deck, statistics: DeckStatistics) -> str:
        """
        Create a detailed summary report for deck composition and analysis.
        
        Args:
            deck: Deck object to report on
            statistics: DeckStatistics with analysis data
            
        Returns:
            Formatted summary report as string
        """
        lines = []
        
        lines.append("DECK COMPOSITION ANALYSIS")
        lines.append("=" * 40)
        lines.append("")
        
        # Card type breakdown
        lines.append("Card Types:")
        for card_type, count in statistics.card_types.items():
            if count > 0:
                percentage = (count / statistics.total_cards) * 100
                lines.append(f"  {card_type.title()}: {count} ({percentage:.1f}%)")
        
        lines.append("")
        
        # Mana curve analysis
        lines.append("Mana Curve:")
        for cmc in range(0, 8):
            count = statistics.mana_curve.get(cmc, 0)
            if count > 0:
                bar = "█" * min(count, 20)  # Visual bar representation
                lines.append(f"  CMC {cmc}: {count:2d} {bar}")
        
        # High CMC cards
        high_cmc_count = sum(statistics.mana_curve.get(i, 0) for i in range(8, 16))
        if high_cmc_count > 0:
            bar = "█" * min(high_cmc_count, 20)
            lines.append(f"  CMC 8+: {high_cmc_count:2d} {bar}")
        
        lines.append("")
        lines.append(f"Average CMC: {statistics.average_cmc:.2f}")
        
        # Color distribution
        lines.append("")
        lines.append("Color Distribution:")
        for color, count in statistics.color_distribution.items():
            if count > 0:
                percentage = (count / statistics.total_cards) * 100
                lines.append(f"  {color.title()}: {count} ({percentage:.1f}%)")
        
        # Synergy analysis
        if statistics.synergy_score > 0:
            lines.append("")
            lines.append(f"Synergy Score: {statistics.synergy_score:.2f}/1.0")
            if statistics.synergy_score >= 0.8:
                lines.append("  Excellent synergy with commander")
            elif statistics.synergy_score >= 0.6:
                lines.append("  Good synergy with commander")
            elif statistics.synergy_score >= 0.4:
                lines.append("  Moderate synergy with commander")
            else:
                lines.append("  Low synergy with commander")
        
        # Deck balance assessment
        lines.append("")
        lines.append("Deck Balance Assessment:")
        
        creature_pct = statistics.creature_percentage
        land_pct = statistics.land_percentage
        
        if creature_pct < 20:
            lines.append("  ⚠ Low creature count - consider adding more threats")
        elif creature_pct > 50:
            lines.append("  ⚠ High creature count - consider more non-creature spells")
        else:
            lines.append("  ✓ Good creature balance")
        
        if land_pct < 30:
            lines.append("  ⚠ Low land count - may have mana issues")
        elif land_pct > 45:
            lines.append("  ⚠ High land count - may flood frequently")
        else:
            lines.append("  ✓ Good mana base size")
        
        if statistics.average_cmc > 4.5:
            lines.append("  ⚠ High average CMC - consider more low-cost cards")
        elif statistics.average_cmc < 2.5:
            lines.append("  ⚠ Low average CMC - may lack late-game power")
        else:
            lines.append("  ✓ Good mana curve balance")
        
        return "\n".join(lines)