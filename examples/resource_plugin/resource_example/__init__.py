"""SDK-only example of equivalent full/stream and full/disk execution."""
import numpy as np
from biopipe_sdk import Form, Reader, Step, port, reader_contract


class Sum(Step):
    parameters_file = 'Sum.parameters.json'
    definition = {'protocol_version': 3,
     'id': 'example.stream_sum',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'example.stream_sum',
     'description': '',
     'category': 'Plugins',
     'contracts': {'version': 1,
                   'inputs': [{'version': 1,
                               'numeric': True,
                               'info': {},
                               'dims': [],
                               'labels': [],
                               'parallel': [],
                               'ndim': 2}],
                   'output': {'mode': 'report'}},
     'resources': {'memory_modes': ['full', 'stream'],
                   'supports_cuda': False,
                   'estimate': 'estimate_memory',
                   'stream_protocol': 'flat-reduction-v1',
                   'stream_buffer_multiplier': 2,
                   'stream_fixed_bytes': 1024},
     'inputs_arity': 1,
     'outputs': [],
     'output_parameter': None}

    def run(self, ctx, inputs):
        self.total = float(np.nansum(inputs[0].data, dtype=np.float64))

    def run_stream(self, ctx, stream):
        self.total = 0.0
        for block in stream['chunks']:
            self.total += float(np.nansum(block, dtype=np.float64))

    def export(self, ctx):
        return {'sum': self.total}


class NpyReader(Reader):
    parameters_file = 'NpyReader.parameters.json'
    definition = {'protocol_version': 3,
     'id': 'example.disk_npy',
     'version': '1.0.0',
     'kind': 'reader',
     'title': 'NpyReader',
     'contracts': {'version': 1,
                   'inputs': [],
                   'output': {'version': 1,
                              'numeric': True,
                              'info': {'missing_code': {'type': ['number', 'null']},
                                       'encoders': {'type': 'object', 'optional': True}},
                              'dims': [],
                              'labels': [],
                              'parallel': [],
                              'ndim': 2,
                              'axis_fields': [],
                              'info_open': False}},
     'resources': {'memory_modes': ['full', 'disk'],
                   'supports_cuda': False,
                   'disk_protocol': 'dense-writer-v1'},
     'extensions': ['.npy'],
     'requires_siblings': [],
     'excludes_siblings': [],
     'handles_compression': False}

    def probe(self, path, **args):
        array = np.load(path, mmap_mode='r', allow_pickle=False)
        if array.ndim != 2 or array.dtype.kind not in 'biuf':
            raise ValueError('Expected a real numeric two-dimensional NPY array')
        size = int(array.size) * 4
        return {'file_bytes': path.stat().st_size, 'shape': list(array.shape),
                'dtype': 'float32', 'dense_bytes': size, 'preparation_bytes': size}

    def metadata(self, shape, dims, labels):
        if len(dims) != 2:
            raise ValueError('Expected two dimension names')
        mapping = {}
        for dim, size in zip(dims, shape):
            value = labels.get(dim, 'auto')
            if value == 'auto':
                mapping[dim] = {str(i): i for i in range(size)}
            elif isinstance(value, dict) and all(type(i) is int for i in value.values()):
                mapping[dim] = dict(value)
            else:
                raise ValueError('Use auto labels or explicit name-to-position mappings')
        return {'dims': list(dims), 'labels': mapping, 'info': {'missing_code': float('nan')}, 'axis_info': {}}

    def read(self, path, dims, labels, **args):
        self.probe(path)
        array = np.load(path, allow_pickle=False).astype(np.float32)
        return Form(array, **self.metadata(array.shape, dims, labels))

    def read_to_disk(self, path, dims, labels, writer, chunk_bytes, **args):
        array = np.load(path, mmap_mode='r', allow_pickle=False)
        if array.shape != writer.shape:
            raise ValueError('Source shape changed after probe')
        width = max(1, chunk_bytes // max(array.dtype.itemsize, 4))
        for row in range(array.shape[0]):
            for column in range(0, array.shape[1], width):
                writer.write(row, column, array[row, column:column + width])
        return self.metadata(array.shape, dims, labels)
