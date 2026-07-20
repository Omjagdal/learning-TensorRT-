"""
conftest.py — Add backend/ to sys.path so tests can import app modules.
"""

import sys
from pathlib import Path

# Add the backend directory to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))
