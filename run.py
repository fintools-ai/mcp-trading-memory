#!/usr/bin/env python3
"""Simple runner script for the MCP Trading Memory Server."""

import sys
from pathlib import Path

# Add the current directory to Python path
current_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(current_dir))

if __name__ == "__main__":
    from src.server import main
    main()