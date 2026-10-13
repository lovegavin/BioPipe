"""Compatibility entry point: discover and validate routes/ without fixed names.

Use `python -m biopipe registry discover --source-ref origin/main` to inspect
upstream. Route generation uses reviewed local YAML, never an implicit Git ref.
"""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from biopipe.registry import main

if __name__ == "__main__":
    raise SystemExit(main(["build", "--scope", "routes", *sys.argv[1:]]))
