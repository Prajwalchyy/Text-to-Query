"""
Legacy F00-F17 modules, controllers, and routes archive.

Maintains backward-compatibility by ensuring the archive directory
is present in sys.path when imported, allowing flat legacy inter-module imports
(e.g., `from F00_imports import *`) to resolve properly.
"""
import sys
from pathlib import Path

LEGACY_DIR = Path(__file__).resolve().parent
if str(LEGACY_DIR) not in sys.path:
    sys.path.insert(0, str(LEGACY_DIR))

__all__ = [
    "LEGACY_DIR",
]

