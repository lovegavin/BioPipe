# src/version.py
"""Single source of truth for the BioPipe version string.

Every module that reports a version — the manifest default, the
pipeline class, run metadata, the package itself — imports from here.
Bumping the version is a one-line edit.
"""

from __future__ import annotations

__version__ = "0.1.0"

__all__ = ["__version__"]