"""Viewer discovery, retained-path boundaries, launch arguments and API scopes."""
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from operon import viewers as module
from operon.documents import CommandError


@pytest.fixture
def service(tmp_path, monkeypatch):
    monkeypatch.setattr(module, 'system', lambda: 'windows')
    monkeypatch.setattr(module, 'discover', lambda commands: None)
    # Function has a cache reset API used by explicit refresh/configuration.
    module.discover.cache_clear = lambda: None
    files = {}
    def preview(*args, **kwargs):
        return {'files': [{'role': role, 'name': path.name, 'bytes': path.stat().st_size, 'downloadable': True}
                          for role, path in files.items()]}
    app = SimpleNamespace(service=SimpleNamespace(directory=tmp_path / 'profile'),
                          artifacts=SimpleNamespace(preview=preview, file=lambda j, a, r: files[r]))
    return module.ViewerService(app), files


def test_catalog_discovery_and_profile_persistence(service, tmp_path):
    viewer, _ = service
    assert len(viewer.listing()['viewers']) == 29
    exe = tmp_path / 'installed app.exe'; exe.write_bytes(b'test')
    viewer.configure('igv', str(exe))
    fresh = module.ViewerService(viewer.app)
    entry = next(v for v in fresh.listing()['viewers'] if v['id'] == 'igv')
    assert entry['available'] and entry['executable'] == str(exe)
    viewer.configure('igv', None)
    assert 'igv' not in viewer.settings()


@pytest.mark.parametrize('bad', ['relative.exe', 'https://example.org/app.exe', '../app.exe', 'cmd.exe /c echo secret'])
def test_configure_does_not_accept_command_strings(service, bad):
    with pytest.raises(ValueError):
        service[0].configure('igv', bad)


def test_reject_scripts_and_nonregistered_viewers(service, tmp_path):
    path = tmp_path / 'app.cmd'; path.write_text('echo unsafe')
    with pytest.raises(ValueError, match='shell'):
        service[0].configure('igv', str(path))
    with pytest.raises(ValueError, match='registered'):
        service[0].configure('invented', str(path))


def test_options_are_lazy_and_filter_files(service, tmp_path):
    viewer, files = service
    files['contact'] = tmp_path / 'test.hic'; files['contact'].write_bytes(b'HIC')
    viewer.app.artifacts.file = lambda *args: pytest.fail('listing must not transfer an output')
    result = viewer.options('job', 'artifact', 'contact')
    assert [v['id'] for v in result['viewers']] == ['juicebox', 'juicebox-web']
    with pytest.raises(CommandError, match='retained'):
        viewer.options('job', 'artifact', 'missing')


def test_prepare_preserves_remote_indexes_and_reuses_cache(service, tmp_path, monkeypatch):
    viewer, files = service
    for folder, role, name in [('a', 'data', 'reads.bam'), ('b', 'index', 'reads.bam.bai'), ('c', 'other', 'huge.bam')]:
        p = tmp_path / folder / name; p.parent.mkdir(); p.write_bytes(role.encode()); files[role] = p
    original = viewer.app.artifacts.file
    fetched = []
    viewer.app.artifacts.file = lambda j, a, r: (fetched.append(r), original(j, a, r))[1]
    output = viewer.prepare('job', 'artifact', 'data')
    main = Path(output['path'])
    assert main.name == 'reads.bam' and main.with_name('reads.bam.bai').read_bytes() == b'index'
    assert fetched == ['data', 'index']
    monkeypatch.setattr(module.shutil, 'copyfile', lambda *args: pytest.fail('unchanged transferred files must be reused'))
    assert viewer.prepare('job', 'artifact', 'data')['path'] == output['path']


def test_launch_preserves_argument_boundaries_and_manual_mode(service, tmp_path, monkeypatch):
    viewer, files = service
    p = tmp_path / 'a b & sample.bed'; p.write_bytes(b'chr1\t0\t10\n'); files['data'] = p
    exe = tmp_path / 'IGV.exe'; exe.write_bytes(b'test'); viewer.configure('igv', str(exe))
    calls = []
    class Process:
        pid = 123
        def wait(self): return 0
    monkeypatch.setattr(module.subprocess, 'Popen', lambda args, **kwargs: (calls.append((args, kwargs)), Process())[1])
    result = viewer.open('job', 'artifact', 'data', 'igv')
    assert result['status'] == 'started' and result['mode'] == 'file'
    assert calls[0][0] == [str(exe), str(p)] and calls[0][1]['shell'] is False
    assert calls[0][1]['stdout'] is not module.subprocess.PIPE
    with pytest.raises(ValueError, match='compatible'):
        viewer.open('job', 'artifact', 'data', 'pymol')
    hic = tmp_path / 'result.hic'; hic.write_bytes(b'HIC'); files['data'] = hic
    viewer.configure('juicebox', str(exe))
    result = viewer.open('job', 'artifact', 'data', 'juicebox')
    assert calls[-1][0] == [str(exe)] and result['mode'] == 'manual'
    assert result['path'] == str(hic)


def test_custom_catalog_validation(service, tmp_path):
    viewer, _ = service
    entry = deepcopy(viewer.catalog()['igv']); entry.update(id='custom-igv', name='Lab IGV')
    viewer.directory.mkdir(parents=True)
    path = viewer.directory / 'catalog.json'
    path.write_text(json.dumps({'schema_version': 1, 'viewers': [entry]}))
    assert 'custom-igv' in viewer.catalog()
    entry['extensions'] = ['.py']
    path.write_text(json.dumps({'schema_version': 1, 'viewers': [entry]}))
    with pytest.raises(ValueError, match='Executable'):
        viewer.catalog()


def test_open_and_configuration_require_execution_permission(tmp_path, monkeypatch):
    from src.web.service import Settings
    from operon.headless import create_headless_app
    monkeypatch.setenv('OPERON_REGISTRY_MAINTENANCE', '1')
    app = create_headless_app(Settings(tmp_path, tmp_path / 'profile', tmp_path / 'no-ui', testing=True,
                                       code_root=Path(__file__).resolve().parents[1]))
    app.state.application.viewers.prepare = lambda *args: {'path': 'prepared'}
    app.state.application.viewers.open = lambda j, a, r, v: {'viewer': v, 'role': r}
    with TestClient(app, base_url='http://127.0.0.1') as client:
        def auth(scopes):
            r = client.post('/api/agent/connect', headers={'X-Operon-Bridge': app.state.bridge.secret}, json={'name': 'viewer-test', 'scopes': scopes})
            return {'Authorization': 'Bearer ' + r.json()['token']}
        read, run = auth(['context']), auth(['context', 'run'])
        assert client.get('/api/v1/viewers').status_code == 403
        assert client.get('/api/v1/viewers', headers=read).status_code == 200
        assert client.post('/api/v1/viewers/igv/configure', headers=read, json={}).status_code == 403
        assert client.post('/api/v1/viewers/default', headers=read, json={'extension': '.bed', 'viewer': 'igv'}).status_code == 403
        saved = client.post('/api/v1/viewers/default', headers=run, json={'extension': '.bed', 'viewer': 'igv'})
        assert saved.status_code == 200 and saved.json()['defaults'] == {'.bed': 'igv'}
        assert client.get('/api/v1/viewers', headers=read).json()['defaults'] == {'.bed': 'igv'}
        prefix = '/api/v1/jobs/j/artifacts/a'
        assert client.post(prefix + '/open-viewer', headers=read, json={'viewer': 'igv', 'role': 'data'}).status_code == 403
        assert client.post(prefix + '/open-viewer', headers=run, json={'role': 'data'}).json() == {'viewer': None, 'role': 'data'}
        assert client.post(prefix + '/prepare-viewer', headers=read, json={'role': 'data'}).status_code == 403
        assert client.post(prefix + '/prepare-viewer', headers=run, json={'role': 'data'}).json() == {'path': 'prepared'}
        assert client.post(prefix + '/prepare-viewer', headers=run, json={'role': 'data', 'path': 'untrusted'}).status_code == 422


def test_default_survives_restart_without_changing_program_paths(service, tmp_path, monkeypatch):
    viewer, files = service
    exe = tmp_path / 'IGV.exe'; exe.write_bytes(b'test')
    viewer.configure('igv', str(exe)); viewer.set_default('.bed', 'igv')
    p = tmp_path / 'reads.BED'; p.write_bytes(b'chr1\t0\t10'); files['data'] = p
    fresh = module.ViewerService(viewer.app)
    assert fresh.settings() == {'igv': str(exe)}
    assert fresh.options('j', 'a', 'data')['default_viewer'] == 'igv'
    calls = []
    class Process:
        pid = 123
        def wait(self): return 0
    monkeypatch.setattr(module.subprocess, 'Popen', lambda args, **kw: (calls.append(args), Process())[1])
    assert fresh.open('j', 'a', 'data')['status'] == 'started'
    assert calls == [[str(exe), str(p)]]
    fresh.set_default('.bed', None)
    assert fresh.defaults() == {} and fresh.settings() == viewer.settings()
    assert fresh.options('j', 'a', 'data')['default_source'] == 'automatic'


@pytest.mark.parametrize(('suffix', 'viewer'), [('.bed', 'pymol'), ('.hic', 'juicebox-web'), ('.exe', 'igv'), ('.bed', 'unknown')])
def test_default_requires_compatible_desktop_format(service, suffix, viewer):
    with pytest.raises(ValueError):
        service[0].set_default(suffix, viewer)
    assert service[0].defaults() == {}


def test_unavailable_default_never_silently_launches_another_viewer(service, tmp_path, monkeypatch):
    viewer, files = service
    path = tmp_path / 'reads.bed'; path.write_bytes(b'chr1'); files['data'] = path
    viewer.set_default('.bed', 'igv')
    monkeypatch.setattr(module.subprocess, 'Popen', lambda *a, **kw: pytest.fail('must not launch a fallback'))
    with pytest.raises(CommandError, match='Configure'):
        viewer.open('j', 'a', 'data')
    # A removed custom entry remains visible as an unavailable preference.
    viewer.user_config.update(lambda config: config['viewers'].update(defaults={'.bed': 'removed-app', '.custom': 'removed-app'}))
    with pytest.raises(CommandError, match='Settings'):
        viewer.open('j', 'a', 'data')
    viewer.set_default('.custom', None)
    assert '.custom' not in viewer.defaults()


def test_default_uses_longest_suffix_and_does_not_fetch_outputs(service, tmp_path):
    viewer, files = service
    entry = deepcopy(viewer.catalog()['igv']); entry.update(id='generic-gz', extensions=['.gz'])
    viewer.directory.mkdir(parents=True)
    (viewer.directory / 'catalog.json').write_text(json.dumps({'schema_version': 1, 'viewers': [entry]}))
    viewer.set_default('.gz', 'generic-gz'); viewer.set_default('.vcf.gz', 'igv')
    p = tmp_path / 'reads.vcf.gz'; p.write_bytes(b'test'); files['data'] = p
    viewer.app.artifacts.file = lambda *args: pytest.fail('preferences must not fetch files')
    assert viewer.options('j', 'a', 'data')['default_viewer'] == 'igv'


def test_cli_exposes_viewer_actions():
    from operon.cli import parser
    assert parser().parse_args(['viewers', 'list', '--refresh']).refresh
    args = parser().parse_args(['artifacts', 'open', 'job', 'artifact', '--role', 'data', '--viewer', 'igv'])
    assert args.viewer == 'igv' and args.role == 'data'
    args = parser().parse_args(['viewers', 'default', '.bed', '--viewer', 'igv'])
    assert args.action == 'default' and args.id == '.bed' and args.viewer == 'igv'
    assert parser().parse_args(['artifacts', 'open', 'job', 'artifact', '--role', 'data']).viewer is None


def test_mcp_viewer_uses_shared_api_and_escapes_ids():
    import asyncio
    from operon.mcp_server import create_server
    calls = []
    client = SimpleNamespace(request=lambda *args: (calls.append(args), {'ok': True})[1])
    server = create_server(client)
    asyncio.run(server.call_tool('operon_viewer', {'job_id': 'j/a', 'artifact_id': 'a b', 'role': 'data'}))
    assert calls[-1] == ('/v1/jobs/j%2Fa/artifacts/a%20b/viewers?role=data',)
    asyncio.run(server.call_tool('operon_viewer', {'job_id': 'job', 'artifact_id': 'artifact', 'role': 'data', 'viewer': 'igv'}))
    assert calls[-1] == ('/v1/jobs/job/artifacts/artifact/open-viewer', {'role': 'data', 'viewer': 'igv'})
