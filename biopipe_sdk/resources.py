"""Resource protocol 1: bounded numeric streams and two-dimensional disk input."""
from typing import Iterator, TypedDict
import math
import numpy as np


class StreamInput(TypedDict):
    shape: tuple[int, ...]
    metadata: dict
    chunks: Iterator[np.ndarray]


class SourceProbe(TypedDict):
    file_bytes: int
    shape: list[int]
    dtype: str
    dense_bytes: int
    preparation_bytes: int


def validate_probe(probe):
    """Validate an allocation promise before the writer allocates disk space."""
    shape = probe.get("shape")
    if not isinstance(shape, (tuple, list)) or len(shape) != 2 or any(type(n) is not int or n < 0 for n in shape):
        raise ValueError("dense-writer-v1 probe.shape must contain two non-negative integer dimensions")
    dtype = np.dtype(probe.get("dtype"))
    if dtype.kind not in "biuf":
        raise ValueError("dense-writer-v1 requires a fixed-width real numeric dtype")
    size = math.prod(shape) * dtype.itemsize
    if type(probe.get("dense_bytes")) is not int or probe["dense_bytes"] != size:
        raise ValueError("probe.dense_bytes must equal product(shape) * dtype.itemsize")
    if type(probe.get("preparation_bytes", size)) is not int or probe.get("preparation_bytes", size) < size:
        raise ValueError("probe.preparation_bytes must include the output and temporary disk storage")
    return probe
