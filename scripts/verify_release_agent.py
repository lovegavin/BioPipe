"""Real CLI/MCP acceptance against an explicit, already running Operon instance.

Never creates a canvas session or fabricates selection. Canvas phases require a
real desktop window. Keep each release variant in its own synthetic profile.
"""
from __future__ import annotations
import argparse
import asyncio
from contextlib import asynccontextmanager
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


class Acceptance:
    def __init__(self, args):
        self.args = args
        self.code = args.code_root.resolve()
        self.workspace = args.workspace.resolve()
        self.evidence = args.evidence.resolve(); self.evidence.mkdir(parents=True, exist_ok=True)
        self.state_path = self.evidence / 'state.json'
        self.state = json.loads(self.state_path.read_text(encoding='utf-8')) if self.state_path.exists() else {}
        self.report = {'phase': args.phase, 'started': datetime.now(timezone.utc).isoformat(), 'checks': [],
                       'code_root': str(self.code), 'workspace': str(self.workspace),
                       'ui_observation': 'Not performed by this script; separate EXE visual verification required.'}
        self.env = dict(os.environ, PYTHONPATH=str(self.code), PYTHONUTF8='1', PYTHONIOENCODING='utf-8')
        sys.path.insert(0, str(self.code))
        from operon.client import Client
        self.control = Client(self.workspace / '.studio', instance=args.instance,
                              name='Release acceptance', scopes=['context', 'edit', 'run'])
        record = self.control.instance
        self.instance = record['instance_id']
        self.report['instance'] = {key: value for key, value in record.items() if key != 'secret'}
        self.command = [str(args.python), '-m', 'operon', '--workspace', str(self.workspace), '--instance', self.instance]
        import psutil
        command = psutil.Process(record['pid']).cmdline()
        self.report['backend_process'] = {'pid': record['pid'], 'executable': command[0],
                                         'launch_kind': 'headless' if record.get('headless') else 'desktop'}
        if not args.allow_headless:
            assert not record.get('headless'), 'Expected packaged desktop, found headless service'
            entry = next((part for part in command if part.endswith('desktop_server.py')), None)
            assert entry and Path(entry).resolve().is_relative_to(self.code), 'Backend is not from the selected packaged code root'
            self.report['backend_process']['entry'] = str(Path(entry).resolve())
        probe = json.loads(self.process([str(args.python), '-c',
            'import json,operon,operon.worker; print(json.dumps({"package":operon.__file__,"worker":operon.worker.__file__,"version":operon.__version__}))']))
        assert Path(probe['package']).resolve().is_relative_to(self.code)
        assert Path(probe['worker']).resolve().is_relative_to(self.code)
        assert probe['version'] == args.version
        self.report['client_package'] = probe

    def check(self, name, value=True):
        self.report['checks'].append({'name': name, 'passed': True, 'evidence': value})

    def process(self, command):
        result = subprocess.run(command, cwd=self.code, env=self.env, capture_output=True, encoding='utf-8', timeout=150)
        with (self.evidence / 'cli.log').open('a', encoding='utf-8') as log:
            log.write(json.dumps({'argv': command, 'code': result.returncode}) + '\n' + result.stdout + '\n' + result.stderr + '\n')
        assert result.returncode == 0, result.stderr or result.stdout
        return result.stdout

    def cli(self, *args):
        return json.loads(self.process(self.command + list(args)))

    @asynccontextmanager
    async def mcp(self, *flags):
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
        config = StdioServerParameters(command=str(self.args.python), args=self.command[1:] + ['mcp', *flags],
                                       cwd=str(self.code), env=self.env)
        with (self.evidence / 'mcp-stderr.log').open('a', encoding='utf-8') as log:
            async with stdio_client(config, errlog=log) as (reader, writer):
                async with ClientSession(reader, writer) as session:
                    init = await session.initialize()
                    self.check('MCP initialize', {'name': init.serverInfo.name, 'version': init.serverInfo.version})
                    yield session

    async def call(self, session, tool, args=None, *, denied=None):
        result = await session.call_tool(tool, args or {})
        text = '\n'.join(item.text for item in result.content if hasattr(item, 'text'))
        with (self.evidence / 'mcp.jsonl').open('a', encoding='utf-8') as log:
            log.write(json.dumps({'tool': tool, 'arguments': args, 'is_error': bool(result.isError), 'text': text}, ensure_ascii=False) + '\n')
        if denied:
            assert result.isError and denied.lower() in text.lower(), text
            self.check(tool + ' rejected', denied)
            return None
        assert not result.isError, text
        if tool == 'operon_sessions':
            # FastMCP represents a list as structured result and may emit each
            # item in its own text block (one item is not a JSON array).
            structured = getattr(result, 'structuredContent', None)
            if isinstance(structured, dict) and isinstance(structured.get('result'), list):
                return structured['result']
            values = [json.loads(item.text) for item in result.content if hasattr(item, 'text')]
            return values[0] if len(values) == 1 and isinstance(values[0], list) else values
        return json.loads(text)

    def fixture(self):
        source = self.workspace / 'release-agent-input.csv'
        source.write_text('geneA,geneB,geneC\n1,3,5\n2,6,10\n3,9,15\n4,12,20\n', encoding='utf-8')
        return {'schema_version': 2, 'name': 'Operon release agent acceptance', 'base_dir': '.',
                'memory': {'enabled': True, 'auto_spill': True, 'budget_mb': 64, 'process_limit_mb': 768,
                           'chunk_mb': .01, 'io_buffer_kb': 4, 'keep': ['input', 'pcs']},
                'nodes': [
                    {'id': 'input', 'kind': 'source', 'position': {'x': 80, 'y': 170},
                     'source': {'path': source.name, 'reader': 'CsvReader', 'dims': ['sample', 'feature'],
                                'labels': {'sample': 'auto', 'feature': 'builtin'}}},
                    {'id': 'pca', 'kind': 'operator', 'operator': 'pca', 'position': {'x': 390, 'y': 80},
                     'params': {'dim': 'feature', 'n_components': 2, 'output': 'pcs'}},
                    {'id': 'summary', 'kind': 'operator', 'operator': 'describe', 'position': {'x': 390, 'y': 350}, 'params': {}},
                    {'id': 'scatter', 'kind': 'operator', 'operator': 'scatter', 'position': {'x': 720, 'y': 80},
                     'params': {'dim': 'component', 'x_label': 'PC1', 'y_label': 'PC2', 'filename': 'release-pca.png',
                                'title': 'Synthetic PCA', 'figure_width_mm': 90, 'figure_height_mm': 75}}],
                'edges': [{'id': 'input-pca', 'source': 'input', 'target': 'pca'},
                          {'id': 'input-summary', 'source': 'input', 'target': 'summary'},
                          {'id': 'pca-scatter', 'source': 'pca', 'target': 'scatter'}]}

    async def backend(self):
        assert not self.state.get('job_id'), 'Evidence already contains a run; use retry or a fresh evidence directory'
        graph = self.fixture()
        async with self.mcp('--read-only') as session:
            names = {tool.name for tool in (await session.list_tools()).tools}
            assert {'operon_context', 'operon_apply', 'operon_submit', 'operon_artifacts'} <= names
            self.check('MCP tool discovery', sorted(names))
            guide = await self.call(session, 'operon_guide')
            assert guide['topic'] == 'start' and guide['content']
            cached = await self.call(session, 'operon_guide', {'if_sha256': guide['sha256']})
            assert not cached.get('content')
            resources = await session.list_resources()
            assert 'operon://guide' in {str(item.uri) for item in resources.resources}
            search_page = await self.call(session, 'operon_operator_search', {'query': ''})
            assert len(search_page['items']) <= 5
            assert all('parameters_schema' not in item for item in search_page['items'])
            schema = await self.call(session, 'operon_operator_describe', {'ids': ['pca']})
            assert 'parameters_schema' in schema['items'][0]['descriptor']
            self.check('Layered guides, conditional reuse and bounded default schemas')
            searched = await self.call(session, 'operon_operator_search', {'query': 'pca', 'limit': 3})
            assert len(searched['items']) <= 3
            described = await self.call(session, 'operon_operator_describe', {'ids': ['pca'], 'sections': ['parameters']})
            assert 'parameters' in described['items'][0]['documentation']['content']
            await self.call(session, 'operon_submit', {'request_id': 'release-denied', 'graph': graph}, denied='capability')
            await self.call(session, 'operon_workflow_save', {'graph': graph}, denied='capability')
        async with self.mcp() as session:
            prepared = await self.call(session, 'operon_workflow_prepare', {'graph': graph})
            saved = await self.call(session, 'operon_workflow_save', {'graph': prepared['graph']})
            edited = deepcopy(saved['graph']); edited['name'] += ' — saved edit'
            changed = await self.call(session, 'operon_workflow_save', {'graph': edited, 'workflow_id': saved['id'], 'expected_version': 1})
            assert changed['version'] == 2
            await self.call(session, 'operon_workflow_save', {'graph': edited, 'workflow_id': saved['id'], 'expected_version': 1}, denied='changed')
            await self.call(session, 'operon_submit', {'request_id': 'default-agent-denied', 'graph': graph}, denied='capability')
            fetched = await self.call(session, 'operon_workflows', {'workflow_id': saved['id']})
            assert fetched['graph'] == changed['graph']
        path = self.evidence / 'prepared-graph.json'; write(path, changed['graph'])
        self.state.update(workflow_id=saved['id'], expected_version=2, graph=changed['graph'],
                          request_id='release-agent-' + hashlib.sha256(str(self.evidence).encode()).hexdigest()[:20],
                          backend_instance=self.instance)
        if self.args.prepare_environment:
            # Explicit acceptance flag grants installation, separately from run.
            async with self.mcp('--allow-plugins') as session:
                prepared = await self.call(session, 'operon_workflow_prepare_environment', {'graph': changed['graph']})
                assert prepared['readiness']['status'] == 'ready', prepared
                self.check('Explicit route dependency preparation', prepared['readiness'])
        async with self.mcp('--allow-run') as session:
            job = await self.call(session, 'operon_submit', self.request())
            assert job['status'] in {'queued', 'preparing', 'running', 'uploading'}
            self.state['job_id'] = job['id']; write(self.state_path, self.state)
        self.check('MCP process exits while accepted task remains active', job['status'])
        deadline = time.monotonic() + 120
        while True:
            result = self.cli('jobs', 'get', job['id'])
            if result['status'] not in {'queued', 'preparing', 'running', 'uploading', 'waiting_connection'}:
                break
            assert time.monotonic() < deadline, result
            await asyncio.sleep(.3)
        assert result['status'] == 'complete', result.get('error')
        result = self.cli('jobs', 'get', job['id'], '--view', 'full')
        write(self.evidence / 'job.json', result)
        self.check('Real packaged scientific worker completed', {'job': job['id'], 'steps': [row['name'] for row in result['summary']['steps']]})
        parameters = self.control.request('/v1/jobs/' + job['id'] + '/parameters')
        write(self.evidence / 'frozen-parameters.json', parameters)
        assert parameters['memory']['enabled'] and parameters['memory']['auto_spill']
        assert result['report']['managed_peak_bytes'] > 0
        assert (self.workspace / '.studio/jobs' / job['id'] / 'parameters.json').is_file()
        self.check('Managed memory and independent parameter JSON retained')
        async with self.mcp('--allow-run') as session:
            again = await self.call(session, 'operon_submit', self.request())
            assert again['id'] == job['id'] and again['reused']
            index = await self.call(session, 'operon_artifacts', {'job_id': job['id']})
            brief = await self.call(session, 'operon_job', {'job_id': job['id'], 'wait_seconds': 1})
            assert brief['status'] == 'complete' and 'graph' not in brief and 'report' not in brief
            log_text = await self.call(session, 'operon_logs', {'job_id': job['id']})
            assert isinstance(log_text['text'], str) and 'base64' not in log_text
            write(self.evidence / 'artifacts.json', index)
            cursor, log = 0, bytearray()
            import base64
            while True:
                chunk = await self.call(session, 'operon_logs', {'job_id': job['id'], 'offset': cursor, 'limit': 127, 'encoding': 'base64'})
                block = base64.b64decode(chunk['base64']); assert len(block) <= 127
                log.extend(block); cursor = chunk['offset']
                if chunk['done']: break
            assert b'Task finished' in log
            (self.evidence / 'worker-console.log').write_bytes(log)
        summary = next(item for item in index['reports'] if item['name'] == 'describe')
        self.cli('artifacts', 'report', job['id'], str(summary['index']), '--output', str(self.evidence / 'summary.json'))
        assert json.loads((self.evidence / 'summary.json').read_text(encoding='utf-8'))['global']['mean'] == 7.5
        assert {'png', 'pdf', 'svg'} <= {item['format'] for item in index['figures']}
        for fmt in ('png', 'pdf', 'svg'):
            figure = next(item for item in index['figures'] if item['format'] == fmt)
            assert figure['width_mm'] == 90 and figure['height_mm'] == 75
            target = self.evidence / ('original-figure.' + fmt)
            self.cli('artifacts', 'figure', job['id'], str(figure['report_index']), '--format', fmt,
                     '--figure-id', figure['id'], '--output', str(target))
            assert target.stat().st_size > 100
            content = target.read_bytes()
            if fmt == 'png': assert content.startswith(b'\x89PNG\r\n\x1a\n')
            if fmt == 'pdf': assert content.startswith(b'%PDF-') and b'/FontFile2' in content
            if fmt == 'svg':
                import xml.etree.ElementTree as ET
                image = ET.fromstring(content)
                assert image.tag.endswith('svg') and '<text' in content.decode('utf-8')
                assert abs(float(image.attrib['width'].removesuffix('pt')) * 25.4 / 72 - 90) < .01
                assert abs(float(image.attrib['height'].removesuffix('pt')) * 25.4 / 72 - 75) < .01
        self.check('Exact logs, original PDF/SVG/PNG, numeric report and MCP retry', {'mean': 7.5, 'figure_mm': [90, 75]})
        spec = self.control.request('/v1/openapi.json')
        assert '/api/v1/jobs' in spec['paths']
        assert self.control.request('/v1/guides/api')['content']
        assert self.cli('help', 'workflow')['content']
        result = json.loads(self.process([str(self.args.python), str(self.code / 'examples/api_client/run_workflow.py'),
                                          '--workspace', str(self.workspace), '--job', job['id']]))
        assert result['job']['status'] == 'complete' and result['results']['job_id'] == job['id']
        self.check('Packaged API tutorial and authenticated OpenAPI', {'job_id': job['id']})

    def request(self):
        return {key: self.state[key] for key in ('request_id', 'workflow_id', 'expected_version')}

    async def retry(self):
        assert self.state['backend_instance'] != self.instance, 'Restart the tested backend before the restart acceptance phase'
        before = {item['id'] for item in self.cli('jobs', 'list')}
        async with self.mcp('--allow-run') as session:
            result = await self.call(session, 'operon_submit', self.request())
        assert result['id'] == self.state['job_id'] and result['reused']
        assert before == {item['id'] for item in self.cli('jobs', 'list')}
        self.check('Persisted retry across client/backend restart', {'job_id': result['id'], 'reused': result['reused']})

    async def canvas(self):
        async with self.mcp() as session:
            sessions = await self.call(session, 'operon_sessions')
            selected = self.args.session or (sessions[0]['id'] if len(sessions) == 1 else None)
            assert selected, 'Choose a real open desktop session using --session; this script never creates sessions'
            snapshot = await self.call(session, 'operon_graph', {'session_id': selected})
            if self.args.phase == 'open':
                opened = await self.call(session, 'operon_open', {'session_id': selected, 'expected_revision': snapshot['revision'],
                                                                 'mode': 'append', 'graph': self.state.get('graph') or self.fixture()})
                self.state['canvas'] = {'session_id': selected, 'document_id': opened['workspace']['active_id']}
                self.check('New synthetic tab opened; select PCA in the actual EXE', self.state['canvas'])
                return
            canvas = self.state['canvas']
            assert canvas['session_id'] == selected
            document = next(doc for doc in snapshot['workspace']['documents'] if doc['id'] == canvas['document_id'])
            if self.args.phase in ('capture', 'apply'):
                context = await self.call(session, 'operon_context', {'session_id': selected, 'scope': 'selection'})
                assert context['document_id'] == canvas['document_id'] and context['selection']['nodes'] == ['pca'], context
                resource = await session.read_resource(f'operon://sessions/{selected}/selection')
                assert json.loads(resource.contents[0].text)['selection']['nodes'] == ['pca']
                self.report['selection'] = context
                self.check('Real UI-published PCA selection visible through MCP tool and resource')
                if self.args.phase == 'capture': return
                baseline = deepcopy(document['graph'])
                pca = next(node for node in baseline['nodes'] if node['id'] == 'pca')
                commands = [{'op': 'update_node', 'id': 'pca', 'patch': {'params': {**pca['params'], 'n_components': 3}}},
                            {'op': 'add_node', 'node': {'id': 'agent_diagnostic', 'kind': 'operator', 'operator': 'describe',
                             'title': 'Agent diagnostic', 'position': {'x': 720, 'y': 350}, 'params': {}}},
                            {'op': 'connect', 'edge': {'id': 'agent-branch', 'source': 'pca', 'target': 'agent_diagnostic'}},
                            {'op': 'configure', 'patch': {'name': 'Operon release — Agent batch'}}]
                before_jobs = {job['id'] for job in self.cli('jobs', 'list')}
                applied = await self.call(session, 'operon_apply', {'session_id': selected, 'document_id': canvas['document_id'],
                    'expected_revision': snapshot['revision'], 'commands': commands, 'request_id': 'release-batch-' + str(snapshot['revision'])})
                assert applied['history'][canvas['document_id']]['undo'] == snapshot.get('history', {}).get(canvas['document_id'], {}).get('undo', 0) + 1
                assert before_jobs == {job['id'] for job in self.cli('jobs', 'list')}
                canvas.update(baseline=baseline, applied_revision=applied['revision'])
                self.check('Four graph edits form one undo entry and launch no job', {'revision': applied['revision']})
            elif self.args.phase == 'undo':
                assert snapshot['revision'] == canvas['applied_revision'], 'Canvas changed after agent batch; inspect it before undo'
                undone = await self.call(session, 'operon_undo', {'session_id': selected, 'document_id': canvas['document_id'],
                                                                  'expected_revision': snapshot['revision']})
                restored = next(doc['graph'] for doc in undone['workspace']['documents'] if doc['id'] == canvas['document_id'])
                assert restored == canvas['baseline']
                self.check('One MCP undo restored the entire pre-edit graph exactly', {'revision': undone['revision']})

    def finish(self, error=None):
        self.report.update(finished=datetime.now(timezone.utc).isoformat(), passed=error is None)
        if error: self.report['error'] = error
        write(self.state_path, self.state)
        write(self.evidence / (self.args.phase + '-report.json'), self.report)
        self.control.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=['backend', 'retry', 'open', 'capture', 'apply', 'undo'])
    parser.add_argument('--code-root', type=Path, required=True)
    parser.add_argument('--python', type=Path, default=Path(sys.executable))
    parser.add_argument('--workspace', type=Path, required=True)
    parser.add_argument('--instance', required=True)
    parser.add_argument('--evidence', type=Path, required=True)
    parser.add_argument('--session')
    parser.add_argument('--version', default='3.0.0')
    parser.add_argument('--prepare-environment', action='store_true',
                        help='Explicitly authorize installing only this synthetic route dependencies before backend acceptance')
    parser.add_argument('--allow-headless', action='store_true', help='Development smoke only; never label this an EXE UI test')
    args = parser.parse_args()
    try:
        run = Acceptance(args)
    except BaseException:
        write(args.evidence.resolve() / (args.phase + '-initialization-error.json'),
              {'passed': False, 'phase': args.phase, 'error': traceback.format_exc()})
        raise
    try:
        asyncio.run(run.backend() if args.phase == 'backend' else run.retry() if args.phase == 'retry' else run.canvas())
    except BaseException:
        run.finish(traceback.format_exc())
        raise
    else:
        run.finish()
        print(json.dumps({'passed': True, 'phase': args.phase, 'report': str(run.evidence / (args.phase + '-report.json'))}))


if __name__ == '__main__':
    main()
