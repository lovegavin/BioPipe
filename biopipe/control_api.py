"""Versioned application API, mounted by both desktop and headless hosts."""
from fastapi import Request
from fastapi.responses import FileResponse, Response, JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, ConfigDict, Field, model_validator
from typing import Literal

from .documents import CommandError
from .bytecode import io_path


class GraphRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    graph: dict


class ValidationRequest(GraphRequest):
    require_files: bool = False


class WorkflowRequest(GraphRequest):
    workflow_id: str | None = None
    expected_version: int | None = Field(default=None, ge=1, strict=True)


class SubmissionRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    graph: dict | None = None
    workflow_id: str | None = None
    expected_version: int | None = Field(default=None, ge=1, strict=True)
    request_id: str | None = Field(default=None, min_length=1, max_length=200)

    @model_validator(mode='after')
    def one_source(self):
        if (self.graph is not None) == bool(self.workflow_id):
            raise ValueError('Provide exactly one graph or workflow_id')
        if self.workflow_id and self.expected_version is None:
            raise ValueError('Saved workflow submission requires expected_version')
        return self


class DescribeRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    ids: list[str] = Field(min_length=1, max_length=20)
    sections: list[str] | None = Field(default=None, max_length=30)
    generation: str | None = None
    view: Literal['schema', 'docs', 'full'] = 'full'


def mount_control(app, application, bridge):
    def authorize(request, scope='context'):
        return bridge.actor(request, scope)

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request, error):
        if not request.url.path.startswith('/api/v1/'):
            from fastapi.exception_handlers import request_validation_exception_handler
            return await request_validation_exception_handler(request, error)
        details = [{'location': list(item['loc']), 'message': item['msg'], 'type': item['type']} for item in error.errors()]
        return JSONResponse({'code': 'invalid_request', 'message': 'Request does not match the application API schema',
                             'details': details}, status_code=422)

    @app.get('/api/v1/capabilities')
    def capabilities(request: Request):
        authorize(request)
        return {'api_version': 1, 'operator_protocol': 3, 'headless': bool(getattr(app.state, 'headless', False)),
                'capabilities': ['workflows', 'tasks', 'artifacts', 'operator-docs', 'canvas-sessions', 'agent-guides', 'brief-views'],
                'guides_href': '/api/v1/guides', 'openapi_href': '/api/v1/openapi.json',
                'permission_scopes': ['context', 'edit', 'run', 'plugins']}

    @app.get('/api/v1/guides')
    def guides(request: Request):
        authorize(request)
        from .guidance import guide
        return guide('index')

    @app.get('/api/v1/guides/{topic}')
    def guide_topic(topic: str, request: Request, if_sha256: str | None = None):
        authorize(request)
        from .guidance import guide
        return guide(topic, if_sha256=if_sha256)

    @app.get('/api/v1/openapi.json', include_in_schema=False)
    def api_schema(request: Request):
        authorize(request)
        from copy import deepcopy
        schema = deepcopy(app.openapi())
        schema['paths'] = {path: value for path, value in schema['paths'].items() if path.startswith('/api/v1/')}
        schema.setdefault('components', {}).setdefault('securitySchemes', {})['BioPipeToken'] = {'type': 'http', 'scheme': 'bearer'}
        schema['security'] = [{'BioPipeToken': []}]
        return schema

    @app.get('/api/v1/workflows')
    def workflows(request: Request):
        authorize(request)
        return application.workflows.list()

    @app.post('/api/v1/workflows/prepare')
    def prepare(request: Request, payload: GraphRequest):
        authorize(request)
        return application.prepare(payload.graph).model_dump(mode='json')

    @app.post('/api/v1/workflows/validate')
    def validate(request: Request, payload: ValidationRequest):
        authorize(request)
        return application.validate(payload.graph, require_files=payload.require_files)

    @app.post('/api/v1/workflows/export')
    def export(request: Request, payload: GraphRequest):
        authorize(request)
        from src.web.parameters import export_bundle
        return Response(export_bundle(application.prepare(payload.graph)), media_type='application/zip')

    @app.post('/api/v1/workflows')
    def save(request: Request, payload: WorkflowRequest):
        authorize(request, 'edit')
        return application.workflows.save(payload.graph, workflow_id=payload.workflow_id,
                                          expected_version=payload.expected_version)

    @app.get('/api/v1/workflows/{key}')
    def workflow(key: str, request: Request):
        authorize(request)
        return application.workflows.get(key)

    @app.post('/api/v1/jobs', status_code=202)
    def submit(request: Request, payload: SubmissionRequest):
        authorize(request, 'run')
        return application.jobs.submit(payload.model_dump(exclude_none=True))

    @app.get('/api/v1/jobs')
    def jobs(request: Request):
        authorize(request)
        return application.jobs.list()

    @app.get('/api/v1/jobs/{key}')
    def job(key: str, request: Request, view: Literal['brief', 'full'] = 'full'):
        authorize(request)
        from .agent_views import job_view
        return job_view(application.jobs.details(key), view)

    @app.post('/api/v1/jobs/{key}/cancel')
    def cancel(key: str, request: Request):
        authorize(request, 'run')
        return application.jobs.cancel(key)

    @app.get('/api/v1/jobs/{key}/logs')
    def logs(key: str, request: Request, offset: int = 0, limit: int = 65536,
             encoding: Literal['text', 'base64', 'both'] = 'both'):
        authorize(request)
        from .agent_views import log_view
        return log_view(application.jobs.logs(key, offset=offset, limit=limit), encoding)

    @app.get('/api/v1/jobs/{key}/parameters')
    def parameters(key: str, request: Request):
        authorize(request)
        from src.web.models import Graph
        from src.web.parameters import split_graph
        job = application.jobs.details(key)
        _, values = split_graph(Graph.model_validate(job['graph']))
        return {'job_id': key, 'values': values,
                'execution': job['graph'].get('runtime', {}).get('execution', {}),
                'memory': job['graph'].get('memory', {}), 'plugin_lock': job['graph'].get('plugin_lock', {})}

    @app.get('/api/v1/jobs/{key}/artifacts')
    def artifacts(key: str, request: Request):
        authorize(request)
        return application.artifacts.list(key)

    @app.get('/api/v1/jobs/{key}/artifacts/{artifact_id}')
    def artifact(key: str, artifact_id: str, request: Request):
        authorize(request)
        return application.artifacts.metadata(key, artifact_id)

    @app.get('/api/v1/jobs/{key}/artifacts/{artifact_id}/preview')
    def preview(key: str, artifact_id: str, request: Request, offset: int = 0, limit: int = 100):
        authorize(request)
        return application.artifacts.preview(key, artifact_id, offset=offset, limit=limit)

    @app.get('/api/v1/jobs/{key}/artifacts/{artifact_id}/table')
    def artifact_table(key: str, artifact_id: str, request: Request, offset: int = 0, limit: int = 100):
        authorize(request)
        value = application.artifacts.preview(key, artifact_id, offset=offset, limit=limit)
        return {'artifact_id': artifact_id, 'columns': value.get('columns', []), 'rows': value.get('rows', []),
                'row_labels': value.get('row_labels', []), 'total': value.get('total', 0),
                'offset': value.get('offset', offset), 'limit': value.get('limit', limit), 'descriptor': value.get('descriptor')}

    @app.get('/api/v1/jobs/{key}/artifacts/{artifact_id}/file')
    def artifact_file(key: str, artifact_id: str, request: Request, role: str | None = None):
        authorize(request)
        path = application.artifacts.file(key, artifact_id, role)
        return FileResponse(io_path(path), filename=path.name)

    @app.get('/api/v1/jobs/{key}/reports/{index}')
    def report(key: str, index: int, request: Request):
        authorize(request)
        return FileResponse(io_path(application.artifacts.report(key, index)), media_type='application/json')

    @app.get('/api/v1/jobs/{key}/reports/{index}/figure')
    def figure(key: str, index: int, request: Request, format: str | None = None, figure_id: str | None = None):
        authorize(request)
        return FileResponse(io_path(application.artifacts.figure(key, index, format, figure_id)), content_disposition_type='inline')

    @app.get('/api/v1/operators')
    def search(request: Request, query: str = '', kind: str | None = None, category: str | None = None,
               limit: int = 20, offset: int = 0, view: Literal['brief', 'full'] = 'full'):
        authorize(request)
        return application.operator_docs.search(query, kind=kind, category=category, limit=limit, offset=offset, view=view)

    @app.post('/api/v1/operators/describe')
    def describe(request: Request, payload: DescribeRequest):
        authorize(request)
        return application.operator_docs.describe(payload.ids, sections=payload.sections, generation=payload.generation, view=payload.view)

    @app.get('/api/v1/resources')
    def resources(request: Request):
        authorize(request)
        return application.executions.resources()

    @app.get('/api/v1/remotes')
    def remotes(request: Request):
        authorize(request)
        return application.service.remotes.status()

    @app.post('/api/v1/remotes')
    def save_remote(request: Request, payload: dict):
        authorize(request, 'edit')
        return application.service.remotes.save(payload)

    @app.post('/api/v1/remotes/{key}/connect')
    def connect_remote(key: str, request: Request, payload: dict):
        authorize(request, 'run')
        return application.service.remotes.connect(key, {k: str(payload[k]) for k in ('password', 'passphrase') if payload.get(k)})

    @app.post('/api/v1/remotes/{key}/trust')
    def trust_remote(key: str, request: Request, payload: dict):
        authorize(request, 'edit')
        application.service.remotes.trust(key, payload.get('fingerprint'))
        return {'trusted': True}

    @app.get('/api/v1/service')
    def status(request: Request):
        authorize(request)
        return {'instance_id': bridge.id, 'headless': bool(getattr(app.state, 'headless', False)),
                'jobs': application.jobs.list()}

    @app.post('/api/v1/service/stop')
    def stop(request: Request, payload: dict):
        authorize(request, 'run')
        if not getattr(app.state, 'headless', False):
            raise CommandError('desktop_owned', 'This service is owned by Studio; close its window to stop it', 409)
        callback = getattr(app.state, 'request_shutdown', None)
        if callback is None:
            raise CommandError('shutdown_unavailable', 'This host does not expose a shutdown callback', 409)
        with application.submission_guard:
            active = application.jobs.active_ids()
            if active:
                raise CommandError('jobs_active', 'Cancel or finish active jobs before stopping the service', 409, {'jobs': active})
            application.stopping = True
            callback()
        return {'stopping': True, 'instance_id': bridge.id}
