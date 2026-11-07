"""PLINK .map variant map reader."""
from __future__ import annotations

from pathlib import Path

import numpy as np

from src.core import Form, ReaderError
from src.core.numeric import compact_numeric
from src.reader.base import Reader
from src.reader.readers._encoder import get_encoder
from src.reader.readers._labels import unique_labels
from src.reader.readers._table_common import read_whitespace


class MapReader(Reader):
    provider = 'operon-readers'
    """Reader for the four-column PLINK .map format."""
    parameters_file = 'map_reader.MapReader.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'MapReader',
     'version': '1.0.0',
     'kind': 'reader',
     'title': 'Reader for the four-column PLINK .map format',
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
     'description': 'Reader for the four-column PLINK .map format.',
     'extensions': ['.map'],
     'requires_siblings': [],
     'excludes_siblings': [],
     'handles_compression': False,
     'file_input': {'dims': ['variant', 'field'], 'labels': {'variant': 'auto', 'field': 'builtin'}}}


    def read(self, path: Path, dims: list, labels: dict, **args) -> Form:
        if len(dims) != 2:
            raise ReaderError(f"MAP reader requires exactly two dims, got {dims}")
        variant_dim, field_dim = dims
        df = read_whitespace(path, ["chrom", "variant", "cm", "bp"], "MAP")
        variants = [str(v) for v in df["variant"]]
        data = np.empty((len(df), 3), dtype=np.float64)
        enc = get_encoder((args.get("encoders") or {}).get("chrom", "labelencoder"))
        data[:, 0] = enc.fit_transform([str(v) for v in df["chrom"]])
        data[:, 1] = df["cm"].to_numpy(dtype=np.float64)
        data[:, 2] = df["bp"].to_numpy(dtype=np.float64)
        return Form(
            data=compact_numeric(data),
            dims=[variant_dim, field_dim],
            labels={
                variant_dim: unique_labels(variants, variant_dim, "map"),
                field_dim: unique_labels(["chrom", "cm", "bp"], field_dim, "map"),
            },
            info={"missing_code": np.nan, "encoders": {field_dim: {"chrom": enc}}},
        )
