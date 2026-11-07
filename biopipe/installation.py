"""Setup identity shared by desktop, CLI and headless profile resolution."""
import json
import os
from pathlib import Path
import re
import sys


def isolated_root(code_root):
    root = Path(code_root).resolve()
    if (root / 'biopipe-install.json').is_file():
        return root
    executable = Path(sys.executable).resolve()
    if len(executable.parents) >= 3 and executable.parent.name == 'python' and executable.parent.parent.name == 'runtime':
        candidate = executable.parents[2]
        if root.is_relative_to(candidate) and (candidate / 'biopipe-install.json').is_file():
            return candidate
    return None


def profile_id(root):
    value = json.loads((Path(root) / 'biopipe-install.json').read_text(encoding='utf-8'))
    if (value.get('schema_version') != 1 or value.get('isolated') is not True or
            not re.fullmatch(r'[a-f0-9]{32}', str(value.get('profile_id', '')))):
        raise ValueError('Invalid isolated installation identity; rerun Operon Setup.')
    return value['profile_id']


def profile_namespace(root):
    """New branded installs cannot attach to an older product's profile."""
    profile_id(root)
    value = json.loads((Path(root) / 'biopipe-install.json').read_text(encoding='utf-8'))
    product = value.get('product', 'biopipe')
    if not isinstance(product, str) or product not in {'operon', 'biopipe'}:
        raise ValueError('Unknown installation product; rerun Operon Setup.')
    return '.' + product


def configure_environment(code_root):
    """Also isolate direct CLI/MCP starts, which do not pass through the EXE."""
    root = isolated_root(code_root)
    if root is None:
        return
    profile_namespace(root)  # Reject an invalid identity/product before changing the environment.
    for key in list(os.environ):
        upper = key.upper()
        if upper.startswith(('BIOPIPE_', 'PYTHON', 'CONDA')) or upper in {
            'VIRTUAL_ENV', 'R_HOME', 'R_LIBS', 'R_LIBS_USER', 'R_PROFILE', 'R_ENVIRON',
            'PIP_TARGET', 'PIP_PREFIX', 'PIP_USER', 'PIP_REQUIRE_VIRTUALENV'}:
            del os.environ[key]
    python = root / 'runtime/python'
    windows = Path(os.environ.get('SystemRoot', str(Path(sys.executable).anchor)))
    os.environ['PATH'] = os.pathsep.join(map(str, (python, python / 'Scripts', windows / 'System32', windows)))
    os.environ['PYTHONNOUSERSITE'] = '1'
    os.environ['PIP_CONFIG_FILE'] = os.devnull
