"""5' versus 3' alignment density bias across annotated genes.

Inputs:  FileArtifact (bam), FileArtifact (gff/gff3/gtf)
Output:  2D Form [feature, statistic] with 5' density, 3' density and their ratio
"""
from __future__ import annotations

import numpy as np

from src.core import FileArtifact, Form, StepError
from src.task.context import Context
from src.task.step.base import Step
from src.task.step.steps._atac_utils import bam_path
from src.task.step.steps._bam_utils import iter_records, ref_span, read_header
from src.task.step.steps._count_utils import FeatureIndex
from src.task.step.steps.bam_gene_counts import annotation_features

_SKIP = 0x4 | 0x100 | 0x200 | 0x800


class BamGeneBiasStep(Step):
    """Compare alignment density in the first and last segment of each gene."""
    provider = 'operon-core'
    parameters_file = 'bam_gene_bias.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'file_artifact',
                     'representations': ['file_artifact'],
                     'metadata': {}},
                    {'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
        'id': 'bam_gene_bias',
        'version': '1.0.0',
        'kind': 'operator',
        'title': 'bam_gene_bias',
        'description': "5' versus 3' alignment density bias across annotated genes.",
        'category': 'Omics',
        'icon': 'TrendingUp',
        'contracts': {
            'version': 1,
            'inputs': [
                {'version': 1, 'kind': 'file', 'numeric': False, 'ndim': 0, 'dims': [],
                 'info': {'representation': {'type': 'string', 'enum': ['bam']}}},
                {'version': 1, 'kind': 'form', 'numeric': True, 'ndim': 2,
                 'dims': ['feature', 'field'], 'labels': []},
            ],
            'output': {'mode': 'declare', 'schema': {'ndim': 2, 'numeric': True,
                                                     'info_open': True,
                                                     'axis_info_open': True}},
        },
        'resources': {'memory_modes': ['full'], 'supports_cuda': False,
                      'estimate': 'estimate_memory'},
        'inputs_arity': 2,
        'outputs': [],
        'output_parameter': 'output',
    }

    @classmethod
    def estimate_memory(cls, inputs, params, profiles):
        size = sum(int(getattr(item, 'file_bytes', 0) or 0) for item in inputs or [])
        return max(int(size * 0.2), 16 * 1024 ** 2), 1024 ** 2

    def run(self, ctx: Context, inputs) -> None:
        if len(inputs) != 2:
            raise StepError('bam_gene_bias requires a BAM and an annotation')
        params = ctx.step_params
        out_name = params.get('output', 'gene_bias')
        bam = bam_path(inputs[0], 'bam_gene_bias')
        feature_type = str(params.get('feature_type', 'gene'))
        id_attribute = str(params.get('id_attribute', 'locus_tag'))
        min_mapq = int(params.get('min_mapq', 30))
        bins = int(params.get('bins', 5))
        count_pairs = bool(params.get('count_pairs', False))
        if bins < 2:
            raise StepError('bins must be at least 2')

        features = annotation_features(inputs[1], feature_type, id_attribute,
                                       'bam_gene_bias')
        lengths = {feature_id: end - start for _, feature_id, start, end, _ in features}
        bin_counts = {feature_id: np.zeros(bins, dtype=np.int64) for _, feature_id, _, _, _ in features}
        index = FeatureIndex(features)
        _, references = read_header(bam)
        names = [name for name, _ in references]

        for record in iter_records(bam, max_records=int(params.get('max_records', 0))):
            flag = record['flag']
            if flag & _SKIP or record['mapq'] < min_mapq:
                continue
            if count_pairs and not flag & 0x40:
                continue
            ref_id = record['ref_id']
            if ref_id < 0 or ref_id >= len(names):
                continue
            span = ref_span(record['cigar'])
            if span <= 0:
                continue
            start = record['pos']
            midpoint = start + span / 2.0
            for feature_start, feature_end, feature_id, _strand in index.overlaps(
                    names[ref_id], start, start + span):
                length = lengths[feature_id]
                fraction = (midpoint - feature_start) / length
                slot = int(fraction * bins)
                if slot < 0:
                    slot = 0
                elif slot >= bins:
                    slot = bins - 1
                bin_counts[feature_id][slot] += 1

        rows = []
        labels = {}
        zero_three = 0
        for position, (_, feature_id, start, end, _strand) in enumerate(features):
            length = end - start
            width = length / bins
            five = bin_counts[feature_id][0] / width
            three = bin_counts[feature_id][-1] / width
            if three > 0:
                ratio = float(five / three)
            else:
                ratio = 0.0
                zero_three += 1
            rows.append((float(five), float(three), ratio))
            labels[feature_id] = position
        data = np.asarray(rows, dtype=np.float64)
        info = {
            'n_features': len(features),
            'bins': bins,
            'min_mapq': min_mapq,
            'count_pairs': count_pairs,
            'n_zero_three_prime': zero_three,
        }
        out = Form(data, ['feature', 'statistic'],
                   {'feature': labels,
                    'statistic': {'five_prime_density': 0,
                                  'three_prime_density': 1,
                                  'ratio': 2}}, info=info)
        out.validate()
        ctx[out_name] = out
        self._export_data = dict(info, output=out_name)

    def export(self, ctx: Context):
        return dict(getattr(self, '_export_data', {}))
