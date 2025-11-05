# Implementation Plan

- [x] 1. Set up project structure and dependencies

  - Create Python package structure with proper **init**.py files
  - Set up pyproject.toml with pyedhrec dependency and project metadata
  - Create main entry point script for command-line execution
  - _Requirements: 5.1, 5.2_

- [x] 2. Implement core data models and validation

  - [x] 2.1 Create CardEntry and Deck data classes

    - Write CardEntry dataclass with name, quantity, set_code, and normalized_name fields
    - Implement Deck dataclass with commander, cards list, and validation methods
    - Add DeckStatistics dataclass for deck analysis data
    - _Requirements: 1.3, 3.1, 3.2_

  - [x] 2.2 Implement deck validation logic

    - Write validate() method for Deck class to check 100-card limit and singleton rules
    - Create color identity validation based on commander mana cost
    - Implement format legality checks for Commander rules
    - _Requirements: 3.1, 3.2, 3.3_

  - [x] 2.3 Write unit tests for data models
    - Create test cases for CardEntry creation and normalization
    - Test Deck validation with various card combinations
    - Verify color identity enforcement logic
    - _Requirements: 3.1, 3.2, 3.3_

- [x] 3. Build collection parser module

  - [x] 3.1 Implement CSV parsing functionality

    - Write load_collection() method to read and parse CSV files
    - Handle various CSV formats and column headers for card collections
    - Implement error handling for malformed CSV files with specific error messages
    - _Requirements: 2.1, 2.2, 5.2_

  - [x] 3.2 Create card name normalization system

    - Implement normalize_card_name() function to standardize card names
    - Handle special characters, alternate printings, and name variations
    - Create lookup system for resolving card name discrepancies
    - _Requirements: 2.2, 2.3_

  - [x] 3.3 Add commander validation

    - Write validate_commander() method to check if commander exists in collection
    - Implement commander legality checks (legendary creature requirement)
    - Add error handling for missing or invalid commanders
    - _Requirements: 1.1, 4.4_

  - [x] 3.4 Write unit tests for collection parser
    - Test CSV parsing with various file formats and edge cases
    - Verify card name normalization with known problematic names
    - Test commander validation with valid and invalid inputs
    - _Requirements: 2.1, 2.2, 4.4_

- [x] 4. Integrate EDHREC service functionality

  - [x] 4.1 Create EDHREC API wrapper

    - Implement get_commander_recommendations() using pyedhrec package
    - Write get_card_synergy_score() method for individual card ratings
    - Add CardRecommendation dataclass for API response data
    - _Requirements: 1.2, 3.4_

  - [x] 4.2 Implement API error handling and retry logic

    - Add handle_api_errors() method with exponential backoff retry
    - Implement graceful degradation when EDHREC API is unavailable
    - Create caching mechanism for API responses to reduce network calls
    - _Requirements: 5.3, 4.2_

  - [x] 4.3 Write integration tests for EDHREC service
    - Test API integration with mock responses
    - Verify error handling and retry mechanisms
    - Test caching functionality with repeated requests
    - _Requirements: 1.2, 5.3_

- [x] 5. Develop deck building engine

  - [x] 5.1 Implement core deck building algorithm

    - Write build_deck() method that orchestrates the entire deck building process
    - Create card filtering logic based on color identity restrictions
    - Implement card selection algorithm using EDHREC synergy scores and availability
    - _Requirements: 1.3, 3.3, 3.4_

  - [x] 5.2 Create mana base selection system

    - Implement select_mana_base() method to choose appropriate lands
    - Calculate optimal land count based on deck's mana requirements
    - Prioritize lands that support the commander's color identity
    - _Requirements: 3.5, 3.3_

  - [x] 5.3 Add deck balancing and optimization

    - Write balance_mana_curve() method to optimize converted mana cost distribution
    - Implement card categorization (removal, ramp, draw, etc.) for balanced deck building
    - Create enforce_singleton_rule() method to prevent duplicate cards
    - _Requirements: 3.2, 3.4, 3.5_

  - [x] 5.4 Handle insufficient card scenarios

    - Implement partial deck generation when collection lacks sufficient cards
    - Add logging for card selection decisions and availability constraints
    - Create fallback strategies for missing card categories
    - _Requirements: 4.1, 4.2_

  - [x] 5.5 Write unit tests for deck building engine
    - Test deck building with various collection sizes and commanders
    - Verify mana base selection with different color combinations
    - Test partial deck generation with insufficient collections
    - _Requirements: 1.3, 3.4, 4.1_

- [x] 6. Create output management system

  - [x] 6.1 Implement file output functionality

    - Write generate_filename() method with timestamp handling for unique names
    - Create format_deck_list() method to structure deck output in readable format
    - Implement write_deck_file() method with proper file permissions and error handling
    - _Requirements: 1.4, 1.5, 5.5_

  - [x] 6.2 Add deck statistics generation

    - Write generate_deck_statistics() method for mana curve and card type analysis
    - Create summary reporting for deck composition and synergy scores
    - Implement color distribution analysis for deck balance assessment
    - _Requirements: 4.3_

  - [x] 6.3 Write unit tests for output manager
    - Test filename generation with various commanders and timestamp scenarios
    - Verify deck list formatting with different deck compositions
    - Test file writing with various file system conditions
    - _Requirements: 1.4, 1.5, 4.3_

- [x] 7. Build command-line interface

  - [x] 7.1 Create CLI argument parsing

    - Implement parse_arguments() function using argparse for CSV path and commander name
    - Add input validation for file paths and commander names
    - Create help documentation and usage examples for the CLI
    - _Requirements: 5.1, 5.2_

  - [x] 7.2 Implement main orchestration logic

    - Write main() function that coordinates all components for deck building workflow
    - Add progress feedback for long-running operations like API calls
    - Implement comprehensive error handling with user-friendly error messages
    - _Requirements: 5.4, 4.1, 4.4_

  - [x] 7.3 Add logging and user feedback

    - Create logging system for debugging and user information
    - Implement progress indicators for deck building steps
    - Add verbose mode option for detailed operation reporting
    - _Requirements: 4.2, 5.4_

  - [x] 7.4 Write integration tests for CLI
    - Test end-to-end workflow with sample CSV files and commanders
    - Verify error handling with invalid inputs and missing files
    - Test CLI argument parsing with various input combinations
    - _Requirements: 5.1, 5.2, 5.4_

- [ ] 8. Package and finalize application

  - [x] 8.1 Create executable entry point

    - Set up console_scripts entry point in pyproject.toml for easy installation
    - Create standalone script that can be run directly from command line
    - Add proper shebang and executable permissions for Unix systems
    - _Requirements: 5.1_

  - [x] 8.2 Add configuration and documentation

    - Create configuration file support for default settings and preferences
    - Write README.md with installation instructions and usage examples
    - Add sample CSV format documentation and example files
    - _Requirements: 2.1, 5.1_

  - [x] 8.3 Create end-to-end integration tests
    - Test complete workflow with real CSV files and various commanders
    - Verify output file generation and content accuracy
    - Test error scenarios and recovery mechanisms
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_
