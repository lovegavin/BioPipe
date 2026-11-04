"""Release errors must be caught before building/publishing an operator update."""
import json
from pathlib import Path
import runpy
import subprocess
import sys

import pytest

HELPER = runpy.run_path(str(Path(__file__).resolve().parents[1] / 'scripts/release_library.py'))


def test_library_version_and_tag_are_independent_of_application(tmp_path):
    (tmp_path / 'library').mkdir()
    config = {'version': '2026.11.4', 'minimum_application': '2.0.4', 'build_application': '2.0.4'}
    file = tmp_path / 'library/release.json'
    file.write_text(json.dumps(config), encoding='utf-8')
    assert HELPER['configuration'](tmp_path, 'library-v2026.11.4') == config
    with pytest.raises(ValueError, match='tag differs'):
        HELPER['configuration'](tmp_path, 'v2.0.4')
    config['build_application'] = '2.2.2'
    file.write_text(json.dumps(config), encoding='utf-8')
    with pytest.raises(ValueError, match='minimum supported'):
        HELPER['configuration'](tmp_path)


def test_checkout_cannot_impersonate_released_application(tmp_path, monkeypatch):
    import biopipe
    monkeypatch.setattr(biopipe, '__file__', str(tmp_path / 'biopipe/__init__.py'))
    with pytest.raises(ValueError, match='source checkout|python -I'):
        HELPER['released_application'](tmp_path, {'build_application': biopipe.__version__})


def test_wrong_released_application_is_rejected(tmp_path):
    with pytest.raises(ValueError, match='Expected released|python -I'):
        HELPER['released_application'](tmp_path, {'build_application': '0.0.0'})


@pytest.mark.parametrize('name,dependency', [('esm_embedding_autoencoder', 'torch'), ('vhh_humanization_score', 'Bio')])
def test_optional_dependencies_are_not_imported_during_registration(name, dependency):
    source = Path(__file__).resolve().parents[1] / 'src/task/step/steps' / (name + '.py')
    code = "import runpy,sys; sys.modules[sys.argv[1]]=None; runpy.run_path(sys.argv[2])"
    subprocess.run([sys.executable, '-I', '-c', code, dependency, str(source)], check=True)
