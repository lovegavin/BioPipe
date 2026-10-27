"""Process-safe host admission. Capacity is frozen for a pool's live session.

The ledger is shared by Studio workspaces belonging to the same OS user. It
contains reservations, not measurements: polling never changes the capacity.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import socket
import uuid

import psutil

from .storage import FileLock, atomic_json

MIB = 1024 ** 2


def process_identity(pid=None):
    process = psutil.Process(pid or os.getpid())
    return {"pid": process.pid, "created": process.create_time()}


def process_alive(identity):
    try:
        return psutil.Process(identity["pid"]).create_time() == identity["created"]
    except (KeyError, psutil.NoSuchProcess):
        return False
    except psutil.AccessDenied:
        return True


def cpu_capacity():
    """Respect affinity and visible Linux cgroup CPU quotas where available."""
    try:
        count = len(psutil.Process().cpu_affinity())
    except (AttributeError, psutil.Error):
        count = os.cpu_count() or 1
    if os.name == "posix" and Path('/proc/self/cgroup').exists():
        groups = {}
        for line in Path('/proc/self/cgroup').read_text().splitlines():
            _, controllers, path = line.split(':', 2)
            if not controllers:
                groups['cgroup2'] = path
            elif 'cpu' in controllers.split(','):
                groups['cgroup'] = path
        for line in Path('/proc/self/mountinfo').read_text().splitlines():
            before, after = line.split(' - ', 1)
            fields, options = before.split(), after.split()
            kind = options[0]
            if kind not in groups or (kind == 'cgroup' and 'cpu' not in options[2].split(',')):
                continue
            try:
                relative = Path(groups[kind]).relative_to(fields[3])
            except ValueError:
                continue
            mount = Path(fields[4]); current = mount / relative
            while True:
                try:
                    if kind == 'cgroup2':
                        quota, period = (current / 'cpu.max').read_text().split()
                        if quota != 'max':
                            count = min(count, max(1, math.floor(int(quota) / int(period))))
                    else:
                        quota = int((current / 'cpu.cfs_quota_us').read_text())
                        period = int((current / 'cpu.cfs_period_us').read_text())
                        if quota > 0:
                            count = min(count, max(1, math.floor(quota / period)))
                except FileNotFoundError:
                    pass
                if current == mount:
                    break
                current = current.parent
    return max(1, count)


class HostAdmission:
    def __init__(self, directory=None, *, available_bytes=None, cpu_threads=None):
        self.directory = Path(directory or os.environ.get('BIOPIPE_ADMISSION_DIR') or
                              Path.home() / '.biopipe' / 'admission' / socket.gethostname())
        self.path = self.directory / 'resources.json'
        self.lock = FileLock(self.directory / 'resources.lock')
        self.identity = process_identity()
        self.client = uuid.uuid4().hex
        with self.lock:
            state = self._read()
            self._reconcile(state)
            if not state['clients'] and not state['reservations']:
                capacity_error = None
                if available_bytes is None:
                    from src.task.memory.system import available_memory
                    try:
                        available_bytes = available_memory()
                    except (ImportError, OSError, RuntimeError) as exc:
                        capacity_error = f'Cannot scan host memory capacity: {exc}'
                cpu_warning = None
                if cpu_threads is None:
                    try:
                        cpu_threads = cpu_capacity()
                    except (OSError, ValueError) as exc:
                        # A single worker thread is the conservative fallback;
                        # never assume the host's whole core count in a container.
                        cpu_threads = 1
                        cpu_warning = f'CPU quota unavailable; using one CPU slot: {exc}'
                from src.task.memory.config import AUTO_BUDGET_FRACTION
                state = {'clients': {}, 'reservations': {},
                         'snapshot_at': datetime.now(timezone.utc).isoformat(),
                         'available_at_start_bytes': int(available_bytes) if available_bytes is not None else None,
                         'capacity_bytes': int((available_bytes or 0) * AUTO_BUDGET_FRACTION),
                         'cpu_threads': max(1, cpu_threads), 'capacity_error': capacity_error,
                         'cpu_warning': cpu_warning}
                if state['capacity_bytes'] <= 0:
                    state['capacity_error'] = capacity_error or 'No available memory for the host execution pool'
            state['clients'][self.client] = self.identity
            atomic_json(self.path, state)
        self.capacity = state['capacity_bytes']
        self.cpus = state['cpu_threads']
        self.available_at_start = state['available_at_start_bytes']
        self.capacity_error = state.get('capacity_error')
        self.baseline_bytes = min(self.capacity // 4,
                                  max(256 * MIB, psutil.Process().memory_info().rss * 2))

    def _read(self):
        try:
            return json.loads(self.path.read_text(encoding='utf-8'))
        except FileNotFoundError:
            return {'clients': {}, 'reservations': {}}

    def _reconcile(self, state):
        state['clients'] = {k: v for k, v in state['clients'].items() if process_alive(v)}
        state['reservations'] = {k: v for k, v in state['reservations'].items()
                                 if process_alive(v.get('worker', v['owner']))}

    def request(self, manifest):
        if self.capacity <= 0:
            raise ValueError(self.capacity_error or 'Host memory capacity is unavailable; restart Studio after resolving the scan error')
        memory = manifest.get('runtime', {}).get('memory', {})
        execution = manifest.get('runtime', {}).get('execution', {})
        parallel = execution.get('max_parallel_tasks', 2)
        if isinstance(parallel, bool) or not isinstance(parallel, int) or parallel < 1:
            raise ValueError('execution.max_parallel_tasks must be a positive integer')
        slots = min(self.cpus, parallel)
        def resource(value, default=0):
            return value if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value > 0 else default
        requested_threads = max([1] + [int(resource(step.get('params', {}).get('threads'), 1))
                                       for step in manifest.get('steps', [])])
        enabled = memory.get('enabled', True)
        if not enabled:
            budget, reserved, cpus = 0, self.capacity, self.cpus
        else:
            explicit = memory.get('budget_mb')
            workspace = max([0] + [resource(step.get('params', {}).get('memory_mb'))
                                   for step in manifest.get('steps', [])] +
                            [float(p.get('workspace_mb', 0)) for p in memory.get('profiles', {}).values()])
            if explicit is not None:
                budget = int(float(explicit) * MIB)
                reserved = min(self.capacity, budget + self.baseline_bytes)
            else:
                reserved = max(self.capacity // slots, int(workspace * MIB) + self.baseline_bytes)
                budget = max(1, reserved - self.baseline_bytes)
            cpus = min(self.cpus, max(1, requested_threads))
            if budget > self.capacity or reserved > self.capacity:
                raise ValueError('Requested job memory exceeds the frozen host capacity; lower the budget or workspace')
            if memory.get('process_limit_mb'):
                reserved = max(reserved, int(float(memory['process_limit_mb']) * MIB))
                if reserved > self.capacity:
                    raise ValueError('Requested process limit exceeds the frozen host capacity')
        return {'budget_bytes': budget, 'reserved_bytes': reserved,
                'process_limit_bytes': min(reserved, int(float(memory.get('process_limit_mb', reserved / MIB)) * MIB)),
                'cpu_threads': cpus, 'memory_enabled': enabled,
                'available_at_start_bytes': self.available_at_start,
                'host_capacity_bytes': self.capacity,
                'policy': 'fixed-startup-pool', 'state': 'queued'}

    def reserve(self, key, allocation):
        with self.lock:
            state = self._read(); self._reconcile(state)
            if key in state['reservations']:
                return state['reservations'][key]['client'] == self.client
            used = sum(v['reserved_bytes'] for v in state['reservations'].values())
            cpus = sum(v['cpu_threads'] for v in state['reservations'].values())
            fits = (used + allocation['reserved_bytes'] <= state['capacity_bytes'] and
                    cpus + allocation['cpu_threads'] <= state['cpu_threads'])
            if fits:
                state['reservations'][key] = {**allocation, 'owner': self.identity, 'client': self.client}
            atomic_json(self.path, state)
            return fits

    def started(self, key, pid):
        with self.lock:
            state = self._read()
            entry = state['reservations'][key]
            try:
                entry['worker'] = process_identity(pid)
            except psutil.NoSuchProcess:
                pass  # A very short worker is released by its watcher.
            atomic_json(self.path, state)

    def release(self, key):
        with self.lock:
            state = self._read()
            removed = state['reservations'].pop(key, None)
            atomic_json(self.path, state)
            return removed is not None

    def resources(self):
        with self.lock:
            state = self._read(); self._reconcile(state)
            atomic_json(self.path, state)
            used = sum(v['reserved_bytes'] for v in state['reservations'].values())
            cpu = sum(v['cpu_threads'] for v in state['reservations'].values())
            return {k: state[k] for k in ('snapshot_at', 'available_at_start_bytes', 'capacity_bytes', 'cpu_threads')} | {
                'reserved_bytes': used, 'free_bytes': max(0, state['capacity_bytes'] - used),
                'available_bytes': max(0, state['capacity_bytes'] - used),
                'cpu_capacity': state['cpu_threads'], 'cpu_reserved': cpu,
                'reserved_cpu_threads': cpu, 'free_cpu_threads': max(0, state['cpu_threads'] - cpu),
                'running_jobs': len(state['reservations']), 'active_jobs': len(state['reservations']), 'scope': 'host-user',
                'capacity_error': state.get('capacity_error'),
                'cpu_warning': state.get('cpu_warning'),
                'pressure_policy': 'emergency-spill-then-stop', 'reservations': state['reservations']}

    def close(self):
        with self.lock:
            state = self._read()
            state['clients'].pop(self.client, None)
            self._reconcile(state)
            atomic_json(self.path, state)
