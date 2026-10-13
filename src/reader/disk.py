"""Bounded writes into one C-order NPY file; no full-array concatenation/mmap."""
import math
import os
from collections import OrderedDict
from contextlib import contextmanager
from pathlib import Path

import numpy as np

from src.core import ReaderError


class DenseDiskWriter:
    def __init__(self, path, shape, dtype=np.float32, *, block_bytes=4 * 1024**2,
                 budget_bytes=16 * 1024**2, pressure=None, event=None):
        self.shape, self.dtype = tuple(shape), np.dtype(dtype)
        self.path = Path(path)
        self.block_bytes = max(self.dtype.itemsize, (min(block_bytes, budget_bytes) // self.dtype.itemsize) * self.dtype.itemsize)
        self.budget_bytes = max(self.block_bytes, budget_bytes)
        self.blocks = OrderedDict()
        self.pressure, self.event = pressure, event or (lambda *a, **k: None)
        self.peak_bytes = 0
        self.file = open(path, "w+b")
        np.lib.format.write_array_header_2_0(self.file, {
            "descr": np.lib.format.dtype_to_descr(self.dtype),
            "fortran_order": False, "shape": self.shape})
        self.offset = self.file.tell()
        self.file.truncate(self.offset + math.prod(self.shape) * self.dtype.itemsize)

    def _evict(self, reason):
        key, block = self.blocks.popitem(last=False)
        self.file.seek(self.offset + key * self.block_bytes)
        remaining = math.prod(self.shape) * self.dtype.itemsize - key * self.block_bytes
        self.file.write(memoryview(block)[:min(remaining, len(block))])
        self.event("densify_block_spill", reason=reason, block=key, bytes=len(block))

    def _block(self, position):
        key = position // self.block_bytes
        if self.pressure and self.pressure():
            while self.blocks:
                self._evict("rss_pressure")
        if key not in self.blocks:
            while self.blocks and (len(self.blocks) + 1) * self.block_bytes > self.budget_bytes:
                self._evict("buffer_watermark")
            self.file.seek(self.offset + key * self.block_bytes)
            block = bytearray(self.file.read(self.block_bytes))
            block.extend(bytes(self.block_bytes - len(block)))
            self.blocks[key] = block
            self.peak_bytes = max(self.peak_bytes, len(self.blocks) * self.block_bytes)
        self.blocks.move_to_end(key)
        return self.blocks[key], position % self.block_bytes

    def write(self, row, column, values):
        values = np.asarray(values, dtype=self.dtype).reshape(-1)
        if not (0 <= row < self.shape[0] and 0 <= column <= self.shape[1]
                and column + values.size <= self.shape[1]):
            raise ReaderError("Matrix block lies outside declared shape")
        position = (row * self.shape[1] + column) * self.dtype.itemsize
        raw = memoryview(values).cast("B")
        while raw:
            block, offset = self._block(position)
            count = min(len(raw), len(block) - offset)
            block[offset:offset + count] = raw[:count]
            position += count
            raw = raw[count:]

    def add(self, row, column, value):
        if not (0 <= row < self.shape[0] and 0 <= column < self.shape[1]):
            raise ReaderError("Matrix coordinate lies outside declared shape")
        position = (row * self.shape[1] + column) * self.dtype.itemsize
        block, offset = self._block(position)
        cell = np.frombuffer(block, dtype=self.dtype, count=1, offset=offset)
        cell[0] += value

    def close(self, retain=False):
        if self.file.closed:
            return
        try:
            if retain:
                for key, block in self.blocks.items():
                    self.file.seek(self.offset + key * self.block_bytes)
                    remaining = math.prod(self.shape) * self.dtype.itemsize - key * self.block_bytes
                    self.file.write(memoryview(block)[:min(remaining, len(block))])
            else:
                while self.blocks:
                    self._evict("phase_handoff")
            self.file.flush()
            os.fsync(self.file.fileno())
        finally:
            self.file.close()


@contextmanager
def accumulator(target, dtype, chunk_bytes):
    """Sum duplicate coordinates at source precision, then cast in bounded rows."""
    path = target.path.with_name('accumulator.npy')
    work = DenseDiskWriter(path, target.shape, dtype,
                           block_bytes=target.block_bytes, budget_bytes=target.budget_bytes,
                           pressure=target.pressure, event=target.event)
    try:
        yield work
        work.close()
        with path.open('rb') as source:
            np.lib.format.read_magic(source)
            np.lib.format.read_array_header_2_0(source)
            width = max(1, chunk_bytes // max(16, np.dtype(dtype).itemsize * 2))
            for row in range(target.shape[0]):
                for column in range(0, target.shape[1], width):
                    count = min(width, target.shape[1] - column)
                    values = np.fromfile(source, dtype=dtype, count=count)
                    if len(values) != count:
                        raise ReaderError('Truncated source accumulator')
                    target.write(row, column, values)
    finally:
        if not work.file.closed:
            work.file.close()
        path.unlink(missing_ok=True)
