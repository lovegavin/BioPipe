"""PLINK FAM sample metadata reader."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.core import Form, ReaderError
from src.reader.base import Reader
from src.reader.readers._table_common import table_form


class FamReader(Reader):
    provider = 'operon-readers'
    """PLINK FAM reader (six standard columns)."""
    parameters_file = 'fam_reader.FamReader.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'FamReader',
     'version': '1.0.0',
     'kind': 'reader',
     'title': 'PLINK FAM reader (six standard columns)',
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
     'description': 'PLINK FAM reader (six standard columns).',
     'extensions': ['.fam'],
     'requires_siblings': [],
     'excludes_siblings': [],
     'handles_compression': False,
     'file_input': {'dims': ['sample', 'feature'], 'labels': {'sample': 'auto', 'feature': 'builtin'}}}


    def read(self, path: Path, dims: list, labels: dict, **args) -> Form:
        try:
            frame = pd.read_csv(path, sep=r"\s+", header=None, comment="#")
        except Exception as exc:
            raise ReaderError(f"FAM reader: cannot parse {path}: {exc}") from exc
        if frame.shape[1] != 6:
            raise ReaderError(f"FAM reader: expected 6 columns, got {frame.shape[1]}")
        frame.columns = ["family", "individual", "father", "mother", "sex", "phenotype"]
        ids = frame["individual"].astype(str).tolist()
        frame["sex"] = pd.to_numeric(frame["sex"], errors="coerce").mask(lambda s: s <= 0)
        frame["phenotype"] = pd.to_numeric(frame["phenotype"], errors="coerce").mask(lambda s: s <= 0)
        return table_form(
            frame.drop(columns=["individual"]), dims, labels, "FAM",
            encoders_cfg=args.get("encoders") or {},
            row_labels=ids,
            info_extra={"format": "FAM", "n_samples": len(ids)},
        )
