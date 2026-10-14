"""Resource admission, adaptive metadata and redundant RSS spill monitor."""
from __future__ import annotations

from collections import Counter
import gc
import json
import hashlib
import os
from pathlib import Path
import threading
import time

from src.core import ManifestError
from biopipe.run_log import RunLog
from .config import DiskBudgetError, MemoryBudgetError
from .planner import LifetimePlan, NEVER, block_elements, full_estimate
from .store import ArtifactStore


class MemoryRuntime:
    def __init__(self, config, out_dir, manifest, run_log=None):
        self.config, self.out_dir = config, Path(out_dir)
        self.run_log = run_log or RunLog(self.out_dir)
        self.run_id, self.run_dir = self.run_log.run_id, self.run_log.run_dir
        self.event_path = self.run_log.event_path
        self.log, self.log_lock = self.run_log.stream, self.run_log.lock
        self.counts = Counter()
        self.rss_peak = 0
        self.step_rss_peak = 0
        self.status = "created"
        self.failure = None
        self.observed_workspace = {}
        self.remaining_output = 0
        self.workspace = 0
        self.plan = None
        self.plan_records = []
        self.fault = None
        self._closed = False
        self._stop = threading.Event()
        self._thread = None
        try:
            import psutil
            self.process = psutil.Process()
        except ImportError:
            self.process = None
        if config.process_limit_bytes and self.process is None:
            raise ManifestError("process_limit_mb requires psutil")
        if config.cache_dir:
            base = Path(config.cache_dir)
            if not base.is_absolute():
                base = self.out_dir.parent / base
            cache_root = base.resolve() / self.run_id
        else:
            # run_dir already isolates this run; avoid repeating the run ID,
            # which also needlessly approaches Windows path-length limits.
            cache_root = self.run_dir / "cache"
        self.store = ArtifactStore(config, cache_root, self.event)
        self.store.on_output = self._output_registered
        snapshot = json.dumps(manifest, indent=2, ensure_ascii=False)
        self.pipeline_hash = hashlib.sha256(snapshot.encode("utf-8")).hexdigest()
        (self.run_dir / "pipeline.json").write_text(snapshot, encoding="utf-8")
        self.event("run_started", run_id=self.run_id, budget_bytes=config.budget_bytes,
                   available_at_start_bytes=config.available_at_start_bytes,
                   process_limit_bytes=config.process_limit_bytes, cache_dir=str(cache_root),
                   algorithm="fixed-order-next-use-heap", optimality="heuristic",
                   pipeline_sha256=self.pipeline_hash)

    def event(self, action, **details):
        with self.log_lock:
            self.counts[action] += 1
            if not self._closed:
                self.run_log.event(action, **details)

    def configure(self, steps, registry):
        start = time.perf_counter()
        self.plan = LifetimePlan(steps, registry)
        self.store.plan = self.plan
        known = set(self.store.aliases) | set(self.plan.producers)
        missing = set(self.config.keep) - known
        if missing:
            raise ManifestError(f"Unknown memory.keep Forms: {sorted(missing)}")
        sinks = {name for name, positions in self.plan.producers.items()
                 if self.plan.next_use(name, positions[-1], positions[-1]) == NEVER}
        for entry in self.store.entries.values():
            entry.keep |= entry.name in sinks
            self.store.refresh(entry)
        self.sinks = sinks
        self.event("plan_compiled", steps=len(steps), references=sum(map(len, self.plan.uses.values())),
                   seconds=time.perf_counter() - start, retained_outputs=sorted(sinks | set(self.config.keep)))
        # Startup discovery updates a durable directory; no scanning per step.
        from src.task.operator_catalog import build_catalog
        catalog = build_catalog(registry)
        directory = self.out_dir / "operators.json"
        temporary = self.out_dir / (".operators-" + self.run_id + ".tmp")
        temporary.write_text(json.dumps(catalog, indent=2), encoding="utf-8")
        os.replace(temporary, directory)
        self.status = "running"
        self._sample()
        if self.config.auto_spill:
            self._thread = threading.Thread(target=self._monitor, name="biopipe-spill-monitor", daemon=True)
            self._thread.start()

    def _output_registered(self, entry):
        entry.keep |= entry.name in getattr(self, "sinks", set())
        self.remaining_output = max(0, self.remaining_output - entry.size)
        self.store.reserved = self.workspace + self.remaining_output

    def _sample(self):
        rss = self.process.memory_info().rss if self.process else 0
        self.rss_peak = max(self.rss_peak, rss)
        self.step_rss_peak = max(self.step_rss_peak, rss)
        return rss

    def emergency_spill(self, reason="rss_pressure"):
        """Drop only unpinned cache; failure preserves the original copy."""
        with self.store.lock:
            rss = self._sample()
            target = int(self.config.budget_bytes * self.config.target_fraction)
            if self.config.process_limit_bytes:
                target = min(target, max(0, self.store.managed - max(0, rss - int(self.config.process_limit_bytes * self.config.target_fraction))))
            before = self.store.managed
            self.store.evict_to(target, reason)
            self.event("emergency_spill", reason=reason, rss_bytes=rss,
                       managed_before=before, managed_after=self.store.managed,
                       pinned_or_shared_bytes=self.store.managed)
            return before - self.store.managed

    def _monitor(self):
        pressure = False
        last_attempt = 0.0
        while not self._stop.wait(self.config.poll_seconds):
            try:
                rss = self._sample()
                managed_pressure = self.store.managed > self.config.budget_bytes * self.config.spill_fraction
                rss_pressure = bool(self.config.process_limit_bytes and rss > self.config.process_limit_bytes * self.config.spill_fraction)
                if (managed_pressure or rss_pressure) and (not pressure or time.monotonic() - last_attempt >= .25):
                    self.emergency_spill("rss_pressure" if rss_pressure else "managed_pressure")
                    pressure = True
                    last_attempt = time.monotonic()
                elif not managed_pressure and not rss_pressure:
                    pressure = False
            except (DiskBudgetError, OSError) as exc:
                # Soft pressure is redundant protection. Keep the valid RAM
                # copy and retry later; strict dispatch admission still fails
                # if the next operator cannot fit without a successful spill.
                self.event("spill_blocked", error_type=type(exc).__name__, message=str(exc))
                pressure = True
                last_attempt = time.monotonic()
            except Exception as exc:
                self.fault = exc
                self.event("monitor_failure", error_type=type(exc).__name__, message=str(exc))
                return

    def _barrier(self):
        if self.fault:
            raise self.fault
        rss = self._sample()
        if self.config.process_limit_bytes and rss > self.config.process_limit_bytes:
            if self.config.auto_spill:
                self.emergency_spill()
                gc.collect()
                rss = self._sample()
            if rss > self.config.process_limit_bytes:
                raise MemoryBudgetError(f"Process RSS {rss} exceeds process_limit={self.config.process_limit_bytes}; dispatch paused")

    def prepare(self, index, spec, cls):
        self._barrier()
        self.store.position = index
        self.store.pin(spec.get("inputs", []))
        self.step_rss_peak = self._sample()
        self.step_rss_start = self.step_rss_peak
        start = time.perf_counter()
        can_stream = getattr(cls, "supports_streaming", False) and len(spec.get("inputs", [])) == 1
        if can_stream:
            entry = self.store.entry(spec["inputs"][0])
            with self.store.lock:
                if entry.form is None and entry.disk is None:
                    self.store.stage_source(entry)
                    if entry.disk is None:
                        self.store._load(entry)
                can_stream = entry.dtype.kind in "biuf"
        if can_stream:
            entry = self.store.entry(spec["inputs"][0])
            with self.store.lock:
                if entry.form is None and entry.disk is None:
                    self.store._load(entry)  # Legacy readers without a disk preparation protocol.
                metadata_reserve = int(entry.metadata_size * 2.50) + 8192 + cls.stream_fixed_bytes
                pinned = entry.size if entry.form is not None else 0
                elements = block_elements(self.config.budget_bytes - pinned - metadata_reserve,
                                          entry.dtype, self.config.chunk_bytes, cls.stream_buffer_multiplier)
                if not elements and entry.form is not None and self.config.auto_spill:
                    self.store.spill(entry, "prepare_stream", preparing_stream=True)
                    elements = block_elements(self.config.budget_bytes - metadata_reserve,
                                              entry.dtype, self.config.chunk_bytes, cls.stream_buffer_multiplier)
                if not elements:
                    raise MemoryBudgetError("Stream metadata plus minimum block cannot fit the managed budget")
                chunk_reservation = elements * (max(entry.dtype.itemsize, 8) * cls.stream_buffer_multiplier + 1)
                self.workspace, self.remaining_output = metadata_reserve + chunk_reservation, 0
                self.store.reserved = self.workspace
                excess = self.store.managed + self.store.reserved - self.config.budget_bytes
                if excess > 0:
                    self.store.trim_source_blocks(entry, excess, "stream_admission")
                self.store.ensure(0, "stream_admission")
                metadata = ({k: getattr(entry.form, k) for k in ("dims", "labels", "info", "axis_info")}
                            if entry.form is not None else self.store.read_metadata(entry))
                plan = {"index": index + 1, "name": spec["name"], "mode": "stream",
                        "chunk_elements": elements, "chunk_bytes": elements * entry.dtype.itemsize,
                        "workspace_estimate_bytes": self.workspace, "output_estimate_bytes": 0,
                        "planning_seconds": time.perf_counter() - start}
                stream = {"metadata": metadata, "shape": entry.shape,
                          "chunks": self.store.chunks(entry, elements)}
                self.plan_records.append(plan)
                self.event("step_plan", **plan)
                self.step_rss_start = self.step_rss_peak = self._sample()
                return [], stream

        forms = [self.store[name] for name in spec.get("inputs", [])]
        workspace, output = cls.estimate_memory(forms, spec.get("params", {}), self.config.profiles)
        if any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in (workspace, output)):
            raise ValueError(f"{spec['name']}: estimate_memory must return two non-negative integer byte counts")
        workspace = max(workspace, self.observed_workspace.get(spec["name"], 0))
        self.workspace, self.remaining_output = workspace, output
        self.store.reserved = workspace + output
        self.store.ensure(0, "full_step_admission")
        self._barrier()
        plan = {"index": index + 1, "name": spec["name"], "mode": "full",
                "workspace_estimate_bytes": workspace, "output_estimate_bytes": output,
                "planning_seconds": time.perf_counter() - start}
        self.plan_records.append(plan)
        self.event("step_plan", **plan)
        self.step_rss_start = self.step_rss_peak = self._sample()
        return forms, None

    def finish(self, spec, elapsed):
        self._sample()
        observed = max(0, self.step_rss_peak - self.step_rss_start)
        # Conservative observation, including outputs/allocator effects. Not a
        # causal measurement or certified bound for the operator's workspace.
        self.observed_workspace[spec["name"]] = max(self.observed_workspace.get(spec["name"], 0), observed)
        touched = list(self.store.step_pins)
        self.store.end_step()
        self.store.release_finished(touched)
        self.event("step_finished", name=spec["name"], elapsed=elapsed,
                   rss_peak_bytes=self.step_rss_peak, observed_extra_rss_bytes=observed,
                   managed_bytes=self.store.managed)
        self._barrier()

    def abort_step(self):
        self.store.end_step()

    def update_budget(self, budget_bytes):
        if isinstance(budget_bytes, bool) or not isinstance(budget_bytes, int) or budget_bytes <= 0:
            raise ValueError("budget_bytes must be a positive integer")
        with self.store.lock:
            if self.store.active:
                raise MemoryBudgetError("Budget changes are accepted only at a task boundary")
            old = self.config.budget_bytes
            self.config.budget_bytes = budget_bytes
            try:
                self.store.ensure(0, "budget_changed")
            except BaseException:
                self.config.budget_bytes = old
                self.event("budget_change_blocked", old_bytes=old, requested_bytes=budget_bytes)
                raise
            self.event("budget_changed", old_bytes=old, new_bytes=budget_bytes)

    def close(self, status="complete", error=None):
        if self._closed:
            return self.report
        self._stop.set()
        if self._thread:
            self._thread.join()
        self.failure = str(error) if error else None
        self.status = status
        with self.store.lock:
            if status == "complete":
                for entry in list(self.store.entries.values()):
                    if entry.keep:
                        self.store.spill(entry, "final_output")
            self._sample()
            self.event("run_finished", status=status, error=self.failure)
            self.report = {"run_id": self.run_id, "status": status, "error": self.failure,
                           "pipeline_sha256": self.pipeline_hash,
                           "budget_bytes": self.config.budget_bytes,
                           "available_at_start_bytes": self.config.available_at_start_bytes,
                           "process_limit_bytes": self.config.process_limit_bytes,
                           "managed_peak_bytes": self.store.peak_managed,
                           "admitted_peak_estimate_bytes": self.store.admitted_peak,
                           "sampled_rss_peak_bytes": self.rss_peak,
                           "disk_bytes": self.store.disk_bytes,
                           "event_counts": dict(self.counts), "plans": self.plan_records,
                           "event_log": str(self.event_path),
                           "artifacts": [self.store.describe(e) for e in self.store.entries.values()],
                           "guarantee": "estimated admission and sampled feedback; no hard RSS guarantee"}
            (self.run_dir / "memory_report.json").write_text(json.dumps(self.report, indent=2), encoding="utf-8")
            with self.log_lock:
                self._closed = True
                self.run_log.close()
        return self.report
