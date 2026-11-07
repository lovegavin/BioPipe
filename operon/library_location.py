"""Locate the optional, independently shipped reference library without imports.

The relative layout inside a seed is stable so v3 source hashes, entry points and
offline provider bundles remain portable. No operator code runs during discovery.
"""
import importlib.util
from pathlib import Path

INDEX = Path('operon/builtin_packages.json')


def source_root(root=None):
    if root is not None:
        root = Path(root).resolve()
        nested = root / 'library/seed'
        return nested if (nested / 'src/task/step/steps').is_dir() else root
    checkout = Path(__file__).resolve().parents[1] / 'library/seed'
    if (checkout / 'src/task/step/steps').is_dir():
        return checkout
    spec = importlib.util.find_spec('operon_builtin_library')
    if spec and spec.submodule_search_locations:
        installed = Path(next(iter(spec.submodule_search_locations)))
        if (installed / 'src/task/step/steps').is_dir():
            return installed
    return None


def asset_path(relative):
    root = source_root()
    return (root if root is not None else Path(__file__).parent / '_no_library') / relative


def implementation_paths(relative):
    root = source_root()
    return [str(root / relative)] if root is not None else []
