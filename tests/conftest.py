"""
Root test configuration.

PYTHONPATH must be the project root so `from backend.*` resolves:
    PYTHONPATH=. pytest tests/
    # or via Makefile: make test
"""

import os
import sys

# Ensure project root is on sys.path regardless of how pytest is invoked
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
