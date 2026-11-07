"""The display rename must not strand existing commands or canvas sessions."""
import asyncio
import importlib
from pathlib import Path
import subprocess
import sys
import tomllib
from types import SimpleNamespace

import pytest

from operon.client import Client, ClientError
from operon.documents import DocumentHub


ROOT = Path(__file__).resolve().parents[1]


def test_new_and_legacy_console_aliases_target_the_same_cli(tmp_path):
    manifest = tomllib.loads((ROOT / 'pyproject.toml').read_text(encoding='utf-8'))
    aliases = manifest['project']['scripts']
    assert aliases['operon'] == aliases['operon'] == 'operon.cli:main'
    module, function = aliases['operon'].split(':')
    assert callable(getattr(importlib.import_module(module), function))
    # The historical module invocation still handles the new advertised command surface.
    result = subprocess.run([sys.executable, '-m', 'operon', '--help'], cwd=ROOT,
                            capture_output=True, encoding='utf-8', timeout=20)
    assert result.returncode == 0 and 'usage: operon ' in result.stdout
    assert not (tmp_path / '.studio').exists()


def test_mcp_display_name_changes_without_renaming_existing_tools():
    from operon.mcp_server import create_server
    server = create_server(SimpleNamespace())
    assert server.name == 'Operon'
    names = {tool.name for tool in asyncio.run(server.list_tools())}
    assert {'operon_context', 'operon_apply', 'operon_workflow_prepare_environment', 'operon_submit'} <= names


def test_new_session_display_name_and_legacy_session_identity_coexist(tmp_path):
    service = SimpleNamespace(directory=tmp_path, routes=SimpleNamespace(save_workspace=lambda _: None))
    hub = DocumentHub(service)
    workspace = {'schema_version': 1, 'active_id': 'main', 'documents': [{'id': 'main', 'graph': {'nodes': [], 'edges': []}}]}
    old = hub.create(workspace, name='Operon Studio')
    new = hub.create(workspace)
    assert old['name'] == 'Operon Studio' and new['name'] == 'Operon'
    restored = DocumentHub(service)
    assert restored.get(old['id'])['name'] == 'Operon Studio'
    assert restored.get(new['id'])['name'] == 'Operon'
    assert old['id'] != new['id']


def test_missing_service_advertises_operon_without_changing_error_code(tmp_path, monkeypatch):
    monkeypatch.setattr('operon.client.instances', lambda _: [])
    with pytest.raises(ClientError) as failure:
        Client(tmp_path)
    assert failure.value.code == 'not_connected'
    assert 'operon serve' in str(failure.value) and 'Operon Studio' not in str(failure.value)
