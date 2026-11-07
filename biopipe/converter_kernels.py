"""Portable conversion kernels; depends only on NumPy and the standard library.

Logical metadata is supplied by the caller and is never reinterpreted here.
"""
from pathlib import Path
import os


def array_to_npy(data, path, *, buffer_bytes=65536, checkpoint=lambda: None):
    import numpy as np
    if data.dtype.hasobject:
        raise ValueError('Object arrays are not a lossless portable numeric format')
    path = Path(path)
    partial = path.with_suffix(path.suffix + '.partial')
    import io
    header = io.BytesIO()
    np.lib.format.write_array_header_2_0(header, {
        'descr': np.lib.format.dtype_to_descr(data.dtype), 'fortran_order': False, 'shape': data.shape})
    try:
        with partial.open('wb') as target:
            target.write(header.getvalue())
            with np.nditer(data, flags=['external_loop', 'buffered', 'zerosize_ok'],
                           op_flags=['readonly'], order='C',
                           buffersize=max(1, buffer_bytes // max(1, data.dtype.itemsize))) as blocks:
                for block in blocks:
                    checkpoint()
                    target.write(block.tobytes())
            target.flush()
            os.fsync(target.fileno())
        os.replace(partial, path)
        return np.load(path, allow_pickle=False, mmap_mode='r')
    finally:
        partial.unlink(missing_ok=True)


def mmap_to_array(data):
    import numpy as np
    # ndarray view over the existing mapping, not a new full in-memory copy.
    value = np.asarray(data).view()
    value.flags.writeable = False
    return value
