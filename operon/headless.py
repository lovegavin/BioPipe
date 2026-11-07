"""Headless loopback application host and per-profile detached lifecycle."""
from contextlib import asynccontextmanager
from dataclasses import replace
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import time
from urllib.parse import urlparse

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from operon import __version__
from .application import Application
from .bridge import Bridge
from .control_api import mount_control
from src.web.storage import FileLock


def create_headless_app(settings):
    settings = replace(settings, manifest_only_registry=True)
    application = Application(settings)
    service = application.service

    @asynccontextmanager
    async def lifespan(app):
        bridge.publish(getattr(app.state, 'instance_url', None) or settings.instance_url)
        try:
            yield
        finally:
            bridge.close()
            application.shutdown()

    app = FastAPI(title='Operon application service', version=__version__, lifespan=lifespan,
                  docs_url=None, redoc_url=None, openapi_url=None)
    app.state.headless = True
    app.state.application, app.state.service = application, service
    app.state.executions = application.executions
    bridge = Bridge(app, service, secrets.token_urlsafe(32))
    app.state.bridge = bridge
    mount_control(app, application, bridge)

    @app.middleware('http')
    async def boundary(request, call_next):
        host = request.url.hostname
        origin = request.headers.get('origin')
        if host not in ('127.0.0.1', 'localhost') or (origin and urlparse(origin).hostname not in ('127.0.0.1', 'localhost')):
            return JSONResponse({'code': 'local_only', 'message': 'The application service accepts loopback clients only'}, status_code=403)
        service.refresh_catalog()
        response = await call_next(request)
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        return response

    @app.exception_handler(KeyError)
    async def missing(request, error):
        return JSONResponse({'code': 'not_found', 'message': str(error).strip("'")}, status_code=404)

    @app.exception_handler(ValueError)
    async def invalid(request, error):
        return JSONResponse({'code': getattr(error, 'code', 'invalid_request'), 'message': str(error),
                             'details': getattr(error, 'details', None)}, status_code=422)

    from operon.remote.client import RemoteError, HostKeyRequired
    @app.exception_handler(RemoteError)
    async def remote_error(request, error):
        payload = {'code': error.code, 'message': str(error)}
        if isinstance(error, HostKeyRequired):
            payload.update(fingerprint=error.key['fingerprint'], changed=error.changed)
        return JSONResponse(payload, status_code=409 if error.code == 'host_key_required' else 422)

    @app.get('/health')
    def health(request: Request):
        bridge.actor(request, 'context')
        return {'status': 'ok', 'version': __version__, 'headless': True}

    return app


def serve(*, profile_dir=None, workspace=None, data_dir=None, port=0):
    import uvicorn
    from src.web.profile import make_settings
    root = Path(__file__).resolve().parents[1]
    os.environ['OPERON_REGISTRY_MAINTENANCE'] = '1'
    settings = make_settings(root, root / 'frontend/dist', profile_dir=profile_dir, workspace=workspace, data_dir=data_dir)
    if not 0 <= port <= 65535:
        raise ValueError('port must be between 0 and 65535')
    # Lifetime OS lock, separate from the short client-side startup lock. A
    # crash releases it; concurrent clients cannot leave competing daemons.
    with FileLock(settings.data_dir / 'agent/.headless-owner.lock', timeout=1):
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', port))
            settings.instance_url = f'http://127.0.0.1:{sock.getsockname()[1]}'
            app = create_headless_app(settings)
            server = uvicorn.Server(uvicorn.Config(app, log_level='warning', access_log=False))
            app.state.request_shutdown = lambda: setattr(server, 'should_exit', True)
            server.run(sockets=[sock])


def ensure_service(directory, *, workspace=None, require_api=1):
    from .client import instances, ClientError
    directory = Path(directory).resolve()
    with FileLock(directory / 'agent/.start.lock', timeout=120):
        available = [v for v in instances(directory) if v.get('api_version', 0) >= require_api]
        if available:
            return available
        root = Path(__file__).resolve().parents[1]
        log = directory / 'service.log'
        log.parent.mkdir(parents=True, exist_ok=True)
        env = dict(os.environ, PYTHONIOENCODING='utf-8', PYTHONUTF8='1', PYTHONUNBUFFERED='1', OPERON_REGISTRY_MAINTENANCE='1')
        env['PYTHONPATH'] = os.pathsep.join([str(root), env.get('PYTHONPATH', '')])
        # The selected data directory always lives below its workspace. Use its
        # parent as the default isolated workspace; normal profiles use .studio.
        command = [sys.executable, '-m', 'operon', '--workspace', str(Path(workspace).resolve() if workspace else directory.parent), '--data-dir', str(directory), 'serve']
        with log.open('ab') as output:
            process = subprocess.Popen(command, cwd=root, env=env, stdin=subprocess.DEVNULL,
                                       stdout=output, stderr=subprocess.STDOUT,
                                       creationflags=(subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW) if os.name == 'nt' else 0,
                                       start_new_session=os.name != 'nt')
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            available = [v for v in instances(directory) if v.get('api_version', 0) >= require_api]
            if available:
                return available
            if process.poll() is not None:
                raise ClientError(f'Operon service exited during startup. See {log}', 'service_start_failed')
            time.sleep(.2)
        raise ClientError(f'Operon service is still starting. See {log}; retry service status.', 'service_start_timeout')
