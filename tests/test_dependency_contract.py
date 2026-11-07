"""Contract checks for declared runtime resources.

Regression guard for the hosted-install failure mode where the frontend
reported ``0/N`` dependencies while a manual probe passed: the dependency
snapshot dropped ``resources.environment`` and ``resources.external_tools``,
so ``probe`` fell back to importing a binary or the shared interpreter.
"""

from __future__ import annotations

import threading
from copy import deepcopy
from types import SimpleNamespace

import pytest

from operon import dependencies as module
from operon.dependencies import DependencySession, find_tool, probe
from operon.remote.handshake import ManifestHandshake


def descriptor(name, *, environment=None, external_tools=None, dependencies=None,
               dependency_imports=None):
    return {
        'id': name,
        'kind': 'operator',
        'title': name,
        'version': '1.0.0',
        'distribution': 'lab',
        'entry_point': 'lab:' + name,
        'dependencies': dependencies or [],
        'dependency_imports': dependency_imports or [],
        'resources': {'environment': environment, 'external_tools': external_tools or []},
        'execution': {'mode': 'shared'},
        'implementation': {'code_sha': 'sha-' + name},
    }


class Manager:
    def __init__(self, path):
        self.directory = path / 'plugins'
        self.directory.mkdir()
        self.lock = threading.RLock()
        self.value = {'packages': [{'name': 'lab'}], 'descriptors': []}

    def state(self):
        return deepcopy(self.value)

    def python_for(self, state):
        return state.get('python', 'base')

    def _publish(self, state):
        self.value = deepcopy(state)
        return state


@pytest.fixture(autouse=True)
def _full_scope(monkeypatch):
    monkeypatch.setattr(module, 'scope', lambda: set())


def test_snapshot_keeps_environment_and_external_tools(tmp_path):
    manager = Manager(tmp_path)
    manager.value['descriptors'] = [
        descriptor('env_op', environment='antifold', dependencies=['antifold']),
        descriptor('tool_op', external_tools=['foldseek']),
        descriptor('plain_op', dependencies=['numpy>=0']),
    ]
    session = DependencySession(manager)
    session.sync(manager.state())
    entries = {entry['id']: entry for entry in session.snapshot()['entries']}
    assert entries['env_op']['resources'] == {'environment': 'antifold', 'external_tools': []}
    assert entries['tool_op']['resources'] == {'environment': None, 'external_tools': ['foldseek']}
    assert entries['plain_op']['resources'] == {'environment': None, 'external_tools': []}


def test_changing_environment_invalidates_cached_pass(tmp_path):
    manager = Manager(tmp_path)
    manager.value['descriptors'] = [descriptor('env_op', environment='antifold')]
    calls = []

    def inspector(python, entries, directory):
        calls.append([entry['id'] for entry in entries])
        return {entry['id']: {'status': 'passed', 'error': ''} for entry in entries}

    session = DependencySession(manager, inspector=inspector)
    session.check(repair=False)
    assert session.snapshot()['entries'][0]['status'] == 'passed'

    manager.value['descriptors'][0]['resources']['environment'] = 'esm3'
    session.check(repair=False)
    entry = session.snapshot()['entries'][0]
    assert entry['resources']['environment'] == 'esm3'
    assert entry['status'] == 'passed'
    assert calls == [['env_op'], ['env_op']], 'the environment change must force a recheck'


def test_probe_routes_external_tools_through_find_tool(monkeypatch):
    seen = []

    def missing(name):
        seen.append(name)
        return None

    monkeypatch.setattr(module, 'find_tool', missing)
    result = probe([descriptor('tool_op', external_tools=['ghosttool'])])
    assert result['tool_op']['status'] == 'failed'
    assert 'ghosttool: not on PATH' in result['tool_op']['error']
    assert seen == ['ghosttool']

    monkeypatch.setattr(module, 'find_tool', lambda name: '/opt/bin/' + name)
    result = probe([descriptor('tool_op', external_tools=['ghosttool'])])
    assert result['tool_op']['status'] == 'passed'


def test_probe_routes_environment_through_isolated_interpreter(monkeypatch):
    calls = []

    def fake(entry_id, environment, imports):
        calls.append((entry_id, environment, tuple(imports)))
        return {'status': 'passed', 'error': ''}

    monkeypatch.setattr(module, 'probe_environment', fake)
    entry = descriptor('env_op', environment='antifold', dependency_imports=['antifold', 'torch'])
    assert probe([entry])['env_op']['status'] == 'passed'
    assert calls == [('env_op', 'antifold', ('antifold', 'torch'))]


def test_find_tool_falls_back_to_managed_environment_bins(tmp_path, monkeypatch):
    managed = tmp_path / 'managed'
    env_bin = managed / 'env-abc123' / 'bin'
    env_bin.mkdir(parents=True)
    tool = env_bin / 'ghosttool'
    tool.write_text('#!/bin/sh\nexit 0\n', encoding='utf-8')
    tool.chmod(0o755)

    monkeypatch.setattr('shutil.which', lambda name: None)
    monkeypatch.setattr('sys.prefix', str(managed / 'current'))
    assert find_tool('ghosttool') == str(tool)
