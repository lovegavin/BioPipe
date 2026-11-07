"""GSEA .rnk ranked-list reader."""
from __future__ import annotations

from pathlib import Path

import numpy as np

from src.core import Form, ReaderError
from src.core.numeric import compact_numeric
from src.reader.base import Reader
from src.reader.readers._gsea_common import parse_rnk
from src.reader.readers._table_common import labels_for


class RnkReader(Reader):
    provider = 'operon-readers'
    """Reader for GSEA .rnk ranked gene lists.

    The output is ``[gene, feature]`` with a single numeric ``score``
    feature. File order is preserved because rank order is meaningful for
    preranked GSEA.
    """
    parameters_file = 'rnk_reader.RnkReader.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'RnkReader',
     'version': '1.0.0',
     'kind': 'reader',
     'title': 'Reader for GSEA .rnk ranked gene lists',
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
     'description': 'Reader for GSEA .rnk ranked gene lists.\n'
                    '\n'
                    '    The output is ``[gene, feature]`` with a single numeric ``score``\n'
                    '    feature. File order is preserved because rank order is meaningful for\n'
                    '    preranked GSEA.',
     'extensions': ['.rnk'],
     'requires_siblings': [],
     'excludes_siblings': [],
     'handles_compression': False,
     'file_input': {'dims': ['gene', 'feature'], 'labels': {'gene': 'builtin', 'feature': 'builtin'}}}


    def _parse(self, path: Path, args):
        gene_column = int(args.get("gene_column", 0))
        score_column = int(args.get("score_column", 1))
        if gene_column == score_column:
            raise ReaderError("RNK reader: gene_column and score_column must differ")
        return parse_rnk(
            path,
            header=bool(args.get("header", False)),
            comment=str(args.get("comment", "#")),
            gene_column=gene_column,
            score_column=score_column,
        )

    def probe(self, path, **args):
        genes, _ = self._parse(path, args)
        return {
            "file_bytes": Path(path).stat().st_size,
            "shape": (len(genes), 1),
            "dtype": "float32",
            "dense_bytes": len(genes) * 4,
        }

    def read(self, path: Path, dims: list, labels: dict, **args) -> Form:
        if len(dims) != 2:
            raise ReaderError(f"RNK reader requires exactly two dims, got {dims}")
        gene_dim, feature_dim = dims
        genes, scores = self._parse(path, args)
        feature_label = str(args.get("feature_label", "score")).strip()
        if not feature_label:
            raise ReaderError("RNK reader: feature_label must not be empty")
        data = np.asarray(scores, dtype=np.float32).reshape(-1, 1)
        form = Form(
            data=compact_numeric(data),
            dims=[gene_dim, feature_dim],
            labels={
                gene_dim: labels_for(genes, gene_dim, labels.get(gene_dim), "RNK"),
                feature_dim: labels_for(
                    [feature_label], feature_dim, labels.get(feature_dim), "RNK"
                ),
            },
            info={"missing_code": np.nan, "n_genes": len(genes), "format": "RNK"},
        )
        form.validate()
        return form
