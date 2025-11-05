# Requirements Document

## Introduction

A command-line tool that generates MTG Commander deck recommendations based on a user's card collection CSV file and a specified commander. The tool leverages the pyedhrec package to fetch card synergy data and builds optimized deck lists using only cards available in the user's collection.

## Glossary

- **MTG_Deck_Builder**: The command-line application that generates Commander deck recommendations
- **Card_Collection_CSV**: A CSV file containing the user's Magic: The Gathering card collection data
- **Commander_Card**: The legendary creature that serves as the deck's commander and defines deck building constraints
- **Deck_Output_File**: A text file containing the generated 100-card Commander deck list
- **EDHREC_API**: The external service accessed via pyedhrec package for card recommendation data
- **Deck_Generation_Engine**: The core component that processes collection data and generates deck recommendations

## Requirements

### Requirement 1

**User Story:** As a Magic: The Gathering player, I want to input my card collection CSV and specify a commander, so that I can generate a playable Commander deck using only cards I own.

#### Acceptance Criteria

1. WHEN the user provides a valid CSV file path and commander name, THE MTG_Deck_Builder SHALL parse the Card_Collection_CSV and validate the commander exists in the collection
2. THE MTG_Deck_Builder SHALL integrate with the EDHREC_API via pyedhrec package to fetch card synergy recommendations for the specified Commander_Card
3. THE MTG_Deck_Builder SHALL generate a 100-card deck list using only cards present in the Card_Collection_CSV
4. THE MTG_Deck_Builder SHALL output the deck list to a Deck_Output_File named after the Commander_Card
5. IF a file with the same commander name already exists, THEN THE MTG_Deck_Builder SHALL append a timestamp to create a unique filename

### Requirement 2

**User Story:** As a user, I want the tool to handle various CSV formats and card name variations, so that I can use my existing collection data without reformatting.

#### Acceptance Criteria

1. THE MTG_Deck_Builder SHALL accept CSV files with standard Magic card collection headers including card name, quantity, and set information
2. THE MTG_Deck_Builder SHALL normalize card names to match EDHREC database entries for accurate lookups
3. WHEN card names contain special characters or alternate printings, THE MTG_Deck_Builder SHALL resolve them to canonical card names
4. THE MTG_Deck_Builder SHALL handle quantity information to ensure multiple copies of cards are considered during deck building

### Requirement 3

**User Story:** As a player, I want the generated deck to follow Commander format rules and be strategically coherent, so that the deck is legal and playable.

#### Acceptance Criteria

1. THE MTG_Deck_Builder SHALL ensure the generated deck contains exactly 100 cards including the Commander_Card
2. THE MTG_Deck_Builder SHALL enforce singleton rules where no card appears more than once except for basic lands
3. THE MTG_Deck_Builder SHALL respect color identity restrictions based on the Commander_Card's mana cost and rules text
4. THE Deck_Generation_Engine SHALL prioritize cards with high synergy ratings from EDHREC_API when multiple options are available
5. THE MTG_Deck_Builder SHALL include appropriate mana base cards from the collection to support the deck's color requirements

### Requirement 4

**User Story:** As a user, I want clear feedback about the deck building process and any limitations, so that I understand what cards were selected and why.

#### Acceptance Criteria

1. WHEN the Card_Collection_CSV lacks sufficient cards for a complete deck, THE MTG_Deck_Builder SHALL report the shortfall and generate a partial deck with available cards
2. THE MTG_Deck_Builder SHALL log which cards were selected based on EDHREC recommendations versus collection availability
3. THE MTG_Deck_Builder SHALL provide summary statistics about the generated deck including card types, mana curve, and color distribution
4. IF the specified Commander_Card is not found in the collection, THEN THE MTG_Deck_Builder SHALL terminate with a clear error message

### Requirement 5

**User Story:** As a command-line user, I want simple and intuitive tool usage with proper error handling, so that I can efficiently generate decks without technical issues.

#### Acceptance Criteria

1. THE MTG_Deck_Builder SHALL accept command-line arguments for CSV file path and commander name in a single invocation
2. THE MTG_Deck_Builder SHALL validate file paths and provide clear error messages for missing or inaccessible files
3. THE MTG_Deck_Builder SHALL handle network connectivity issues when accessing EDHREC_API gracefully with appropriate retry logic
4. THE MTG_Deck_Builder SHALL complete deck generation within reasonable time limits and provide progress feedback for long operations
5. THE MTG_Deck_Builder SHALL create the Deck_Output_File in the current working directory with proper file permissions