"""A test-machine transfer cannot accidentally omit the forwarding instructions."""
import hashlib
import importlib.util
from pathlib import Path
import zipfile

import pytest

spec = importlib.util.spec_from_file_location('candidate_packager', Path(__file__).resolve().parents[1] / 'scripts/package_candidate.py')
packager = importlib.util.module_from_spec(spec)
spec.loader.exec_module(packager)


def fixture(tmp_path):
    root = tmp_path / 'project'
    for relative, content in {
        'pyproject.toml': '[project]\nversion="3.0.0"\n',
        'docs/OPERON_3_TEST_ACCEPTANCE.md': 'Actual double-click required.\n',
        'docs/OPERON_3_TEST_INSTRUCTIONS_ZH.md': 'Please test the candidate.\n',
        'scripts/verify_release_agent.md': 'Agent six phases.\n',
        'examples/workflows/script_pipeline/workflow.yaml': 'name: demo\n',
        'examples/workflows/script_pipeline/scale.py': 'factor = 2\n',
    }.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding='utf-8')
    setup = tmp_path / 'Operon_Setup.exe'
    setup.write_bytes(b'MZ-candidate-fixture')
    setup.with_suffix('.exe.sha256').write_text(hashlib.sha256(setup.read_bytes()).hexdigest() + '  Operon_Setup.exe\n')
    return root, setup


def test_transfer_zip_has_mandatory_instructions_and_verified_inventory(tmp_path):
    root, setup = fixture(tmp_path)
    result = packager.package_candidate(root, setup, tmp_path / 'candidate.zip', label='RC3')
    archive_path = Path(result['archive'])
    assert packager.digest(archive_path) == result['sha256']
    with zipfile.ZipFile(archive_path) as archive:
        prefix = 'Operon-3.0.0-RC3-test/'
        manifest = archive.read(prefix + 'SHA256SUMS.txt').decode()
        names = []
        for line in manifest.splitlines():
            digest, relative = line.split('  ', 1)
            assert hashlib.sha256(archive.read(prefix + relative)).hexdigest() == digest
            names.append(relative)
        assert 'FORWARD_TO_TESTER.txt' in names
        assert 'Operon_Setup.exe' in names
        assert 'script_pipeline/scale.py' in names


def test_delivery_refuses_missing_instructions_and_mismatched_setup(tmp_path):
    root, setup = fixture(tmp_path)
    setup.write_bytes(b'mismatched')
    with pytest.raises(ValueError, match='checksum'):
        packager.package_candidate(root, setup, tmp_path / 'bad.zip', label='RC3')
    (root / 'docs/OPERON_3_TEST_INSTRUCTIONS_ZH.md').unlink()
    with pytest.raises(ValueError, match='Missing acceptance material'):
        packager.package_candidate(root, setup, tmp_path / 'missing.zip', label='RC3')
    assert not (tmp_path / 'bad.zip').exists()
    assert not (tmp_path / 'missing.zip').exists()
