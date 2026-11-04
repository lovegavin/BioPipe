"""Stable import namespace for the optional, separately installed library."""
from biopipe.library_location import implementation_paths

__path__ = implementation_paths('src/reader/readers')
