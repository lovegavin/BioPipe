"""Synthetic end-to-end examples: python demo.py --output ./plots [--r]."""
import argparse
import json
from pathlib import Path

import numpy as np
from biopipe_sdk import Context, Form
from biopipe_sdk.declarations import bind_class, for_class
from biopipe_sdk.protocol import validate_parameters
from biopipe.parameter_values import split_task
from src.task import STEPS, run
from biopipe_plot_examples.volcano import Volcano
from biopipe_plot_examples.complex_heatmap import ComplexHeatmap


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--r', action='store_true', help='Also prepare R dependencies and run ComplexHeatmap')
    args = parser.parse_args()
    fixtures = [(Volcano, np.column_stack([np.linspace(-3, 3, 60), np.linspace(.001, .2, 60)]),
                 ['feature', 'stat'], {'feature': {f'g{i}': i for i in range(60)}, 'stat': {'log2FC': 0, 'padj': 1}})]
    if args.r:
        fixtures.append((ComplexHeatmap, np.random.default_rng(17).normal(size=(12, 6)),
                         ['feature', 'sample'], {'feature': {f'g{i}': i for i in range(12)},
                                                 'sample': {f's{i}': i for i in range(6)}}))
    for original, data, dims, labels in fixtures:
        cls = bind_class(original, for_class(original))
        directory = (args.output / cls.name).resolve()
        directory.mkdir(parents=True, exist_ok=True)
        spec = {'name': cls.name, 'inputs': ['x'], 'params': validate_parameters(cls.parameters_schema, {})}
        manifest = {'sources': {}, 'steps': [spec]}
        topology, values = split_task(manifest)
        for name, value in [('task.json', topology), ('parameters.json', values)]:
            (directory / name).write_text(json.dumps(value, indent=2), encoding='utf-8')
        ctx = Context(directory, manifest)
        previous = STEPS.get(cls.name)
        STEPS[cls.name] = cls
        try:
            ctx['x'] = Form(data, dims, labels)
            run(ctx, [spec])
            report = json.loads((ctx.out_dir / ctx.artifacts['exports'][0]['export_path']).read_text(encoding='utf-8'))
            assert len({f['id'] for f in report['figures']}) == (2 if original is Volcano else 1)
            assert all(Path(f['path']).stat().st_size > 100 for f in report['figures'])
            print(cls.name, 'outputs:', json.dumps(report['figures']), flush=True)
        finally:
            ctx.finalize()
            if previous is None:
                STEPS.pop(cls.name, None)
            else:
                STEPS[cls.name] = previous


if __name__ == '__main__':
    main()
