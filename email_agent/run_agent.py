#!/usr/bin/env python3
"""
CLI runner for EPCIS Error Correction Agent
Simple script to run common agent operations
"""

import asyncio
import sys
from pathlib import Path
from main import main

# Add the project root to Python path
sys.path.append(str(Path(__file__).parent))

if __name__ == "__main__":
    main()
