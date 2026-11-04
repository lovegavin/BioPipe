"""Catalog validation must not import optional analysis stacks."""
import os
from pathlib import Path
import subprocess
import sys


def test_new_model_and_chemistry_classes_import_without_optional_stacks():
    modules = ['esm_embedding_autoencoder', 'rdkit_atom_environment_histogram',
               'rdkit_charge_profile', 'rdkit_fragment_profile',
               'rdkit_reaction_smarts_apply', 'vhh_humanization_score']
    script = '''
import builtins, importlib
original = builtins.__import__
def guarded(name, *args, **kwargs):
    if name.split('.')[0] in {'torch', 'rdkit', 'Bio'}:
        raise AssertionError('Eager optional import: ' + name)
    return original(name, *args, **kwargs)
builtins.__import__ = guarded
for name in MODULES:
    importlib.import_module('src.task.step.steps.' + name)
'''.replace('MODULES', repr(modules))
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run([sys.executable, '-c', script], cwd=root,
                            env={**os.environ, 'PYTHONPATH': str(root)},
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
