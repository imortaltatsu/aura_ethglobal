"""Pytest configuration and shared fixtures."""
import sys
from pathlib import Path

# Ensure server directory is on path so "import tools" and "import dipcoin_swap" work
_server_dir = Path(__file__).resolve().parent.parent
if str(_server_dir) not in sys.path:
    sys.path.insert(0, str(_server_dir))
