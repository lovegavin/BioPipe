"""Version-neutral local IPC: tagged JSON metadata and bounded NPY files.

Never pickle dependency-owned objects between different dependency versions.
Unsupported metadata fails explicitly instead of losing information.
"""
import json
import io
import math
from pathlib import Path
import uuid

import numpy as np


class Wire:
    def __init__(self, directory, *, buffer_bytes=65536, admit=None):
        self.directory = Path(directory).resolve()
        self.buffer_bytes = max(1, buffer_bytes)
        self.admit = admit or (lambda count: None)

    def path(self, name):
        if not isinstance(name, str) or Path(name).name != name:
            raise ValueError('Invalid IPC file reference')
        path = (self.directory / name).resolve()
        if path.parent != self.directory:
            raise ValueError('IPC file escaped its exchange directory')
        return path

    def encode(self, value):
        from src.core import Form
        from src.core.files import FileArtifact
        if isinstance(value, FileArtifact):
            value.validate()
            return {"type": "file_artifact", "value": self.encode(value.to_dict())}
        if isinstance(value, np.ndarray):
            if value.dtype.hasobject:
                raise ValueError('Isolated operators cannot exchange object-dtype arrays')
            name = uuid.uuid4().hex[:16] + '.npy'
            header = io.BytesIO()
            np.lib.format.write_array_header_2_0(header, {'descr': np.lib.format.dtype_to_descr(value.dtype), 'fortran_order': False, 'shape': value.shape})
            header = header.getvalue()
            self.admit(int(value.nbytes) + len(header))
            with self.path(name).open('wb') as file:
                file.write(header)
                with np.nditer(value, flags=['external_loop', 'buffered', 'zerosize_ok'], op_flags=['readonly'], order='C',
                               buffersize=max(1, self.buffer_bytes // value.dtype.itemsize)) as blocks:
                    for block in blocks:
                        file.write(block.tobytes())
            return {'type': 'array', 'file': name}
        if isinstance(value, Form):
            return {'type': 'form', 'value': self.encode({k: getattr(value, k) for k in ('data', 'dims', 'labels', 'info', 'axis_info')})}
        if isinstance(value, np.generic):
            return self.encode(value.item())
        if value is None or type(value) in (str, int, bool):
            return value
        if type(value) is float:
            return value if math.isfinite(value) else {'type': 'float', 'value': str(value)}
        if isinstance(value, dict):
            return {'type': 'dict', 'items': [[self.encode(k), self.encode(v)] for k, v in value.items()]}
        if isinstance(value, (tuple, list, set)):
            return {'type': type(value).__name__, 'items': [self.encode(v) for v in value]}
        if isinstance(value, Path):
            return {'type': 'path', 'value': str(value)}
        if (type(value).__name__ == 'LabelEncoder' and getattr(value, 'name', None) == 'labelencoder'
                and hasattr(value, 'mapping') and hasattr(value, 'inverse')):
            return {'type': 'labelencoder', 'value': self.encode({'mapping': value.mapping, 'inverse': value.inverse})}
        raise TypeError(f'Unsupported isolated metadata type: {type(value).__module__}.{type(value).__name__}')

    def decode(self, value, *, mmap=False):
        if not isinstance(value, dict):
            return value
        kind = value['type']
        if kind == 'file_artifact':
            from src.core.files import FileArtifact
            artifact = FileArtifact(**self.decode(value['value'], mmap=mmap))
            artifact.validate()
            return artifact
        if kind == 'array':
            return np.load(self.path(value['file']), allow_pickle=False, mmap_mode='c' if mmap else None)
        if kind == 'float':
            return float(value['value'])
        if kind == 'path':
            return Path(value['value'])
        if kind == 'dict':
            return {self.decode(k, mmap=mmap): self.decode(v, mmap=mmap) for k, v in value['items']}
        if kind in ('list', 'tuple', 'set'):
            return {'list': list, 'tuple': tuple, 'set': set}[kind](self.decode(v, mmap=mmap) for v in value['items'])
        if kind == 'form':
            from src.core import Form
            return Form(**self.decode(value['value'], mmap=mmap))
        if kind == 'labelencoder':
            from src.reader.readers._encoder import LabelEncoder
            encoder = LabelEncoder()
            encoder.__dict__.update(self.decode(value['value'], mmap=mmap))
            return encoder
        raise ValueError(f'Unknown IPC metadata type: {kind}')

    def write(self, name, value):
        encoded = json.dumps(self.encode(value), ensure_ascii=False, allow_nan=False).encode('utf-8')
        self.admit(len(encoded))
        self.path(name).write_bytes(encoded)

    def read(self, name, *, mmap=False):
        return self.decode(json.loads(self.path(name).read_text(encoding='utf-8')), mmap=mmap)
