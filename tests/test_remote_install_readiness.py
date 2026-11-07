"""Server installation must survive unavailable optional external tools truthfully."""
import json
from types import SimpleNamespace

import pytest

from operon.remote import install_linux as installer


# Exact failures reported by the 2.2.2 server installer; no biological data.
TOOLS = {
    'amrfinder_plus': 'amrfinder', 'antismash_bgc': 'antismash',
    'assembly_stats': 'quast', 'crispr_array_detect': 'minced',
    'flye_assemble': 'flye', 'rfam_scan': 'cmscan', 'trnascan_se': 'tRNAscan-SE',
}


def tool_descriptors():
    return [{'id': key, 'resources': {'external_tools': [tool]}} for key, tool in TOOLS.items()]


def tool_results():
    return {key: {'status': 'failed', 'error': tool + ': not on PATH'} for key, tool in TOOLS.items()}


def test_new_library_tools_do_not_invalidate_base_install():
    required, unavailable = installer.split_failures(tool_results(), tool_descriptors())
    assert not required
    assert unavailable == {key: value['error'] for key, value in tool_results().items()}


def test_shared_python_failure_is_still_fatal():
    results = {**tool_results(), 'pca': {'status': 'failed', 'error': 'numpy missing'}}
    required, unavailable = installer.split_failures(results, tool_descriptors())
    assert required == {'pca': 'numpy missing'}
    assert set(unavailable) == set(TOOLS)


def test_unavailable_tool_still_blocks_workflow_placement():
    from src.web.execution_plan import descriptor_capability
    entry = tool_descriptors()[0]
    error = descriptor_capability(entry, {'system': 'linux', 'tools': {},
        'dependencies': {'entries': [{'id': entry['id'], **tool_results()[entry['id']]}]}})
    assert 'Missing executable' in error and TOOLS[entry['id']] in error


@pytest.fixture
def managed_install(tmp_path, monkeypatch):
    prefix = tmp_path / 'managed-v1' / 'env-example'
    prefix.mkdir(parents=True)
    code = tmp_path / 'code'
    code.mkdir()
    monkeypatch.setattr(installer.sys, 'prefix', str(prefix))
    monkeypatch.setattr(installer.sys, 'platform', 'linux')
    monkeypatch.setattr(installer.sys, 'argv', ['install_linux.py', '--code', str(code), '--digest', 'example'])
    monkeypatch.setattr(installer.sys, 'path', list(installer.sys.path))
    monkeypatch.setattr(installer, 'requirements', lambda code: ([], tool_descriptors()))
    monkeypatch.setattr(installer, 'ensure_requirements', lambda *args, **kwargs: None)
    monkeypatch.setattr(installer.metadata, 'distributions', lambda: [])
    monkeypatch.setattr('operon.dependencies.scope', lambda: set())
    monkeypatch.setattr('operon.dependencies.probe', lambda entries: tool_results())
    commands = []
    def run(command, **kwargs):
        commands.append(command)
        return SimpleNamespace(returncode=1 if command == ['bwa'] else 0, stdout='', stderr='')
    monkeypatch.setattr(installer.subprocess, 'run', run)
    return prefix, commands


def test_installer_finishes_and_records_unavailable_operators(managed_install, capsys):
    prefix, commands = managed_install
    installer.main()
    receipt = json.loads((prefix / 'operon-ready.json').read_text())
    states = receipt['dependency_readiness']['entries']
    assert {key: {'status': value['status'], 'error': value['error']} for key, value in states.items()} == tool_results()
    assert {command[0] for command in commands if len(command) <= 2} == {'bwa', 'samtools', 'pairtools', 'cooler', 'cooltools'}
    output = capsys.readouterr().out
    assert 'Operon and Hi-C environment ready' in output
    assert all(key in output for key in TOOLS)
    assert 'Optional OpenMM extras' not in output


def test_core_tool_failure_still_prevents_ready_receipt(managed_install, monkeypatch):
    prefix, _ = managed_install
    monkeypatch.setattr(installer.subprocess, 'run', lambda *a, **k: SimpleNamespace(returncode=99, stdout='', stderr='tool broken'))
    with pytest.raises(ValueError, match='bwa check failed'):
        installer.main()
    assert not (prefix / 'operon-ready.json').exists()


def test_empty_optional_requirements_never_invoke_pip(monkeypatch):
    monkeypatch.setattr(installer, 'EXTRA_NO_DEPS', ())
    monkeypatch.setattr(installer.subprocess, 'run', lambda *a, **k: pytest.fail('Empty pip install'))
    assert installer._ensure_isolated_extras()


def test_partial_model_install_keeps_affected_operator_failed(managed_install, monkeypatch):
    prefix, _ = managed_install
    descriptors = [{'id': 'example_model', 'resources': {'environment': 'model'}}]
    monkeypatch.setattr(installer, 'requirements', lambda code: ([], descriptors))
    monkeypatch.setattr(installer, 'ensure_requirements', lambda *a: {'model': 'package download failed'})
    monkeypatch.setattr('operon.dependencies.probe', lambda entries: {'example_model': {'status': 'passed'}})
    installer.main()
    receipt = json.loads((prefix / 'operon-ready.json').read_text())
    assert receipt['dependency_readiness']['entries']['example_model']['status'] == 'failed'


def test_requirement_repair_runs_reader_extras_and_returns_environment_failures(tmp_path, monkeypatch):
    monkeypatch.setattr(installer.subprocess, 'run', lambda *a, **k: SimpleNamespace(returncode=0))
    monkeypatch.setattr(installer, '_ensure_python_extras', lambda *a: True)
    monkeypatch.setattr(installer, '_ensure_isolated_extras', lambda: True)
    def prepare(prefix, *, failures):
        failures['model'] = 'download failed'
        return False
    monkeypatch.setattr(installer, '_ensure_isolated_environments', prepare)
    repaired = []
    monkeypatch.setattr(installer, '_ensure_conda_extras', lambda: repaired.append(True) or True)
    assert installer.ensure_requirements([], tmp_path / 'requirements.txt', prepare_library=True) == {'model': 'download failed'}
    assert repaired == [True]


def test_nested_conda_install_is_portable_and_failure_is_not_reported_ready(tmp_path, monkeypatch, capsys):
    prefix = tmp_path / 'managed-v1' / 'env-example'
    prefix.mkdir(parents=True)
    mamba = tmp_path / 'tools' / 'micromamba'
    mamba.parent.mkdir()
    mamba.write_text('fixture')
    monkeypatch.setenv('OPERON_MAMBA', str(mamba))
    monkeypatch.setenv('CONDA_PREFIX', '/unrelated/base')
    monkeypatch.setenv('MAMBA_EXE', '/unrelated/mamba')
    monkeypatch.setattr('operon.environments.load', lambda: {'model': {'conda_packages': ['native-package']}})
    monkeypatch.setattr('operon.environments.resolve', lambda name: None)
    monkeypatch.setattr('operon.environments.probe', lambda name: (True, str(prefix / 'python'), ''))
    calls = []
    def run(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(returncode=1 if 'install' in command else 0)
    monkeypatch.setattr(installer.subprocess, 'run', run)
    assert not installer._ensure_isolated_environments(prefix)
    assert len(calls) == 2
    for command, kwargs in calls:
        assert command[0] == str(mamba)
        assert '--no-rc' in command
        assert 'https://conda.anaconda.org/conda-forge' in command
        assert 'CONDA_PREFIX' not in kwargs['env']
        assert 'MAMBA_EXE' not in kwargs['env']
    assert 'model: ready' not in capsys.readouterr().out
