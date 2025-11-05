#!/usr/bin/env python3
"""
Main entry point script for MTG Commander Deck Builder.

This script can be run directly from the command line to build Commander decks
from your card collection CSV file.
"""

import sys
import os
from pathlib import Path

# Add the project directory to Python path
project_dir = Path(__file__).parent
sys.path.insert(0, str(project_dir))

# Check if we're in a virtual environment, if not, try to activate it
if not hasattr(sys, 'real_prefix') and not (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
    venv_path = project_dir / '.venv'
    if venv_path.exists():
        # Try to use the virtual environment's Python
        venv_python = venv_path / 'bin' / 'python'
        if venv_python.exists():
            import subprocess
            # Re-run this script with the virtual environment's Python
            result = subprocess.run([str(venv_python), __file__] + sys.argv[1:])
            sys.exit(result.returncode)

from mtg_deck_builder.cli import main

if __name__ == "__main__":
    main()