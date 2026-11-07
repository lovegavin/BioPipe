"""Lossless Reader payload; imports no scientific runtime during registration."""
from dataclasses import dataclass
from typing import Any


@dataclass
class NativeArray:
    data: Any
    dims: list
    labels: dict
    info: dict
    axis_info: dict


def as_form(value):
    """Wrap explicitly annotated arrays without copying or guessing semantics."""
    import numpy as np
    from src.core import Form
    if isinstance(value, Form):
        value.validate()
        return value
    if not isinstance(value, NativeArray) or not isinstance(value.data, np.ndarray):
        raise ValueError('native.ndarray requires NativeArray with explicit Form metadata')
    if not isinstance(value.dims, list) or not all(isinstance(x, str) for x in value.dims):
        raise ValueError('NativeArray requires explicit dimension names')
    if not all(isinstance(x, dict) for x in (value.labels, value.info, value.axis_info)):
        raise ValueError('NativeArray requires labels, info and axis_info dictionaries')
    result = Form(value.data, list(value.dims), dict(value.labels), dict(value.info), dict(value.axis_info))
    result.validate()
    return result


def reader_output(value, declaration):
    """Validate declared containers and adapt only the registered array bridge."""
    outputs = (declaration.get('data_formats') or {}).get('outputs', [])
    if not outputs:
        return value
    return validate_format_value(value, outputs[0])


def validate_format_value(value, port):
    from src.core import Form, FileArtifact
    representations = port['representations']
    if representations == ['native.ndarray']:
        if port['logical_type'] != 'form':
            raise ValueError('Native Reader wrapper requires logical_type form')
        value = as_form(value)
    logical = port['logical_type']
    if logical == 'form' and not isinstance(value, Form):
        raise ValueError('Declared form logical type requires a Form, not a different container')
    if logical == 'file_artifact' and not isinstance(value, FileArtifact):
        raise ValueError('Declared file_artifact logical type requires a FileArtifact')
    if logical not in {'form', 'file_artifact', 'matrix', 'list'} and not (
            isinstance(value, FileArtifact) and value.format in representations):
        raise ValueError('Logical type has no verified runtime representation validator')
    if representations == ['form'] and not isinstance(value, Form):
        raise ValueError('Reader declared form but returned a different container')
    if representations == ['file_artifact'] and not isinstance(value, FileArtifact):
        raise ValueError('Reader declared file_artifact but returned a different container')
    known = {'native.ndarray', 'form', 'file_artifact', 'numpy.ndarray', 'npy.memmap'}
    if isinstance(value, FileArtifact):
        if 'file_artifact' not in representations and value.format not in representations:
            raise ValueError('Output container does not match the declared representation')
    elif isinstance(value, Form):
        import numpy as np
        accepted = {'form', 'native.ndarray', 'numpy.ndarray'}
        if isinstance(value.data, np.memmap):
            accepted.add('npy.memmap')
        if not accepted.intersection(representations):
            raise ValueError('Output container does not match the declared representation')
    else:
        raise ValueError('Output has no verified implementation for its declared representation')
    if not set(representations) & known:
        if not isinstance(value, FileArtifact) or value.format not in representations:
            raise ValueError('Output has no verified implementation for its declared representation')
    if port['logical_type'] in {'matrix', 'list'}:
        rank = 2 if port['logical_type'] == 'matrix' else 1
        if not isinstance(value, Form) or value.data.ndim != rank:
            raise ValueError('Actual payload does not satisfy its declared logical type')
    if isinstance(value, Form) and any(x in {'numpy.ndarray', 'npy.memmap'} for x in representations):
        import numpy as np
        if representations == ['npy.memmap'] and not isinstance(value.data, np.memmap):
            raise ValueError('Declared npy.memmap requires actual mapped storage')
    for key, expected in port.get('metadata', {}).items():
        observed = ({'dims': value.dims, 'dtype': str(value.data.dtype), 'shape': list(value.data.shape)}.get(key, value.info.get(key))
                    if isinstance(value, Form) else value.info.get(key))
        if observed != expected:
            raise ValueError(f'Output format metadata mismatch: {key}')
    return value


def validate_stream_format(stream, port):
    """Validate generic Form stream metadata without constructing a full Form."""
    if port['logical_type'] != 'form' or 'form' not in port['representations']:
        raise ValueError('Streaming input requires a supported generic Form representation')
    metadata = stream['metadata']
    values = {**metadata.get('info', {}), 'dims': metadata.get('dims'), 'shape': list(stream['shape'])}
    if 'dtype' in metadata:
        values['dtype'] = str(metadata['dtype'])
    for key, expected in port.get('metadata', {}).items():
        if key not in values or values[key] != expected:
            raise ValueError(f'Stream format metadata mismatch: {key}')
