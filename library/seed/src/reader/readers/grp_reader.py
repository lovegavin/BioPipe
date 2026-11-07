"""GSEA .grp phenotype reader."""
from __future__ import annotations

from pathlib import Path

from src.core import Form
from src.reader.base import Reader
from src.reader.readers._gsea_common import parse_phenotype, phenotype_form


class GrpReader(Reader):
    provider = 'operon-readers'
    """Reader for GSEA .grp phenotype group files.

    The layout is the same as CLS: counts, a ``#`` class-name line, then
    one class index per sample. Output is ``[sample, feature]`` with one
    encoded phenotype column.
    """
    parameters_file = 'grp_reader.GrpReader.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'GrpReader',
     'version': '1.0.0',
     'kind': 'reader',
     'title': 'Reader for GSEA .grp phenotype group files',
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
     'description': 'Reader for GSEA .grp phenotype group files.\n'
                    '\n'
                    '    The layout is the same as CLS: counts, a ``#`` class-name line, then\n'
                    '    one class index per sample. Output is ``[sample, feature]`` with one\n'
                    '    encoded phenotype column.',
     'extensions': ['.grp'],
     'requires_siblings': [],
     'excludes_siblings': [],
     'handles_compression': False,
     'file_input': {'dims': ['sample', 'feature'],
                    'labels': {'sample': 'builtin', 'feature': 'builtin'}}}


    def probe(self, path, **args):
        samples, classes, _ = parse_phenotype(path, "GRP")
        return {
            "file_bytes": Path(path).stat().st_size,
            "shape": (len(samples), 1),
            "dtype": "float32",
            "dense_bytes": len(samples) * 4,
        }

    def read(self, path: Path, dims: list, labels: dict, **args) -> Form:
        return phenotype_form(path, dims, labels, args, "GRP")
