"""Standalone source-checkout wrapper for the packaged migration tool."""
from pathlib import Path
import runpy
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from operon.format_migration import migrate
if __name__ == '__main__':
    runpy.run_module('operon.format_migration', run_name='__main__')
