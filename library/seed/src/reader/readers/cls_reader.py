"""GSEA .cls phenotype reader."""
from __future__ import annotations

from pathlib import Path

from src.core import Form
from src.reader.base import Reader
from src.reader.readers._gsea_common import parse_phenotype, phenotype_form


class ClsReader(Reader):
    provider = 'operon-readers'
    """Reader for GSEA .cls categorical phenotype files.

    The output is ``[sample, feature]`` with one encoded ``class`` column.
    Class names are stored in the label encoder, so ``group_values`` can
    recover them for differential-expression operators.
    """
    parameters_file = 'cls_reader.ClsReader.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'ClsReader',
     'version': '1.0.0',
     'kind': 'reader',
     'title': 'Reader for GSEA .cls categorical phenotype files',
     'category': 'Data',
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
     'resources': {'memory_modes': ['full'], 'supports_cuda': False},
     'description': 'Reader for GSEA .cls categorical phenotype files.\n'
                    '\n'
                    '    The output is ``[sample, feature]`` with one encoded ``class`` column.\n'
                    '    Class names are stored in the label encoder, so ``group_values`` can\n'
                    '    recover them for differential-expression operators.',
     'extensions': ['.cls'],
     'requires_siblings': [],
     'excludes_siblings': [],
     'handles_compression': False,
     'file_input': {'dims': ['sample', 'feature'],
                    'labels': {'sample': 'builtin', 'feature': 'builtin'}}}


    def probe(self, path, **args):
        samples, classes, _ = parse_phenotype(path, "CLS")
        return {
            "file_bytes": Path(path).stat().st_size,
            "shape": (len(samples), 1),
            "dtype": "float32",
            "dense_bytes": len(samples) * 4,
        }

    def read(self, path: Path, dims: list, labels: dict, **args) -> Form:
        return phenotype_form(path, dims, labels, args, "CLS")
