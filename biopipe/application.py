"""Transport-independent application services shared by Studio, CLI and MCP.

The scientific worker, host admission ledger, streaming store and SSH execution
coordinator remain the single execution implementation. No canvas is required.
"""
from datetime import datetime, timezone
import base64
import hashlib
import json
from pathlib import Path
import threading
import uuid
from urllib.parse import urlencode

from .documents import CommandError, layout
from src.web.models import Graph, SaveWorkflow
from src.web.storage import FileLock, atomic_json
from src.web.service import JobService, read_json

ACTIVE = {'queued', 'preparing', 'uploading', 'running', 'waiting_connection'}


class Application:
    """Profile-scoped composition root; adapters do not own scientific state."""
    def __init__(self, settings, catalog=None):
        from src.web.operator_catalog import catalog_from_descriptors
        from src.web.remote_service import RemoteManager
        from src.web.execution import ExecutionService
        self.service = JobService(settings, catalog or catalog_from_descriptors())
        self.service.application = self
        self.service.remotes = RemoteManager(self.service)
        self.executions = self.service.executions = ExecutionService(self.service)
        self.service.routes.catalog_for = self.catalog_for
        self.requests = self.service.directory / 'submissions'
        self.requests.mkdir(exist_ok=True)
        self.submission_guard = threading.RLock()
        self.stopping = False
        self.workflows = WorkflowService(self)
        self.jobs = TaskService(self)
        self.artifacts = ArtifactService(self)
        from .operator_docs import OperatorDocs
        self.operator_docs = OperatorDocs(self.service.plugins)

    def catalog_for(self, graph):
        return self.executions.catalog(graph) if self.executions.applies(graph) else self.service.graph_catalog(graph)

    def prepare(self, graph):
        graph = Graph.model_validate(layout(graph)) if isinstance(graph, dict) else graph
        return self.executions.prepare(graph) if self.executions.applies(graph) else self.service.prepare_graph(graph)

    def validate(self, graph, *, require_files=False):
        graph = Graph.model_validate(layout(graph)) if isinstance(graph, dict) else graph
        result = (self.executions.validate(graph, require_files=require_files) if self.executions.applies(graph)
                  else self.service.validate_graph(graph, require_files=require_files))
        return {**result, 'graph': graph.model_dump(mode='json')}

    def shutdown(self):
        self.executions.shutdown()
        self.service.shutdown()


class WorkflowService:
    def __init__(self, application):
        self.app = application
        self.library = application.service.routes

    def list(self):
        return self.library.list_saved()

    def get(self, key):
        return self.library.get(key)

    def save(self, graph, *, workflow_id=None, expected_version=None):
        # Use the same lock and version check as the desktop's saved routes.
        with self.library.lock:
            if workflow_id:
                previous = self.get(workflow_id)
                if previous['version'] != expected_version:
                    raise CommandError('revision_conflict', 'Workflow changed before save', 409,
                                       {'expected_version': expected_version, 'actual_version': previous['version']})
            prepared = self.app.prepare(graph)
            return self.library.save(SaveWorkflow(id=workflow_id, expected_version=expected_version, graph=prepared))

    def graph(self, payload):
        if ('graph' in payload) == bool(payload.get('workflow_id')):
            raise CommandError('invalid_request', 'Provide exactly one of graph or workflow_id')
        if payload.get('workflow_id'):
            item = self.get(payload['workflow_id'])
            if payload.get('expected_version') != item['version']:
                raise CommandError('revision_conflict', 'Workflow changed before submission', 409,
                                   {'actual_version': item['version']})
            return item['graph']
        return payload['graph']


class TaskService:
    def __init__(self, application):
        self.app = application
        self.service = application.service

    def backend(self, key):
        if self.app.executions.owns(key):
            return self.app.executions
        if self.service.remotes.owns(key):
            return self.service.remotes
        return self.service

    def details(self, key):
        backend = self.backend(key)
        return backend.job(key) if backend is self.service.remotes else backend.details(key)

    def list(self):
        parents = self.app.executions.history()
        child_ids = {child.get('id') or child.get('job_id') for job in parents for child in job.get('children', [])}
        # Refresh using the existing worker lifecycle, then expose all records.
        # The desktop history's 60-row presentation limit is not an API limit.
        self.service.history()
        with self.service.lock:
            local = [{**{k: value.get(k) for k in ('id', 'name', 'status', 'created_at', 'finished_at', 'error')},
                      'progress': self.service._progress(value), 'allocation': value.get('allocation'),
                      'execution_parent_id': value.get('graph', {}).get('runtime', {}).get('execution_parent_id'),
                      'queued_reason': value.get('queued_reason')} for value in self.service.jobs.values()]
        children = [j for j in local + self.service.remotes.history() if not j.get('execution_parent_id') and j['id'] not in child_ids]
        return sorted(parents + children, key=lambda job: job['created_at'], reverse=True)

    def cancel(self, key):
        return self.backend(key).cancel(key)

    def active_ids(self):
        # A task list is a bounded UI view; lifecycle safety must include every
        # durable record, including an old long-running task below that view.
        self.service.history()
        local = [j['id'] for j in self.service.jobs.values() if j['status'] in ACTIVE]
        coordinated = [j['id'] for j in self.app.executions.history() if j['status'] in ACTIVE]
        remote = [key for key, j in self.service.remotes.state.get('jobs', {}).items()
                  if j.get('summary', {}).get('status') in ACTIVE]
        return sorted(set(local + coordinated + remote))

    def _recover(self, request_key):
        # Only needed after an interrupted response/publication, not on polling.
        for folder in (self.app.executions.directory, self.service.jobs_dir):
            for path in folder.glob('*/job.json'):
                value = read_json(path, {})
                runtime = value.get('graph', {}).get('runtime', {})
                if runtime.get('submission_key') == request_key and not runtime.get('execution_parent_id'):
                    return self.details(value['id'])
        for record in self.service.remotes.state.get('jobs', {}).values():
            value = record.get('job') or record.get('last_job') or {}
            if value.get('graph', {}).get('runtime', {}).get('submission_key') == request_key:
                return self.details(value['id'])
        return None

    def launch(self, graph):
        """Compatibility entry for a user click without an idempotency key."""
        with self.app.submission_guard:
            if self.app.stopping:
                raise CommandError('service_stopping', 'The service is stopping; retry after it restarts', 503)
            graph = Graph.model_validate(layout(graph)) if isinstance(graph, dict) else graph
            return self._launch(graph)

    def _launch(self, graph):
        return (self.app.executions.launch(graph) if self.app.executions.applies(graph)
                else self.service.launch(graph))

    def _prepare_submission(self, graph):
        original = Graph.model_validate(layout(graph)) if isinstance(graph, dict) else graph
        prepared = self.app.prepare(original)
        # Freeze values while retaining historical implementation requirements.
        # The worker-launch snapshot must resolve those pins itself so its
        # migration receipt remains attached to this run's immutable evidence.
        def retain_pins(before, after):
            after.plugin_lock.update(before.plugin_lock)
            nodes = {node.id: node for node in after.nodes}
            for node in before.nodes:
                if node.kind == 'route':
                    retain_pins(node.route.graph, nodes[node.id].route.graph)
        retain_pins(original, prepared)
        self.app.validate(prepared, require_files=True)
        return prepared

    def submit(self, payload):
        # Serialize durable acceptance with shutdown; scientific jobs still run
        # concurrently under the existing admission/memory coordinator.
        with self.app.submission_guard:
            if self.app.stopping:
                raise CommandError('service_stopping', 'The service is stopping; retry after it restarts', 503)
            return self._submit(payload)

    def _submit(self, payload):
        request_id = payload.get('request_id') or uuid.uuid4().hex
        if not isinstance(request_id, str) or not 1 <= len(request_id) <= 200:
            raise CommandError('invalid_request', 'request_id must be a nonempty string of at most 200 characters')
        request = {k: payload[k] for k in ('graph', 'workflow_id', 'expected_version') if k in payload}
        digest = hashlib.sha256(json.dumps(request, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()
        request_key = hashlib.sha256(request_id.encode()).hexdigest()
        path = self.app.requests / (request_key + '.json')
        with FileLock(path.with_suffix('.lock'), timeout=120):
            receipt = read_json(path)
            if receipt:
                if receipt['digest'] != digest:
                    raise CommandError('idempotency_conflict', 'request_id was already used for a different graph', 409)
                if receipt.get('job_id'):
                    return {**self.details(receipt['job_id']), 'request_id': request_id, 'reused': True}
                recovered = self._recover(request_key)
                if recovered:
                    atomic_json(path, {**receipt, 'state': 'submitted', 'job_id': recovered['id']})
                    return {**recovered, 'request_id': request_id, 'reused': True}
                # A crash before/around submission must never silently duplicate
                # work. The retained receipt is evidence for manual reconciliation.
                if receipt['state'] == 'pending':
                    raise CommandError('submission_uncertain', 'Submission was interrupted; inspect jobs before using a new request_id', 409,
                                       {'request_id': request_id})
                raise CommandError('submission_failed', receipt.get('error', 'Submission failed; use a new request_id after fixing the cause'))
            graph = self.app.workflows.graph(payload)
            prepared = self._prepare_submission(graph)
            prepared.runtime['submission_key'] = request_key
            receipt = {'request_id': request_id, 'digest': digest, 'state': 'pending',
                       'created_at': datetime.now(timezone.utc).isoformat()}
            atomic_json(path, receipt)
            try:
                result = self._launch(prepared)
            except Exception as error:
                recovered = self._recover(request_key)
                if recovered:
                    atomic_json(path, {**receipt, 'state': 'submitted', 'job_id': recovered['id']})
                    return {**recovered, 'request_id': request_id, 'reused': True}
                # A transport exception can arrive after a remote worker was
                # accepted. Without durable job evidence this remains uncertain;
                # never advise a blind resubmission under a fresh identity.
                atomic_json(path, {**receipt, 'state': 'pending', 'error': str(error)})
                raise
            atomic_json(path, {**receipt, 'state': 'submitted', 'job_id': result['id']})
            return {**result, 'request_id': request_id, 'reused': False}

    def logs(self, key, *, offset=0, limit=65536):
        if type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= 1048576:
            raise CommandError('invalid_request', 'Invalid byte offset or limit (1..1048576)')
        job = self.details(key)
        backend = self.backend(key)
        if backend is self.service.remotes:
            ref = backend.reference(key)
            result = backend.call(ref['profile_id'], 'console', {'job_id': ref['job_id'], 'offset': offset, 'limit': limit})
            data = base64.b64decode(result['base64']) if 'base64' in result else result.get('text', '').encode()
            # Older remote agents return a fixed 64 KiB chunk. Honor this API's
            # requested window and cursor without losing the unread remainder.
            if 'base64' in result:
                start = max(0, result['offset'] - len(data))
                selected = data[:limit]
                end = start + len(selected)
                eof = result['done'] and len(selected) == len(data)
            else:
                selected = data[offset:offset + limit]
                end = offset + len(selected)
                eof = end >= len(data)
            return {'text': selected.decode('utf-8', errors='replace'), 'base64': base64.b64encode(selected).decode(),
                    'offset': end, 'eof': eof, 'reset': end < offset,
                    'done': eof and job['status'] not in ACTIVE, 'status': job['status']}
        path = backend.console_path(key) if backend is self.app.executions else self.service.jobs_dir / key / 'console.log'
        if path.is_file():
            with path.open('rb') as stream:
                size = path.stat().st_size
                reset = offset > size
                stream.seek(0 if reset else offset)
                data = stream.read(limit)
                end = stream.tell()
            return {'text': data.decode('utf-8', errors='replace'), 'base64': base64.b64encode(data).decode(),
                    'offset': end, 'eof': end >= size, 'reset': reset,
                    'done': end >= size and job['status'] not in ACTIVE and job.get('logs_complete', True), 'status': job['status']}
        return {'text': '', 'base64': '', 'offset': 0, 'eof': True, 'done': job['status'] not in ACTIVE,
                'status': job['status'], 'error': job.get('error')}


class ArtifactService:
    """Bounded metadata and controlled files; never eager-load a dataset."""
    def __init__(self, application):
        self.app = application

    def list(self, job_id):
        job = self.app.jobs.details(job_id)
        artifacts = []
        for item in (job.get('report') or {}).get('artifacts', []):
            artifacts.append({**item, 'job_id': job_id, 'available': bool(item.get('disk_uri')),
                              'href': f'/api/v1/jobs/{job_id}/artifacts/{item["artifact_id"]}/file'})
        reports, figures = [], []
        for index, step in enumerate((job.get('summary') or {}).get('steps', [])):
            if not step.get('export_path'):
                continue
            href = f'/api/v1/jobs/{job_id}/reports/{index}'
            reports.append({'index': index, 'name': step.get('name'), 'inputs': step.get('inputs', []),
                            'parameters': step.get('params', {}), 'href': href})
            for figure in step.get('figures', []):
                if not isinstance(figure, dict) or not figure.get('format'):
                    continue
                query = {'format': figure['format']}
                if figure.get('id') is not None:
                    query['figure_id'] = figure['id']
                figures.append({**figure, 'job_id': job_id, 'report_index': index,
                                'producer': step.get('name'), 'href': href + '/figure?' + urlencode(query)})
        return {'schema_version': 1, 'job_id': job_id, 'status': job['status'],
                'artifacts': artifacts, 'reports': reports, 'figures': figures,
                'provenance': {'graph': f'/api/v1/jobs/{job_id}',
                               'operator_generation': (job.get('plugins') or {}).get('generation'),
                               'parameters': f'/api/v1/jobs/{job_id}/parameters',
                               'execution': job.get('graph', {}).get('runtime', {}).get('execution'),
                               'run_id': (job.get('summary') or {}).get('run_id')}}

    def metadata(self, job_id, artifact_id):
        found = next((item for item in self.list(job_id)['artifacts'] if item['artifact_id'] == artifact_id), None)
        if found is None:
            raise KeyError('Unknown artifact')
        return found

    def file(self, job_id, artifact_id, role=None):
        backend = self.app.jobs.backend(job_id)
        return backend.artifact_file(job_id, artifact_id, role) if role else backend.artifact(job_id, artifact_id)[0]

    def preview(self, job_id, artifact_id):
        return self.app.jobs.backend(job_id).preview(job_id, artifact_id)

    def report(self, job_id, index):
        return self.app.jobs.backend(job_id).export_file(job_id, index)

    def figure(self, job_id, index, format=None, figure_id=None):
        return self.app.jobs.backend(job_id).figure_file(job_id, index, format=format, figure_id=figure_id)
