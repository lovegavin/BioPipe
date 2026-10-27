"""HTTP helpers for parent executions and bounded parameter-file uploads."""
import asyncio
import json
import os
from pathlib import Path
import uuid

from fastapi import HTTPException, Request
from fastapi.responses import FileResponse, PlainTextResponse, StreamingResponse

from .assets import safe_filename
from .graph import GraphError, project_path
from .models import Graph
from .service import safe_json

ACTIVE_STATUSES = {'queued', 'preparing', 'uploading', 'running', 'waiting_connection'}


def console_tail(path, job, previous=None):
    """Only the display tail is bounded; the download retains the whole file."""
    if path is not None:
        path = Path(path)
        try:
            stat = path.stat()
            signature = (stat.st_size, stat.st_mtime_ns, job['status'], job.get('error'))
            if signature == previous:
                return signature, None
            if stat.st_size:
                with path.open('rb') as stream:
                    stream.seek(max(0, stat.st_size - 65536))
                    text = stream.read(65536).decode('utf-8', errors='replace')
                return signature, {'console': text, 'console_truncated': stat.st_size > 65536}
        except FileNotFoundError:
            pass
    signature = (None, job['status'], job.get('error'))
    if signature == previous:
        return signature, None
    text = f"Status: {job['status']}\n"
    if job.get('error'):
        text += f"Recorded error: {job['error']}\n"
    return signature, {'console': text, 'console_truncated': False}


def mount_execution(app, service, executions):
    @app.post('/api/execution/plan')
    def plan(graph: Graph):
        return executions.plan(graph)

    @app.get('/api/execution/resources')
    def resources():
        return executions.resources()

    @app.post('/api/assets/reference')
    async def upload_reference(request: Request, filename: str, base_dir: str = '.'):
        # Reference/index/annotation files are not input datasets and must not
        # require a Reader declaration just to be transferred to an operator.
        name = safe_filename(filename)
        base = project_path(service.root, '.', base_dir)
        directory = service.assets_dir / uuid.uuid4().hex
        if (not service.assets_dir.resolve().is_relative_to(service.root) or
                directory.resolve().parent != service.assets_dir.resolve()):
            raise GraphError('Invalid reference upload directory')
        directory.mkdir()
        path = directory / name
        temporary = directory / ('.' + name + '.part')
        total = 0
        try:
            with temporary.open('xb') as stream:
                async for block in request.stream():
                    total += len(block)
                    if service.settings.max_upload is not None and total > service.settings.max_upload:
                        raise HTTPException(413, '文件超过本地上传上限。')
                    stream.write(block)
                stream.flush()
                os.fsync(stream.fileno())
            if not total:
                raise GraphError('上传的文件为空。')
            temporary.replace(path)
        except BaseException:
            temporary.unlink(missing_ok=True)
            # Only this fresh, owned upload directory can be removed.
            try: directory.rmdir()
            except OSError: pass
            raise
        return {'path': Path(os.path.relpath(path, base)).as_posix(), 'filename': name,
                'bytes': total, 'location': {'kind': 'local'}}

    async def events(key, request):
        executions.details(key)
        async def stream():
            offset, signature, sequence = 0, None, 0
            while not await request.is_disconnected():
                job = await asyncio.to_thread(executions.details, key)
                terminal = job['status'] not in ACTIVE_STATUSES and job.get('logs_complete', True)
                path = executions.events_path(key)
                batch, eof = [], True
                if path is not None and Path(path).is_file():
                    with Path(path).open(encoding='utf-8') as source:
                        source.seek(offset)
                        for _ in range(200):
                            previous = source.tell(); line = source.readline()
                            if not line or (not terminal and not line.endswith('\n')):
                                offset = previous
                                break
                            offset = source.tell()
                            try: batch.append(json.loads(line))
                            except json.JSONDecodeError: continue
                        else:
                            eof = False
                if 'console' in job:
                    # Orchestration may combine local and SSH child log tails.
                    # Do not replace them with the parent's control-only file.
                    text = str(job.get('console') or '')[-65536:]
                    current_signature = ('combined', text, job['status'], job.get('error'))
                    console = None if signature == current_signature else {
                        'console': text, 'console_truncated': bool(job.get('console_truncated', len(text) >= 65536))}
                    signature = current_signature
                else:
                    signature, console = console_tail(executions.console_path(key), job, signature)
                job = dict(job); job.pop('graph', None); job.pop('console', None)
                sequence += 1
                done = terminal and eof
                payload = safe_json({'job': job, 'events': batch, 'done': done, **(console or {})})
                yield f'id: {sequence}\nevent: update\ndata: {json.dumps(payload, ensure_ascii=False, allow_nan=False)}\n\n'
                if done:
                    break
                await asyncio.sleep(.4)
        return StreamingResponse(stream(), media_type='text/event-stream',
                                 headers={'X-Accel-Buffering': 'no', 'Cache-Control': 'no-cache'})

    def console(key):
        job = executions.details(key)
        path = executions.console_path(key)
        if path is not None and Path(path).is_file() and Path(path).stat().st_size:
            return FileResponse(path, media_type='text/plain', filename='console.log')
        _, snapshot = console_tail(path, job)
        return PlainTextResponse(snapshot['console'])

    return events, console
