"""Editor-side connection records and remote job references; no data payloads."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import threading
import uuid

from pydantic import Field, field_validator
from .models import StrictModel, Graph
from .storage import atomic_json
from .service import read_json
from .source_paths import remote_profile
from biopipe.remote.client import SSHConnection, HostKeyRequired, RemoteError


class ConnectionProfile(StrictModel):
    id: str | None = Field(default=None, pattern='^[a-f0-9]{32}$')
    name: str = Field(min_length=1, max_length=80)
    host: str = Field(min_length=1, max_length=253, pattern=r'^[A-Za-z0-9.:\[\]-]+$')
    port: int = Field(default=22, ge=1, le=65535)
    username: str = Field(min_length=1, max_length=128)
    auth: str = Field(default='password', pattern='^(password|key|agent)$')
    key_path: str = ''
    python: str = 'python3'
    app_dir: str
    workspace: str
    mode: str = Field(default='exec', pattern='^(exec|shell)$')
    menu_choice: str = Field(default='', pattern='^([0-9]{1,4})?$')

    @field_validator('username', 'key_path', 'python', 'app_dir', 'workspace')
    @classmethod
    def no_control(cls, value):
        if any(ord(char) < 32 for char in value):
            raise ValueError('Connection fields cannot contain control characters')
        return value

    @field_validator('app_dir', 'workspace')
    @classmethod
    def absolute_server_path(cls, value):
        if not PurePosixPath(value).is_absolute():
            raise ValueError('Use an absolute Linux server path')
        return value


class RemoteManager:
    def __init__(self, service, connection_factory=SSHConnection):
        self.service, self.factory = service, connection_factory
        self.directory = service.directory/'remote'; self.directory.mkdir(exist_ok=True)
        self.path = self.directory/'profiles.json'
        self.state = read_json(self.path, {'profiles': {}, 'jobs': {}, 'pending': {}})
        self.connections, self.credentials, self.pending_keys = {}, {}, {}
        self.lock = threading.RLock()

    def persist(self):
        with self.lock:
            atomic_json(self.path, self.state)
            self.path.chmod(0o600)

    def profile(self, key):
        if key not in self.state['profiles']: raise KeyError('找不到服务器连接配置。')
        return self.state['profiles'][key]

    def status(self):
        return [{'profile': {k: v for k, v in profile.items() if k != 'host_key'},
                 'fingerprint': profile.get('host_key', {}).get('fingerprint'),
                 'connected': bool(self.connections.get(key) and self.connections[key].connected),
                 'info': read_json(self.directory/(key+'.catalog.json'))}
                for key, profile in self.state['profiles'].items()]

    def save(self, value):
        with self.lock:
            profile = ConnectionProfile.model_validate(value).model_dump()
            key = profile['id'] or uuid.uuid4().hex; profile['id'] = key
            old = self.state['profiles'].get(key, {})
            if old.get('host') == profile['host'] and old.get('port') == profile['port'] and old.get('host_key'):
                profile['host_key'] = old['host_key']
            if old and profile != old:
                self.disconnect(key)
                (self.directory/(key+'.catalog.json')).unlink(missing_ok=True)
            self.state['profiles'][key] = profile; self.persist()
            return {k: v for k, v in profile.items() if k != 'host_key'}

    def trust(self, key, fingerprint):
        with self.lock:
            observed = self.pending_keys.get(key)
            if not observed or observed['fingerprint'] != fingerprint:
                raise ValueError('主机指纹已过期，请重新连接以核对。')
            self.profile(key)['host_key'] = observed
            del self.pending_keys[key]; self.persist()

    def connect(self, key, credentials):
        with self.lock:
            profile = deepcopy(self.profile(key))
            secret = credentials or self.credentials.get(key, {})
            if self.connections.get(key): self.connections.pop(key).close()
            try:
                connection = self.factory(profile, secret)
            except HostKeyRequired as exc:
                self.pending_keys[key] = exc.key
                raise
            except RemoteError: raise
            except Exception as exc:
                raise RemoteError(f'SSH 连接失败：{type(exc).__name__}。请核对主机、认证方式及远端环境。') from exc
            self.connections[key] = connection; self.credentials[key] = secret
            info = connection.info
            atomic_json(self.directory/(key+'.catalog.json'), info)
            for job in info.get('history', []): self.wrap_job(key, job)
            self.persist()
            return info

    def disconnect(self, key):
        with self.lock:
            connection = self.connections.pop(key, None)
            if connection: connection.close()
            self.credentials.pop(key, None)

    def close(self):
        for key in list(self.connections): self.disconnect(key)
        self.pending_keys.clear()

    def remove(self, key):
        with self.lock:
            self.profile(key); self.disconnect(key)
            del self.state['profiles'][key]
            self.state['jobs'] = {k:v for k,v in self.state['jobs'].items() if v['profile_id'] != key}
            (self.directory/(key+'.catalog.json')).unlink(missing_ok=True)
            self.persist()

    def call(self, key, method, params=None):
        self.profile(key)
        connection = self.connections.get(key)
        if not connection or not connection.connected:
            raise RemoteError('服务器未连接。请在服务器面板重新连接，服务器上的任务会继续运行。', code='remote_disconnected')
        return connection.call(method, params)

    def catalog(self, graph):
        key = remote_profile(graph)
        self.profile(key)
        info = read_json(self.directory/(key+'.catalog.json'))
        if not info: raise RemoteError('先连接服务器，读取服务器算子注册表。')
        return info['catalog']

    def prepare(self, graph):
        from .parameters import freeze_graph
        from .routes import prepare_interface
        catalog = self.catalog(graph)
        graph = graph.model_copy(deep=True)
        from biopipe.pins import graphs
        for part in graphs(graph):
            used = {node.operator for node in part.nodes if node.kind == 'operator'}
            # Readers are keyed by file extension; the server resolves ambiguous
            # companion formats when validating the actual server files.
            from .source_paths import source_candidates
            for node in part.nodes:
                if node.source and node.source.path:
                    used.update(r['id'] for r in source_candidates(graph, catalog, self.service.root, node.source.path))
            for descriptor in catalog['operators'] + catalog.get('readers', []):
                if descriptor['id'] in used and descriptor.get('implementation'):
                    part.plugin_lock.setdefault(descriptor['id'], deepcopy(descriptor['implementation']))
        # Saved canvas snapshots remain editable offline. Fresh server pins are
        # resolved on submission; existing pins are never silently discarded.
        return prepare_interface(freeze_graph(graph, catalog, self.service.root), catalog, self.service.root)

    def wrap_job(self, key, job):
        job = deepcopy(job)
        remote_id = job['id']; local_id = 'ssh-'+key+'-'+remote_id
        profile = self.profile(key)
        remote = {'profile_id': key, 'job_id': remote_id, 'name': profile['name'], 'workspace': profile['workspace']}
        job.update(id=local_id, remote=remote)
        self.state['jobs'][local_id] = {'profile_id': key, 'job_id': remote_id,
            'summary': {k:job[k] for k in ('id','name','status','created_at','finished_at','error','remote') if k in job}}
        return job

    def owns(self, key):
        return key.startswith('ssh-')

    def reference(self, key):
        if key not in self.state['jobs']: raise KeyError('找不到远程运行记录，请连接服务器刷新。')
        return self.state['jobs'][key]

    def launch(self, graph):
        key = remote_profile(graph)
        graph = self.prepare(graph)
        payload = graph.model_dump(mode='json')
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
        pending_key = key+':'+digest
        with self.lock:
            request_id = self.state['pending'].setdefault(pending_key, uuid.uuid4().hex)
            self.persist()
        job = self.call(key, 'run', {'graph': payload, 'request_id': request_id})
        with self.lock:
            result = self.wrap_job(key, job)
            self.state['pending'].pop(pending_key, None); self.persist()
        return result

    def job(self, key):
        ref = self.reference(key)
        result = self.wrap_job(ref['profile_id'], self.call(ref['profile_id'], 'job', {'job_id': ref['job_id']}))
        self.persist(); return result

    def cancel(self, key):
        ref = self.reference(key)
        result = self.wrap_job(ref['profile_id'], self.call(ref['profile_id'], 'cancel', {'job_id': ref['job_id']}))
        self.persist(); return result

    def poll(self, key, offsets):
        ref = self.reference(key)
        result = self.call(ref['profile_id'], 'poll', {'job_id': ref['job_id'], 'offsets': offsets})
        result['job'] = self.wrap_job(ref['profile_id'], result['job'])
        self.persist(); return result

    def history(self):
        return [item['summary'] for item in self.state['jobs'].values()]
