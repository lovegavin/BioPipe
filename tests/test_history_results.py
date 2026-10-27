"""Historical SSH jobs use the same result UI endpoints as local/coordinated jobs."""
from copy import deepcopy
import io
from pathlib import Path
import time

from fastapi.testclient import TestClient
import numpy as np

from biopipe.remote.server import RemoteService
from src.web.api import create_app
from src.web.models import Graph
from src.web.service import Settings

ROOT = Path(__file__).resolve().parents[1]


def test_remote_history_previews_reports_figures_downloads_and_reconnect(tmp_path, monkeypatch):
    monkeypatch.setenv('BIOPIPE_ADMISSION_DIR', str(tmp_path/'remote-admission'))
    remote = RemoteService(tmp_path/'server', input_roots=[tmp_path/'server'])
    app = create_app(Settings(tmp_path/'desktop', tmp_path/'desktop'/'s', ROOT/'frontend/dist',
                              testing=True, code_root=ROOT, admission_dir=tmp_path/'local-admission'))
    manager = app.state.service.remotes
    calls = []

    class Connection:
        def __init__(self, *args):
            self.connected = True
            self.info = remote.dispatch('bootstrap', {})
        def call(self, method, params=None):
            calls.append(method)
            result = remote.dispatch(method, params or {})
            if method == 'output_file':
                # The production server is Unix. Windows loopback workers use
                # extended I/O paths, which are not part of that wire format.
                result['path'] = result['path'].removeprefix('\\\\?\\')
            return result
        def close(self): self.connected = False

    manager.factory = Connection
    profile = manager.save({'name':'Results server', 'host':'example.org', 'username':'test',
                            'app_dir':'/app', 'workspace':'/work'})
    try:
        graph = deepcopy(remote.service.demo)
        graph['memory'].update(budget_mb=64, process_limit_mb=768, keep=['clean', 'pcs'])
        graph['nodes'].append({'id':'figure', 'kind':'operator', 'operator':'heatmap',
            'position':{'x':10,'y':10}, 'params':{'dim':'sample','other_dim':'feature',
                'select':'all','cluster_rows':False,'cluster_cols':False,'filename':'history.png'}})
        graph['edges'].append({'id':'figure-edge', 'source':'quality', 'target':'figure'})
        graph = remote.dispatch('prepare', {'graph':graph})
        job = remote.service.launch(Graph.model_validate(graph))
        deadline = time.monotonic()+60
        while time.monotonic()<deadline:
            result = remote.service.details(job['id'])
            if result['status'] not in ('queued','preparing','running'): break
            time.sleep(.05)
        assert result['status']=='complete', result.get('error')
        manager.connect(profile['id'], {})
        wrapped = manager.wrap_job(profile['id'], result)
        manager.persist()
        key = wrapped['id']
        with TestClient(app) as client:
            client.headers['X-Studio-Token'] = client.get('/api/bootstrap').json()['token']
            assert any(j['id']==key for j in client.get('/api/jobs').json())
            value = client.get('/api/jobs/'+key).json()
            artifact = next(a for a in value['report']['artifacts'] if a['name']=='pcs')
            url = f"/api/jobs/{key}/artifacts/{artifact['artifact_id']}"
            calls.clear()
            preview = client.get(url+'/preview')
            assert preview.status_code==200 and len(preview.json()['rows'])==20
            assert calls==['preview']  # No raw-array download for a thumbnail/table.
            download = client.get(url+'/download')
            assert download.status_code==200, download.text
            array = np.load(io.BytesIO(download.content), allow_pickle=False)
            assert array.shape==(128,2)
            assert 'transfer_read' in calls
            calls.clear()
            assert client.get(url+'/download').content==download.content
            assert 'transfer_read' not in calls  # Verified cached output is reused.
            index = next(i for i,s in enumerate(value['summary']['steps']) if s['name']=='heatmap')
            export = f'/api/jobs/{key}/exports/{index}'
            report = client.get(export)
            assert report.status_code==200 and report.json()['filename']=='history.png'
            assert client.get(export+'/download').status_code==200
            figure = client.get(export+'/figure')
            assert figure.status_code==200 and figure.content.startswith(b'\x89PNG\r\n')
            assert {f['format'] for f in value['summary']['steps'][index]['figures']} == {'png','pdf','svg'}
            for fmt, signature, media in [('png', b'\x89PNG', 'image/png'), ('pdf', b'%PDF-', 'application/pdf'), ('svg', b'<?xml', 'image/svg+xml')]:
                opened = client.get(export+'/figure', params={'format':fmt})
                assert opened.status_code == 200 and opened.content.startswith(signature)
                assert opened.headers['content-type'].startswith(media)
                assert opened.headers['content-disposition'].startswith('inline;')
                calls.clear()
                assert client.get(export+'/figure', params={'format':fmt}).content == opened.content
                assert 'transfer_read' not in calls
            assert client.get(export+'/figure', params={'format':'exe'}).status_code == 422
            assert client.get(export+'/figure', params={'format':'tiff'}).status_code == 404
            assert client.get(f'/api/jobs/{key}/exports/999').status_code in (404,422)
            assert client.get(f'/api/jobs/{key}/artifacts/unknown/download').status_code in (404,422)
            manager.disconnect(profile['id'])
            offline = client.get(url+'/preview')
            assert offline.status_code==422 and offline.json()['code']=='remote_disconnected'
            manager.connect(profile['id'], {})
            assert client.get(url+'/preview').json()['rows']==preview.json()['rows']
    finally:
        manager.close()
        remote.handshake.close()
        remote.service.shutdown()
