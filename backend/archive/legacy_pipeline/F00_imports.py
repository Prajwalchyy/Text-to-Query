# ==============================================================================
# Central Project Imports & Path Setup (F00)
# ==============================================================================

# Standard Library Imports
import os
import re
import sys
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

# Third-Party Frameworks & Tooling
import sqlalchemy as db
import sqlglot
from sqlglot import exp
from dotenv import load_dotenv
from openai import OpenAI

# ------------------------------------------------------------------------------
# Project Root Resolution & sys.path Setup
# ------------------------------------------------------------------------------
# SRC_DIR is Text_to_sql/backend/src
SRC_DIR = Path(__file__).resolve().parent
# PROJECT_ROOT is Text_to_sql/backend
PROJECT_ROOT = SRC_DIR.parent

# Ensure both backend/src and backend/ are in sys.path
for path_dir in [str(SRC_DIR), str(PROJECT_ROOT)]:
    if path_dir not in sys.path:
        sys.path.insert(0, path_dir)

# Load configuration secrets from backend/.env
load_dotenv(PROJECT_ROOT / ".env")
