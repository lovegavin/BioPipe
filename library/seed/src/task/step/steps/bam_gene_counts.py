"""Per-gene alignment counts from a BAM and a GFF/GTF annotation.

Inputs:  FileArtifact (bam), FileArtifact (gff/gff3/gtf)
Output:  2D Form [feature, statistic] with counts, length and CPM
"""
from __future__ import annotations

import numpy as np

from src.core import FileArtifact, Form, StepError
from src.task.context import Context
from src.task.step.base import Step
from src.task.step.steps._annotation_utils import (
    annotation_table,
    parse_attributes,
    record_label,
    select_type,
)
from src.task.step.steps._atac_utils import bam_path
from src.task.step.steps._count_utils import count_alignments


def annotation_features(form, feature_type: str, id_attribute: str, operator: str):
    """Decode a GFF Form into [(seqid, id, start, end, strand)] features."""
    table = annotation_table(form, 'feature', 'field', operator)
    indices = select_type(table, feature_type, operator)
    features = []
    for index in indices:
        attributes = table['attributes'][index]
        feature_id = parse_attributes(attributes).get(id_attribute)
        if not feature_id:
            feature_id = record_label(attributes, f"{table['seqid'][index]}:{table['start'][index]}-{table['end'][index]}")
        features.append((table['seqid'][index], feature_id,
                         int(table['start'][index]) - 1, int(table['end'][index]),
                         table['strand'][index]))
    return features


class BamGeneCountsStep(Step):
    """Count primary alignments overlapping each annotated gene."""
    provider = 'operon-core'
    parameters_file = 'bam_gene_counts.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'file_artifact',
                     'representations': ['file_artifact'],
                     'metadata': {}},
                    {'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
        'id': 'bam_gene_counts',
        'version': '1.0.0',
        'kind': 'operator',
        'title': 'bam_gene_counts',
        'description': 'Per-gene alignment counts, gene length and CPM from a BAM and GFF/GTF.',
        'category': 'Omics',
        'icon': 'Table',
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
            raise StepError('bam_gene_counts requires a BAM and an annotation')
        params = ctx.step_params
        out_name = params.get('output', 'gene_counts')
        bam = bam_path(inputs[0], 'bam_gene_counts')
        feature_type = str(params.get('feature_type', 'gene'))
        id_attribute = str(params.get('id_attribute', 'locus_tag'))
        min_mapq = int(params.get('min_mapq', 30))
        count_pairs = bool(params.get('count_pairs', False))

        features = annotation_features(inputs[1], feature_type, id_attribute,
                                       'bam_gene_counts')
        counts, considered = count_alignments(
            bam, features, min_mapq=min_mapq, count_pairs=count_pairs,
            max_records=int(params.get('max_records', 0)))

        rows = []
        labels = {}
        for index, (_, feature_id, start, end, _strand) in enumerate(features):
            rows.append((float(counts.get(feature_id, 0)), float(end - start)))
            labels[feature_id] = index
        table = np.asarray(rows, dtype=np.float64)
        total = float(table[:, 0].sum())
        cpm = table[:, 0] / total * 1e6 if total > 0 else np.zeros(len(table))
        data = np.column_stack([table[:, 0], table[:, 1], cpm])
        dims = ['feature', 'statistic']
        labels = {'feature': labels,
                  'statistic': {'counts': 0, 'length': 1, 'cpm': 2}}
        info = {
            'n_features': len(features),
            'total_counts': total,
            'counted_alignments': considered,
            'feature_type': feature_type,
            'id_attribute': id_attribute,
            'min_mapq': min_mapq,
            'count_pairs': count_pairs,
        }
        out = Form(data, dims, labels, info=info)
        out.validate()
        ctx[out_name] = out
        self._export_data = dict(info, output=out_name)

    def export(self, ctx: Context):
        return dict(getattr(self, '_export_data', {}))
