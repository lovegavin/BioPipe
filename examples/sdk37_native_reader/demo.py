"""Native mapped array -> Form bridge -> unchanged legacy operator."""
from pathlib import Path
import argparse
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from operon_sdk import Reader, NativeArray


class MappedReader(Reader):
    parameters_file = 'demo.parameters.json'
    definition = {
        'protocol_version': 3, 'protocol_revision': '3.7',
        'id': 'example.mapped_array', 'version': '1.0.0', 'kind': 'reader',
        'title': 'Mapped numeric array', 'extensions': ['.npy'],
        'contracts': {'inputs': [], 'output': {'numeric': True, 'ndim': 2}},
        'data_formats': {'inputs': [], 'outputs': [
            {'logical_type': 'form', 'representations': ['native.ndarray']}]},
        'resources': {'memory_modes': ['full'], 'supports_cuda': False},
        'dependencies': ['numpy>=1.26'], 'dependency_imports': ['numpy'],
    }

    def read(self, path, dims, labels, **args):
        import numpy as np
        data = np.load(path, mmap_mode='r', allow_pickle=False)
        if data.ndim != 2 or data.dtype.kind not in 'biuf':
            raise ValueError('Expected a real numeric matrix')
        return NativeArray(data, dims, labels, {'missing_code': float('nan')}, {})


def main(output):
    import numpy as np
    from operon_sdk.native_array import reader_output
    from src.task import Context, run
    output.mkdir(parents=True, exist_ok=True)
    path = output / 'synthetic.npy'
    np.save(path, np.arange(6, dtype=float).reshape(2, 3), allow_pickle=False)
    payload = MappedReader().read(path, ['sample', 'feature'],
        {'sample': {'a': 0, 'b': 1}, 'feature': {'x': 0, 'y': 1, 'z': 2}})
    # This is the same validation/bridge used by normal Reader ingestion.
    form = reader_output(payload, MappedReader.definition)
    assert form.data is payload.data
    assert form.labels == payload.labels and form.axis_info == payload.axis_info
    ctx = Context(output / 'task', {})
    ctx['input'] = form
    try:
        run(ctx, [{'name': 'log_transform', 'inputs': ['input'],
                   'params': {'base': 2, 'pseudocount': 1, 'output': 'result'}}])
        np.testing.assert_allclose(ctx['result'].data, np.log2(payload.data + 1))
        print(json.dumps({'status': 'passed', 'bridge_copies': 0,
                          'legacy_operator': 'log_transform', 'shape': list(ctx['result'].data.shape)}))
    finally:
        ctx.finalize()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    main(parser.parse_args().output.resolve())
