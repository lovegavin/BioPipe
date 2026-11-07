"""Executable synthetic CSV -> normalization -> PCA documentation example.

This verifies wiring, labels and finite results, not biological validity.
"""
import argparse
import gzip
import json
from pathlib import Path


def run_example(directory):
    import numpy as np
    from operon_sdk.declarations import bind_class, for_class
    from operon_sdk.testing import run_operator
    from src.reader.readers.csv_reader import CsvReader
    from src.task.step.steps.normalize import NormalizeStep
    from src.task.step.steps.pca import PcaStep
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / 'synthetic.csv.gz'
    with gzip.open(path, 'wt', encoding='utf-8', newline='') as handle:
        handle.write('f1,f2,f3\n1,4,2\n2,3,5\n5,1,3\n4,6,1\n')
    reader = bind_class(CsvReader, for_class(CsvReader))()
    form = reader.read(path, dims=['sample', 'feature'], labels={'sample': 'auto', 'feature': 'builtin'})
    normalized = run_operator(NormalizeStep, [form], {'method': 'zscore', 'dim': 'sample', 'output': 'normalized'})
    scores = run_operator(PcaStep, [normalized], {'dim': 'feature', 'n_components': 2, 'output': 'scores'})
    assert scores.data.shape == (4, 2)
    assert np.isfinite(scores.data).all()
    assert scores.labels['sample'] == form.labels['sample']
    result = {'synthetic': True, 'input': path.name, 'shape': list(scores.data.shape),
              'dims': list(scores.dims), 'labels': scores.labels, 'scores': scores.data.tolist(),
              'parameters': {'normalize': {'method': 'zscore', 'dim': 'sample'}, 'pca': {'dim': 'feature', 'n_components': 2}}}
    (directory / 'result.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    print(json.dumps(run_example(parser.parse_args().output), indent=2))
