"""
mock_api/_data_loader.py
==========================
Central JSON data loader. All mock APIs import from here.

When migrating to PostgreSQL later:
  - Delete this file
  - Each API swaps load_json() for a DB query
  - Agent code stays completely untouched
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

_BASE_DIR = Path(__file__).resolve().parent.parent / "mock_data"


@lru_cache(maxsize=None)
def load_json(filename: str) -> dict:
    """
    Load and cache a JSON file from mock_data/.
    Cached after first load so disk is only read once per filename.
    """
    path = _BASE_DIR / filename
    if not path.exists():
        raise FileNotFoundError(
            f"Mock data file not found: {path}\n"
            f"Make sure '{filename}' exists in the mock_data/ directory."
        )
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def reload_json(filename: str) -> dict:
    """Force-reload a JSON file, bypassing the cache."""
    load_json.cache_clear()
    return load_json(filename)
