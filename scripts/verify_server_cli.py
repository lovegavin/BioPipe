"""Real terminal acceptance on Windows or Linux, without a desktop window.

Use a new --work-dir. Only synthetic files and this test's service are created.
Run with the intended Operon interpreter. Results are retained even on failure.
"""
import argparse
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work-dir', type=Path, required=True)
    parser.add_argument('--prepare-analysis', action='store_true',
                        help='Explicitly install route-scoped dependencies and run the CSV/PCA starter')
    args = parser.parse_args()
    work = args.work_dir.resolve()
    if work.exists():
        parser.error('Use a new work directory; previous evidence is never overwritten')
    work.mkdir(parents=True)
    project = work / 'project with spaces'
    project.mkdir()
    scratch = work / 'tmp'
    scratch.mkdir()
    env = dict(os.environ, PYTHONPATH=str(ROOT), PYTHONNOUSERSITE='1',
               PYTHONUTF8='1', PYTHONIOENCODING='utf-8', PYTHONDONTWRITEBYTECODE='1',
               OPERON_REGISTRY_MAINTENANCE='1', OPERON_ADMISSION_DIR=str(work / 'admission'),
               OPERON_RUNTIME_CONFIG=str(work / 'runtime.json'), TEMP=str(scratch), TMP=str(scratch), TMPDIR=str(scratch))
    for name in ('OPERON_PROFILE_DIR', 'OPERON_WORKSPACE', 'OPERON_DATA_DIR', 'OPERON_INSTALL_ROOT'):
        env.pop(name, None)
    report = {'status': 'failed', 'python': sys.executable, 'platform': sys.platform,
              'started': datetime.now(timezone.utc).isoformat(), 'checks': [], 'commands': []}
    serial = 0

    def command(*parts, expected=0, parse=True, timeout=240):
        nonlocal serial
        serial += 1
        start = time.monotonic()
        result = subprocess.run([sys.executable, '-m', 'operon', '--workspace', '.', *parts],
                                cwd=project, env=env, capture_output=True, text=True,
                                encoding='utf-8', timeout=timeout)
        prefix = work / f'{serial:02d}-{"-".join(parts[:2]).replace("/", "_")}'
        prefix.with_suffix('.stdout').write_text(result.stdout, encoding='utf-8')
        prefix.with_suffix('.stderr').write_text(result.stderr, encoding='utf-8')
        report['commands'].append({'args': list(parts), 'exit': result.returncode,
                                   'seconds': round(time.monotonic() - start, 3)})
        assert result.returncode in (expected if isinstance(expected, tuple) else (expected,)), (parts, result.returncode, result.stderr[-4000:])
        return json.loads(result.stdout) if parse else result

    def check(name, **details):
        report['checks'].append({'name': name, **details})
        print(name, flush=True)

    try:
        version = command('--version', parse=False).stdout.strip()
        assert version.startswith('Operon 3.')
        command('service', 'status')
        assert not (project / '.studio').exists()
        (project / 'bad.yaml').write_text('format: wrong\n', encoding='utf-8')
        command('run', 'bad.yaml', expected=2, parse=False)
        assert not (project / '.studio').exists()
        check('Offline status and malformed YAML do not start a service', version=version)
        sys.path.insert(0, str(ROOT))
        from operon.script_operators import inspect_script, extract_parameters
        from operon.workflow_spec import compile_spec, export_workflow, parse as parse_yaml
        example = ROOT / 'examples/workflows/script_pipeline'
        spec = parse_yaml((example / 'workflow.yaml').read_text(encoding='utf-8'))
        graph = compile_spec(spec, example)
        for node in graph['nodes']:
            field = 'rows' if node['id'] == 'generate' else 'factor'
            extracted = extract_parameters(node['script'], [field])
            node['script'] = extracted['script']
            node['params'] = {field: {'generate': 4, 'branch_a': 5, 'branch_b': 7}[node['id']]}
        graph['memory']['budget_mb'] = 32
        graph['memory'].pop('process_limit_mb', None)
        route = project / 'route'
        export_workflow(graph, route)
        workflow = 'route/workflow.yaml'
        frozen = hashlib.sha256((route / 'parameters.json').read_bytes()).hexdigest()
        command('workflow', 'lint', workflow)
        command('workflow', 'format', workflow)
        assert hashlib.sha256((route / 'parameters.json').read_bytes()).hexdigest() == frozen
        check('YAML lint/format preserve independent parameter JSON')
        status = command('environment', 'status')
        assert Path(status['workspace']) == project
        assert Path(status['python']).resolve() == Path(sys.executable).resolve()
        assert status['dependency_policy'] == 'explicit-route-preparation'
        check('Environment status describes actual service runtime and terminal-relative workspace', environment=status)
        for action in ('check', 'prepare'):
            ready = command('environment', action, workflow)
            assert ready['readiness']['status'] == 'ready', ready
        assert command('jobs', 'list') == []
        check('Route check and explicit preparation do not submit jobs')
        blocked = deepcopy(graph)
        blocked['nodes'][0]['script']['dependencies'] = ['numpy==0.0.0']
        (project / 'blocked.json').write_text(json.dumps(blocked), encoding='utf-8')
        value = command('environment', 'check', 'blocked.json', expected=1)
        assert value['readiness']['status'] == 'blocked'
        assert command('jobs', 'list') == []
        check('Missing/conflicting requirements fail validation without installing or submitting')
        result = command('run', workflow, '--progress', '--brief', '--request-id', 'cli-acceptance-1', '--timeout', '240', timeout=300)
        assert result['status'] == 'complete', result
        job_id = result['id']
        job = command('jobs', 'get', job_id, '--view', 'full')
        (work / 'job.json').write_text(json.dumps(job, ensure_ascii=False, indent=2), encoding='utf-8')
        job_dir = project / '.studio/jobs' / job_id
        contents = [path.read_text(encoding='utf-8').replace('\r', '').strip() for path in job_dir.rglob('table.csv')]
        assert 'value\n5.0\n10.0\n15.0\n20.0' in contents, contents
        assert 'value\n7.0\n14.0\n21.0\n28.0' in contents, contents
        assert (job_dir / 'parameters.json').is_file()
        assert list(job_dir.rglob('memory_report.json'))
        check('Real branched YAML execution preserves frozen values and memory artifacts', job_id=job_id)
        assert command('jobs', 'logs', job_id, '--limit', '512')['text']
        artifacts = command('artifacts', 'list', job_id)
        assert artifacts
        check('Task logs and retained artifacts are available without a desktop')
        command('service', 'stop')
        deadline = time.monotonic() + 30
        while command('service', 'status')['instances']:
            assert time.monotonic() < deadline, 'Headless service did not stop'
            time.sleep(.3)
        reused = command('run', workflow, '--wait', '--brief', '--request-id', 'cli-acceptance-1', '--timeout', '60')
        assert reused['id'] == job_id and reused['status'] == 'complete'
        assert len(command('jobs', 'list')) == 1
        check('Service restart reuses the original task for the same request ID')
        broken = project / 'failure.py'
        broken.write_text('# output: table file.csv\nraise RuntimeError("cli-acceptance-failure")\n', encoding='utf-8')
        failed_graph = deepcopy(graph)
        failed_graph['nodes'] = [dict(graph['nodes'][0], script=inspect_script(broken), params={})]
        failed_graph['edges'] = []
        failed_graph['runtime'].pop('workflow_outputs', None)
        (project / 'failure.json').write_text(json.dumps(failed_graph), encoding='utf-8')
        failure = command('run', 'failure.json', '--wait', '--brief', '--timeout', '120', expected=1)
        assert failure['status'] == 'failed'
        assert 'cli-acceptance-failure' in command('jobs', 'logs', failure['id'], '--limit', '65536')['text']
        check('Worker failure returns nonzero and retains error logs', job_id=failure['id'])
        if args.prepare_analysis:
            # This opt-in performs actual provider preparation, never an
            # implicit side effect of validation or ordinary job submission.
            command('workflow', 'init', 'analysis')
            settings = project / 'analysis/execution.json'
            config = json.loads(settings.read_text(encoding='utf-8'))
            config['memory']['budget_mb'] = 32
            settings.write_text(json.dumps(config), encoding='utf-8')
            before = command('environment', 'check', 'analysis/workflow.yaml', expected=(0, 1))
            assert before['readiness']['status'] in ('ready', 'blocked')
            prepared = command('environment', 'prepare', 'analysis/workflow.yaml', timeout=1800)
            assert prepared['readiness']['status'] == 'ready', prepared
            assert len(command('jobs', 'list')) == 2
            done = command('run', 'analysis/workflow.yaml', '--wait', '--brief', '--timeout', '240', timeout=300)
            assert done['status'] == 'complete'
            check('Explicit provider preparation and CSV/PCA starter', before=before['readiness']['status'],
                  after='ready', job_id=done['id'])
        assert hashlib.sha256((route / 'parameters.json').read_bytes()).hexdigest() == frozen
        report['status'] = 'passed'
    except BaseException:
        report['error'] = traceback.format_exc()
        print(report['error'], file=sys.stderr)
    finally:
        try:
            if (project / '.studio').exists():
                command('service', 'stop')
        except Exception as error:
            report['cleanup_error'] = str(error)
            report['status'] = 'failed'
        report['finished'] = datetime.now(timezone.utc).isoformat()
        (work / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    return 0 if report['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
