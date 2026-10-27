"""Frozen host capacity, durable admission and isolated real worker processes."""
from copy import deepcopy
import json
import os
from pathlib import Path
import time

import pytest
import yaml

from src.web.admission import HostAdmission, MIB
from src.web.graph import GraphError
from src.web.models import Graph
from src.web.service import JobService, Settings, write_json

ROOT = Path(__file__).resolve().parents[1]


def wait_until(check, timeout=20):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = check()
        if result:
            return result
        time.sleep(.05)
    pytest.fail('Timed out waiting for scheduler/worker')


def test_pool_is_shared_and_capacity_is_scanned_once(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr('src.task.memory.system.available_memory', lambda: calls.append(True) or 1000 * MIB)
    first = HostAdmission(tmp_path, cpu_threads=4)
    second = HostAdmission(tmp_path, cpu_threads=99)
    try:
        assert calls == [True]
        assert first.capacity == second.capacity == 900 * MIB
        allocation = first.request({'runtime': {'memory': {'budget_mb': 250}}})
        assert allocation['budget_bytes'] == 250 * MIB
        assert first.reserve('one', allocation)
        assert not second.reserve('two', allocation)
        assert second.resources()['reserved_bytes'] <= first.capacity
        assert first.release('one') is True
        assert first.release('one') is False
        assert second.reserve('two', allocation)
        second.release('two')
        assert calls == [True]  # Resource reads and releases never rescan.
    finally:
        first.close(); second.close()


def test_cpu_and_memory_limits_are_independent(tmp_path):
    pool = HostAdmission(tmp_path, available_bytes=4096 * MIB, cpu_threads=2)
    try:
        allocation = pool.request({'runtime': {'memory': {'budget_mb': 16}}, 'steps': [{'params': {'threads': 2}}]})
        assert pool.reserve('one', allocation)
        assert not pool.reserve('two', allocation)  # Plenty of RAM, no CPU slots.
        pool.release('one')
        with pytest.raises(ValueError, match='capacity'):
            pool.request({'runtime': {'memory': {'budget_mb': 4096}}})
        disabled = pool.request({'runtime': {'memory': {'enabled': False}}})
        assert disabled['reserved_bytes'] == pool.capacity
        assert disabled['cpu_threads'] == pool.cpus
    finally:
        pool.close()


def test_dead_owner_reservations_are_reconciled(tmp_path):
    pool = HostAdmission(tmp_path, available_bytes=4096 * MIB, cpu_threads=2)
    allocation = pool.request({'runtime': {'memory': {'budget_mb': 16}}})
    pool.reserve('dead', allocation)
    state = json.loads(pool.path.read_text())
    state['reservations']['dead']['owner'] = {'pid': 99999999, 'created': 0}
    write_json(pool.path, state)
    assert pool.resources()['reserved_bytes'] == 0
    pool.close()


@pytest.fixture
def service(tmp_path, monkeypatch):
    from src.task import STEPS
    from src.task.operator_catalog import build_catalog
    import src.web.service as module
    monkeypatch.setattr(module, 'HostAdmission', lambda path: HostAdmission(path, available_bytes=2048 * MIB, cpu_threads=2))
    code = tmp_path / 'code'
    (code / 'scripts').mkdir(parents=True)
    (code / 'scripts/run.py').write_text('''import json,os,sys,time
from pathlib import Path
task=Path(sys.argv[1]); output=task/'output'; output.mkdir()
(output/'started.json').write_text(json.dumps({'pid':os.getpid(),'cpu':os.environ.get('BIOPIPE_CPU_LIMIT'), 'blas':os.environ.get('OPENBLAS_NUM_THREADS')}))
events=output/'runs'/'r'; events.mkdir(parents=True)
(events/'events.jsonl').write_text(json.dumps({'event':'step_started','index':1,'name':'synthetic'})+'\\n')
while not (task/'finish').exists():
    if (task/'cancel.requested').exists(): sys.exit(1)
    time.sleep(.03)
(output/'run_summary.json').write_text(json.dumps({'status':'complete'}))
''', encoding='utf-8')
    settings = Settings(tmp_path, tmp_path / 's', ROOT / 'frontend/dist', testing=True, code_root=code)
    result = JobService(settings, build_catalog(STEPS))
    yield result
    result.shutdown()


def graph_for(service):
    return Graph.model_validate(deepcopy(service.demo))


def test_two_real_workers_run_concurrently_third_queues_and_advances(service):
    graph = graph_for(service)
    first, second, third = [service.launch(graph) for _ in range(3)]
    assert first['status'] == second['status'] == 'running'
    assert third['status'] == 'queued' and third['queue_position'] == 1
    resource = service.resources()
    assert resource['active_jobs'] == 2 and resource['queued_jobs'] == 1
    assert resource['reserved_bytes'] <= resource['capacity_bytes']
    assert resource['cpu_reserved'] <= resource['cpu_capacity']
    for job in (first, second):
        started = service.jobs_dir / job['id'] / 'output/started.json'
        wait_until(started.exists)
        evidence = json.loads(started.read_text())
        assert evidence['cpu'] == evidence['blas'] == '1'
        task = yaml.safe_load((service.jobs_dir / job['id'] / 'task.yaml').read_text(encoding='utf-8'))
        assert task['runtime']['memory']['budget_mb'] * MIB == job['allocation']['budget_bytes']
        assert 'budget_mb' not in job['graph']['memory']
    assert service.processes[first['id']].pid != service.processes[second['id']].pid
    (service.jobs_dir / first['id'] / 'finish').touch()
    wait_until(lambda: service.details(third['id'])['status'] == 'running')
    assert service.details(first['id'])['progress']['percent'] == 100
    for job in (second, third):
        (service.jobs_dir / job['id'] / 'finish').touch()
    wait_until(lambda: all(service.details(job['id'])['logs_complete'] for job in (first, second, third)))
    assert service.resources()['reserved_bytes'] == 0
    assert all(service.details(job['id'])['allocation']['state'] == 'released' for job in (first, second, third))


def test_cancel_queue_and_running_releases_once(service):
    graph = graph_for(service)
    graph.memory['enabled'] = False  # Explicitly unmanaged runs are exclusive.
    first = service.launch(graph); queued = service.launch(graph)
    assert queued['status'] == 'queued'
    cancelled = service.cancel(queued['id'])
    assert cancelled['status'] == 'cancelled' and cancelled['logs_complete']
    assert not (service.jobs_dir / queued['id'] / 'output').exists()
    service.cancel(first['id'])
    wait_until(lambda: service.details(first['id'])['logs_complete'])
    service.cancel(first['id']); service.cancel(queued['id'])
    assert service.resources()['reserved_bytes'] == 0
    assert service.details(first['id'])['status'] == 'cancelled'


def test_spawn_failure_keeps_log_and_releases_capacity(service, monkeypatch):
    monkeypatch.setattr(service.plugins, 'python_for', lambda _: str(service.root / 'missing.exe'))
    job = service.launch(graph_for(service))
    assert job['status'] == 'failed' and job['logs_complete']
    assert 'FileNotFoundError' in (service.jobs_dir / job['id'] / 'console.log').read_text(encoding='utf-8')
    assert job['allocation']['state'] == 'released'
    assert service.resources()['reserved_bytes'] == 0


def test_explicit_budget_is_preserved_and_oversized_request_rejected(service):
    graph = graph_for(service)
    graph.memory['budget_mb'] = 1800
    first = service.launch(graph)
    second = service.launch(graph)
    assert first['allocation']['budget_bytes'] == 1800 * MIB
    assert second['status'] == 'queued'
    graph.memory['budget_mb'] = 2048
    with pytest.raises(GraphError, match='capacity'):
        service.launch(graph)


def test_restart_resumes_durable_queue_without_replaying_running_job(service):
    graph = graph_for(service); graph.memory['enabled'] = False
    first = service.launch(graph); pending = service.launch(graph)
    queued_record = deepcopy(service.require(pending['id']))
    running_record = deepcopy(service.require(first['id']))
    service.shutdown()
    queued_record['owner'] = running_record['owner'] = {'pid': 99999999, 'created': 0}
    write_json(service.jobs_dir / pending['id'] / 'job.json', queued_record)
    write_json(service.jobs_dir / first['id'] / 'job.json', running_record)
    restarted = JobService(service.settings, service.base_catalog)
    try:
        assert restarted.details(first['id'])['status'] == 'interrupted'
        wait_until(lambda: restarted.details(pending['id'])['status'] == 'running')
        (restarted.jobs_dir / pending['id'] / 'finish').touch()
        wait_until(lambda: restarted.details(pending['id'])['logs_complete'])
        assert restarted.details(pending['id'])['status'] == 'complete'
        assert restarted.resources()['reserved_bytes'] == 0
    finally:
        restarted.shutdown()


def test_worker_handoff_retains_startup_snapshot_without_scanning(monkeypatch):
    from src.task.memory.config import MemoryConfig
    monkeypatch.setenv('BIOPIPE_AVAILABLE_AT_START_BYTES', str(4096 * MIB))
    def forbidden():
        raise AssertionError('Workers must not scan available memory again')
    monkeypatch.setattr('src.task.memory.system.available_memory', forbidden)
    config = MemoryConfig.parse({'runtime': {'memory': {'budget_mb': 128, 'process_limit_mb': 512}}})
    assert config.budget_bytes == 128 * MIB
    assert config.available_at_start_bytes == 4096 * MIB


def test_native_tool_thread_count_honors_admission(tmp_path, monkeypatch):
    from biopipe.tool_runner import ToolRunner
    from src.task.context import Context
    monkeypatch.setenv('BIOPIPE_CPU_LIMIT', '2')
    ctx = Context(tmp_path, {})
    try:
        runner = ToolRunner(ctx, {'executor': 'native', 'threads': 16})
        assert runner.threads == 2
    finally:
        ctx.finalize()


def test_actual_scientific_workers_keep_independent_memory_and_logs(service):
    service.settings.code_root = ROOT
    graph = graph_for(service)
    graph.memory['budget_mb'] = 64
    jobs = [service.launch(graph) for _ in range(2)]
    assert all(job['status'] == 'running' for job in jobs)
    assert len({service.processes[job['id']].pid for job in jobs}) == 2
    wait_until(lambda: all(service.details(job['id'])['logs_complete'] for job in jobs), timeout=30)
    for job in jobs:
        result = service.details(job['id'])
        assert result['status'] == 'complete', result.get('error')
        assert result['report']['budget_bytes'] == 64 * MIB
        assert result['report']['available_at_start_bytes'] == 2048 * MIB
        assert result['progress']['percent'] == 100
        assert len(result['report']['artifacts']) > 0
        assert 'status=complete' in (service.jobs_dir / job['id'] / 'console.log').read_text(encoding='utf-8')
    assert service.resources()['reserved_bytes'] == 0


def test_persistent_unmanaged_pressure_is_contained_and_logged(service):
    (service.settings.code_root / 'scripts/run.py').write_text(
        'import time\ndata=bytearray(96*1024**2)\ntime.sleep(20)\n', encoding='utf-8')
    graph = graph_for(service)
    graph.memory.update(budget_mb=1, process_limit_mb=16)
    job = service.launch(graph)
    wait_until(lambda: service.details(job['id'])['logs_complete'], timeout=15)
    result = service.details(job['id'])
    assert result['status'] == 'failed'
    assert 'RSS' in result['error'] and 'reservation' in result['error']
    assert service.resources()['reserved_bytes'] == 0
    assert result['allocation']['state'] == 'released'
