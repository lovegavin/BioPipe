"""Local desktop endpoints; all remote operations travel over authenticated SSH."""
import asyncio
import base64
import json

from fastapi import Request
from fastapi.responses import JSONResponse, StreamingResponse
from biopipe.remote.client import RemoteError, HostKeyRequired
from .remote_service import RemoteManager


def mount_remote(app, service):
    manager = RemoteManager(service)
    service.remotes = manager

    @app.exception_handler(RemoteError)
    async def remote_error(request, exc):
        value = {'message': str(exc), 'code': exc.code, 'node_id': exc.node_id}
        if isinstance(exc, HostKeyRequired):
            value.update(fingerprint=exc.key['fingerprint'], changed=exc.changed)
        return JSONResponse(value, status_code=409 if exc.code == 'host_key_required' else 422)

    @app.get('/api/remote')
    def profiles():
        return manager.status()

    @app.post('/api/remote/profiles')
    def save(payload: dict):
        return manager.save(payload)

    @app.post('/api/remote/{key}/connect')
    def connect(key: str, payload: dict):
        return manager.connect(key, {k: str(payload[k]) for k in ('password', 'passphrase') if payload.get(k)})

    @app.post('/api/remote/{key}/install')
    def install(key: str, payload: dict):
        return manager.connect(key, {k: str(payload[k]) for k in ('password', 'passphrase') if payload.get(k)}, install=True)

    @app.post('/api/remote/{key}/refresh')
    def refresh(key: str, payload: dict | None = None):
        value = (payload or {}).get('verify_all', False)
        if not isinstance(value, bool):
            raise RemoteError('verify_all must be boolean')
        return manager.refresh(key, verify_all=value)

    @app.get('/api/remote/{key}/setup')
    def setup(key: str):
        return manager.setup_status(key)

    @app.post('/api/remote/{key}/trust')
    def trust(key: str, payload: dict):
        manager.trust(key, payload.get('fingerprint'))
        return {'trusted': True}

    @app.post('/api/remote/{key}/disconnect')
    def disconnect(key: str):
        manager.disconnect(key)
        return {'disconnected': True}

    @app.post('/api/remote/{key}/remove')
    def remove(key: str):
        manager.remove(key)
        return {'removed': True}

    @app.post('/api/remote/{key}/browse')
    def browse(key: str, payload: dict):
        return manager.call(key, 'browse', payload)

    @app.post('/api/remote/{key}/source')
    def source(key: str, payload: dict):
        return manager.call(key, 'source', payload)

    async def events(key, request):
        manager.reference(key)
        async def stream():
            offsets, sequence = {}, 0
            while not await request.is_disconnected():
                try:
                    payload = await asyncio.to_thread(manager.poll, key, offsets)
                    offsets = payload.pop('offsets')
                except RemoteError as exc:
                    yield 'event: remote-error\ndata: '+json.dumps({'message': str(exc)})+'\n\n'
                    # Keep the SSE alive so reconnecting SSH resumes from its cursor.
                    await asyncio.sleep(3)
                    continue
                sequence += 1
                yield f'id: {sequence}\nevent: update\ndata: {json.dumps(payload, ensure_ascii=False, allow_nan=False)}\n\n'
                if payload['done']: break
                await asyncio.sleep(1)
        return StreamingResponse(stream(), media_type='text/event-stream', headers={'X-Accel-Buffering': 'no'})

    def console(key):
        ref = manager.reference(key)
        def chunks():
            offset = 0
            while True:
                value = manager.call(ref['profile_id'], 'console', {'job_id': ref['job_id'], 'offset': offset})
                yield base64.b64decode(value['base64']) if 'base64' in value else value['text'].encode()
                offset = value['offset']
                if value['done']: break
        return StreamingResponse(chunks(), media_type='text/plain; charset=utf-8')

    return events, console
