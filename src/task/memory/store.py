"""Whole-Form storage; atomic, bounded-buffer writes and allocation-aware RAM.

Metadata uses pickle ONLY for files created by this run in its private cache.
There is no import-from-cache or cross-run cache API. Never load untrusted
pickle files. Array payloads use numeric .npy, including metadata arrays.
"""
from __future__ import annotations

from collections.abc import MutableMapping
from dataclasses import dataclass, field
import heapq
import os
from pathlib import Path
import pickle
import shutil
import sys
import tempfile
import threading
import uuid

import numpy as np

from src.core import ContextError, Form
from .config import MemoryBudgetError, DiskBudgetError
from .planner import NEVER
from src.core.contracts import VERSION


def footprint(value) -> dict[int, int]:
    """Unique Python objects and backing allocations, without retaining roots."""
    result, todo = {}, [value]
    while todo:
        obj = todo.pop()
        key = id(obj)
        if key in result:
            continue
        if isinstance(obj, np.ndarray):
            if obj.dtype.hasobject:
                raise ContextError("Managed Forms require numeric, non-object arrays")
            result[key] = max(0, sys.getsizeof(obj) - (obj.nbytes if obj.flags.owndata else 0))
            root = obj
            while isinstance(root.base, np.ndarray):
                root = root.base
            allocation = root.base if root.base is not None else root
            allocation_key = id(allocation)
            size = getattr(allocation, "nbytes", None)
            if size is None:
                try:
                    size = memoryview(allocation).nbytes
                except TypeError:
                    size = root.nbytes
            # Buffer key is separate from the Python ndarray header key.
            result[-allocation_key] = max(result.get(-allocation_key, 0), int(size))
        else:
            result[key] = sys.getsizeof(obj)
            if isinstance(obj, dict):
                todo.extend(obj.keys())
                todo.extend(obj.values())
            elif isinstance(obj, (list, tuple, set, frozenset)):
                todo.extend(obj)
            elif hasattr(obj, "__dict__"):
                todo.append(vars(obj))
    return result


@dataclass
class Entry:
    name: str
    generated: int
    key: str = field(default_factory=lambda: uuid.uuid4().hex)
    form: Form | None = None
    loader: object = None
    disk_loader: object = None
    source_probe: dict = field(default_factory=dict)
    source_blocks: dict = field(default_factory=dict)
    source_block_bytes: int = 0
    source_uri: str | None = None
    disk: Path | None = None
    disk_bytes: int = 0
    size: int = 0
    metadata_size: int = 0
    shape: tuple = ()
    dtype: object = None
    refs: dict = field(default_factory=dict)
    pins: int = 0
    heap_version: int = 0
    keep: bool = False


class ArtifactStore(MutableMapping):
    def __init__(self, config, cache_root: Path, event):
        self.config, self.cache_root, self.event = config, cache_root, event
        self.cache_root.mkdir(parents=True, exist_ok=False)
        self.aliases: dict[str, str] = {}
        self.entries: dict[str, Entry] = {}
        self.allocations: dict[int, list[int]] = {}
        self.managed = self.peak_managed = self.disk_bytes = 0
        self.admitted_peak = 0
        self.reserved = 0
        self.position = -1
        self.plan = None
        self.active = False
        self.step_pins = []
        self.heap = []
        self.resident_keys = set()
        self.lock = threading.RLock()
        self.on_output = None

    def __len__(self):
        return len(self.aliases)

    def __iter__(self):
        return iter(tuple(self.aliases))

    def __contains__(self, name):
        return name in self.aliases

    def entry(self, name):
        if name not in self.aliases:
            raise ContextError(f"Form {name!r} is unavailable")
        return self.entries[self.aliases[name]]

    def __getitem__(self, name):
        with self.lock:
            entry = self.entry(name)
            self._load(entry)
            return entry.form

    def __setitem__(self, name, form):
        form.validate()
        with self.lock:
            old = self.entries.get(self.aliases.get(name))
            entry = Entry(name, self.position, form=form)
            entry.keep = name in self.config.keep
            self.entries[entry.key] = entry
            self.aliases[name] = entry.key
            if self.active:
                entry.pins += 1
                self.step_pins.append(entry.key)
            self._account(entry)
            if self.on_output and self.active:
                self.on_output(entry)
            if old and not old.pins:
                self._remove(old)
            self.refresh(entry)
            self.event("artifact_registered", **self.describe(entry))
            self.ensure(0, "actual_output_size")

    def __delitem__(self, name):
        with self.lock:
            entry = self.entry(name)
            if entry.pins:
                raise ContextError("Cannot delete a pinned input/output")
            self._remove(entry)

    def register_source(self, name, loader, uri, probe=None, disk_loader=None):
        with self.lock:
            entry = Entry(name, -1, loader=loader, source_uri=str(uri), keep=name in self.config.keep)
            entry.source_probe = probe or {}
            entry.disk_loader = disk_loader
            entry.size = int(entry.source_probe.get("dense_bytes") or 0)
            self.entries[entry.key] = entry
            self.aliases[name] = entry.key
            self.event("source_registered", name=name, source_uri=str(uri), storage="source", **entry.source_probe)

    def stage_source(self, entry):
        """Complete bounded source preparation before operator admission."""
        if entry.disk is not None or entry.disk_loader is None:
            return
        from src.reader.disk import DenseDiskWriter
        temporary = Path(tempfile.mkdtemp(prefix=".source-", dir=self.cache_root))
        writer = None
        try:
            required = int(entry.source_probe.get("preparation_bytes", entry.source_probe["dense_bytes"])) + 512
            if self.config.disk_limit_bytes is not None and self.disk_bytes + required > self.config.disk_limit_bytes:
                raise DiskBudgetError("Dense source exceeds disk quota before allocation")
            if shutil.disk_usage(self.cache_root).free < required:
                raise DiskBudgetError("Insufficient disk space for dense source")
            # Leave room for parser blocks and Python axis metadata. No second
            # system-available scan: this derives from the frozen run budget.
            chunk = max(4, min(self.config.chunk_bytes, self.config.budget_bytes // 8))
            reservation = min(self.config.budget_bytes, chunk * 4)
            self.ensure(reservation, "source_staging")
            self.event("source_prepare_started", name=entry.name, chunk_bytes=chunk,
                       buffer_budget_bytes=chunk * 2, **entry.source_probe)
            process = None
            if self.config.process_limit_bytes and self.config.auto_spill:
                import psutil
                process = psutil.Process()
            writer = DenseDiskWriter(temporary / "data.npy", entry.source_probe["shape"],
                                     entry.source_probe["dtype"], block_bytes=min(chunk, self.config.io_buffer_bytes),
                                     budget_bytes=chunk * 2, event=self.event,
                                     pressure=lambda: bool(process and process.memory_info().rss >
                                         self.config.process_limit_bytes * self.config.spill_fraction))
            metadata = entry.disk_loader(writer, chunk)
            writer.close(retain=True)
            peak = writer.peak_bytes
            blocks, block_bytes = writer.blocks, writer.block_bytes
            writer = None
            # Validation examines shape, dtype and annotations, without allocating
            # a dense placeholder. These readers declare no value-level contracts.
            shape = tuple(entry.source_probe["shape"])
            dtype = np.dtype(entry.source_probe["dtype"])
            placeholder = np.broadcast_to(np.zeros((), dtype=dtype), shape)
            Form(placeholder, **metadata).validate()
            metadata_size = sum(footprint(metadata).values())
            self.ensure(metadata_size + sum(map(len, blocks.values())), "source_metadata")
            with open(temporary / "metadata.pkl", "wb") as file:
                pickle.dump(metadata, file, protocol=5)
            written = sum(p.stat().st_size for p in temporary.iterdir())
            if self.config.disk_limit_bytes is not None and self.disk_bytes + written > self.config.disk_limit_bytes:
                raise DiskBudgetError("Dense source metadata exceeds disk quota")
            final = self.cache_root / entry.key
            os.replace(temporary, final)
            entry.disk, entry.disk_bytes = final, written
            entry.shape, entry.dtype, entry.metadata_size = shape, dtype, metadata_size
            entry.size = int(entry.source_probe["dense_bytes"]) + metadata_size + 8192
            self.disk_bytes += written
            entry.source_blocks, entry.source_block_bytes = blocks, block_bytes
            self.managed += sum(len(block) for block in blocks.values())
            self.peak_managed = max(self.peak_managed, self.managed)
            self.resident_keys.add(entry.key)
            self.refresh(entry)
            self.event("source_prepare_complete", buffer_peak_bytes=peak, **self.describe(entry))
        except BaseException:
            if writer is not None and not writer.file.closed:
                # Failure discards the staging copy; do not flush more blocks.
                writer.file.close()
            self._delete_folder(temporary)
            raise

    def trim_source_blocks(self, entry, bytes_to_free, reason):
        """Drop only as many clean staging blocks as subsequent admission needs."""
        released = 0
        while entry.source_blocks and released < bytes_to_free:
            key = next(iter(entry.source_blocks))
            released += len(entry.source_blocks.pop(key))
        self.managed -= released
        if released:
            self.event("source_blocks_released", name=entry.name, bytes=released, reason=reason,
                       retained_bytes=sum(map(len, entry.source_blocks.values())))
        if entry.form is None and not entry.source_blocks:
            self.resident_keys.discard(entry.key)
        return released

    def _account(self, entry):
        # Managed numeric payloads are immutable while registered. Operators
        # create new Forms; a same-name output gets a new version and cache URI.
        entry.form.data.setflags(write=False)
        self._unaccount(entry)
        entry.refs = footprint(entry.form)
        entry.size = sum(entry.refs.values())
        entry.shape, entry.dtype = entry.form.data.shape, entry.form.data.dtype
        payload = {k: getattr(entry.form, k) for k in ("dims", "labels", "info", "axis_info")}
        entry.metadata_size = sum(footprint(payload).values())
        for key, size in entry.refs.items():
            record = self.allocations.get(key)
            if record is None:
                self.allocations[key] = [size, 1]
                self.managed += size
            else:
                if size != record[0]:
                    self.managed += size - record[0]
                    record[0] = size
                record[1] += 1
        self.resident_keys.add(entry.key)
        self.peak_managed = max(self.peak_managed, self.managed)

    def _unaccount(self, entry):
        for key in entry.refs:
            record = self.allocations[key]
            record[1] -= 1
            if not record[1]:
                self.managed -= record[0]
                del self.allocations[key]
        entry.refs = {}
        self.resident_keys.discard(entry.key)

    def refresh(self, entry):
        entry.heap_version += 1
        if entry.form is not None or entry.source_blocks:
            next_use = self.plan.next_use(entry.name, self.position, entry.generated) if self.plan else NEVER
            heapq.heappush(self.heap, (-next_use, -entry.size, entry.heap_version, entry.key))
        if len(self.heap) > 2 * len(self.resident_keys) + 64:
            self.heap = [(-(self.plan.next_use(e.name, self.position, e.generated) if self.plan else NEVER),
                          -e.size, e.heap_version, e.key)
                         for key in self.resident_keys for e in (self.entries[key],)]
            heapq.heapify(self.heap)

    def pin(self, names):
        with self.lock:
            self.active = True
            for name in dict.fromkeys(names):
                entry = self.entry(name)
                entry.pins += 1
                self.step_pins.append(entry.key)

    def end_step(self):
        with self.lock:
            self.reserved = 0
            for key in self.step_pins:
                if key in self.entries:
                    entry = self.entries[key]
                    entry.pins -= 1
                    if entry.form is not None:
                        self._account(entry)
                    self.refresh(entry)
            self.step_pins.clear()
            self.active = False
            # Only touched objects need reevaluation; no full alive-set scan.
            # Entries queued below were inputs/outputs of this step.

    def release_finished(self, keys):
        with self.lock:
            for key in dict.fromkeys(keys):
                entry = self.entries.get(key)
                if entry is None or entry.pins:
                    continue
                current = self.aliases.get(entry.name) == key
                future = current and self.plan.next_use(entry.name, self.position, entry.generated) != NEVER
                if not current or (not future and not entry.keep):
                    self.event("last_use_release", **self.describe(entry))
                    self._remove(entry)
            self.ensure(0, "step_boundary")

    def _load(self, entry):
        if entry.form is not None:
            return
        self.stage_source(entry)
        self.trim_source_blocks(entry, float("inf"), "full_mode_admission")
        self.ensure(entry.size, "load_reservation")
        if entry.disk is not None:
            payload = self.read_metadata(entry)
            data = np.load(entry.disk / "data.npy", allow_pickle=False)
            if data.shape != entry.shape or data.dtype != entry.dtype:
                raise ContextError("Cache descriptor/header mismatch")
            entry.form = Form(data=data, **payload)
            entry.form.validate()
            self.event("load", name=entry.name, artifact_id=entry.key, disk_uri=str(entry.disk))
        elif entry.loader is not None:
            entry.form = entry.loader()
            entry.form.validate()
            self.event("source_loaded", name=entry.name, artifact_id=entry.key,
                       source_uri=entry.source_uri)
        else:
            raise ContextError(f"No valid copy of {entry.name!r}")
        self._account(entry)
        self.refresh(entry)
        self.event("size_observed", **self.describe(entry))
        self.ensure(0, "actual_input_size")

    def ensure(self, extra, reason):
        target = self.config.budget_bytes - self.reserved - extra
        if target < 0:
            raise MemoryBudgetError(f"Reservation exceeds managed budget: {reason}")
        if self.managed <= target:
            self.admitted_peak = max(self.admitted_peak, self.managed + self.reserved + extra)
            return
        if not self.config.auto_spill:
            raise MemoryBudgetError(f"Managed memory requires {self.managed + self.reserved + extra} bytes; budget={self.config.budget_bytes}")
        self.evict_to(target, reason)
        if self.managed > target:
            raise MemoryBudgetError(f"Pinned inputs/output plus workspace cannot fit: required>={self.managed + self.reserved + extra}, budget={self.config.budget_bytes}, reason={reason}")
        self.admitted_peak = max(self.admitted_peak, self.managed + self.reserved + extra)

    def evict_to(self, target, reason):
        """Skip pinned entries; restore heap entries before doing compaction."""
        skipped = []
        spill_failure = None
        try:
            while self.managed > max(0, target) and self.heap:
                item = heapq.heappop(self.heap)
                _, _, version, key = item
                entry = self.entries.get(key)
                if entry is None or (entry.form is None and not entry.source_blocks) or entry.heap_version != version:
                    continue
                if entry.pins:
                    skipped.append(item)
                    continue
                try:
                    if entry.source_blocks:
                        self.trim_source_blocks(entry, self.managed - max(0, target), reason)
                        if entry.source_blocks:
                            self.refresh(entry)
                    else:
                        self.spill(entry, reason)
                except (DiskBudgetError, OSError) as exc:
                    # A different victim may already have a durable copy and
                    # can be evicted without consuming additional disk quota.
                    spill_failure = exc
                    skipped.append(item)
                except BaseException:
                    skipped.append(item)
                    raise
        finally:
            for item in skipped:
                heapq.heappush(self.heap, item)
        if spill_failure is not None and self.managed > max(0, target):
            raise spill_failure

    def spill(self, entry, reason, preparing_stream=False):
        with self.lock:
            if entry.form is None:
                return
            if entry.pins and not preparing_stream:
                raise ContextError("Cannot spill a pinned running input")
            if entry.disk is None:
                self._commit(entry)
            self._unaccount(entry)
            entry.form = None
            entry.heap_version += 1
            self.event("spill", reason=reason, **self.describe(entry))

    def _commit(self, entry):
        # Exclusive short temporary names avoid a needless 32-character UUID
        # pushing otherwise valid Windows cache paths over MAX_PATH.
        temporary = Path(tempfile.mkdtemp(prefix=".pending-", dir=self.cache_root))
        final = self.cache_root / entry.key
        written = [0]
        store = self

        class Writer:
            def __init__(self, path):
                self.file = open(path, "wb")
            def write(self, data):
                if store.config.disk_limit_bytes is not None and store.disk_bytes + written[0] + len(data) > store.config.disk_limit_bytes:
                    raise DiskBudgetError("Spill quota exhausted; original RAM copy retained")
                n = self.file.write(data)
                if n != len(data):
                    raise OSError("Short cache write; original RAM copy retained")
                written[0] += n
                return n
            def flush(self):
                self.file.flush()
            def close(self):
                try:
                    self.file.flush()
                    os.fsync(self.file.fileno())
                finally:
                    self.file.close()

        def array_file(array, filename):
            if array.dtype.hasobject:
                raise ContextError("Object dtype cannot be spilled")
            writer = Writer(temporary / filename)
            try:
                np.lib.format.write_array_header_2_0(writer, {
                    "descr": np.lib.format.dtype_to_descr(array.dtype),
                    "fortran_order": False, "shape": array.shape})
                elements = max(1, self.config.io_buffer_bytes // max(1, array.dtype.itemsize))
                with np.nditer(array, flags=["external_loop", "buffered", "zerosize_ok"],
                               op_flags=["readonly"], order="C", buffersize=elements) as chunks:
                    for chunk in chunks:
                        writer.write(chunk.tobytes())
            finally:
                writer.close()

        arrays, array_bytes = {}, [entry.form.data.nbytes]
        class MetadataPickler(pickle.Pickler):
            def persistent_id(self, obj):
                if isinstance(obj, np.ndarray):
                    if id(obj) not in arrays:
                        filename = f"info-{len(arrays)}.npy"
                        array_file(obj, filename)
                        arrays[id(obj)] = filename
                        array_bytes[0] += obj.nbytes
                    return ("ndarray", arrays[id(obj)])
                return None

        try:
            array_file(entry.form.data, "data.npy")
            writer = Writer(temporary / "metadata.pkl")
            try:
                payload = {k: getattr(entry.form, k) for k in ("dims", "labels", "info", "axis_info")}
                MetadataPickler(writer, protocol=5).dump(payload)
            finally:
                writer.close()
            os.replace(temporary, final)
            entry.disk, entry.disk_bytes = final, written[0]
            # Reload can break array sharing, so reserve the serialized array sum.
            metadata_headers = sum(size for key, size in footprint(payload).items() if key >= 0)
            entry.size = max(entry.size, array_bytes[0] + metadata_headers)
            self.disk_bytes += written[0]
            self.event("disk_commit", **self.describe(entry))
        except BaseException:
            self._delete_folder(temporary)
            raise

    def read_metadata(self, entry):
        directory = entry.disk
        class MetadataUnpickler(pickle.Unpickler):
            def persistent_load(self, pid):
                kind, filename = pid
                if kind != "ndarray" or Path(filename).name != filename:
                    raise ContextError("Invalid run-local array reference")
                return np.load(directory / filename, allow_pickle=False)
        with open(directory / "metadata.pkl", "rb") as file:
            return MetadataUnpickler(file).load()

    def chunks(self, entry, elements):
        """No mmap residency or full-array copies; .npy is canonical C order."""
        if entry.form is not None:
            with np.nditer(entry.form.data, flags=["external_loop", "buffered", "zerosize_ok"],
                           op_flags=["readonly"], order="C", buffersize=elements) as chunks:
                for chunk in chunks:
                    yield chunk
        else:
            with open(entry.disk / "data.npy", "rb") as file:
                version = np.lib.format.read_magic(file)
                if version != (2, 0):
                    raise ContextError("Unexpected cache array format")
                shape, fortran, dtype = np.lib.format.read_array_header_2_0(file)
                if fortran or dtype.hasobject or shape != entry.shape or dtype != entry.dtype:
                    raise ContextError("Cache descriptor/header mismatch")
                remaining = int(np.prod(shape, dtype=np.int64))
                position = 0
                while remaining:
                    count = min(elements, remaining)
                    cached = None
                    if entry.source_block_bytes:
                        key, offset = divmod(position * dtype.itemsize, entry.source_block_bytes)
                        count = min(count, (entry.source_block_bytes - offset) // dtype.itemsize)
                        cached = entry.source_blocks.get(key)
                    if cached is not None:
                        chunk = np.frombuffer(cached, dtype=dtype, count=count, offset=offset)
                        chunk.setflags(write=False)
                        file.seek(count * dtype.itemsize, 1)
                    else:
                        chunk = np.fromfile(file, dtype=dtype, count=count)
                    if chunk.size != count:
                        raise ContextError("Truncated cache payload")
                    yield chunk
                    remaining -= count
                    position += count

    def _delete_folder(self, folder):
        folder = folder.resolve()
        if folder.parent != self.cache_root.resolve():
            raise ContextError("Refusing to remove a path outside this run's cache")
        if folder.exists():
            shutil.rmtree(folder)

    def _remove(self, entry):
        self.trim_source_blocks(entry, float("inf"), "last_use")
        self._unaccount(entry)
        entry.form = None
        if entry.disk:
            self._delete_folder(entry.disk)
            self.disk_bytes -= entry.disk_bytes
        if self.aliases.get(entry.name) == entry.key:
            del self.aliases[entry.name]
        self.entries.pop(entry.key, None)

    def describe(self, entry):
        next_use = self.plan.next_use(entry.name, self.position, entry.generated) if self.plan else NEVER
        return {"name": entry.name, "artifact_id": entry.key,
                "producer_step": entry.generated + 1 if entry.generated >= 0 else None,
                "next_use_step": next_use + 1 if next_use != NEVER else None,
                "shape": list(entry.shape), "dtype": str(entry.dtype),
                "contract_version": VERSION,
                "ram_estimate_bytes": entry.size, "disk_bytes": entry.disk_bytes,
                "cached_source_bytes": sum(map(len, entry.source_blocks.values())),
                "storage": "ram" if entry.form is not None else "disk" if entry.disk else "source",
                "disk_uri": str(entry.disk) if entry.disk else None,
                "source_uri": entry.source_uri, "pins": entry.pins}
