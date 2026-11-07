"""protXML reader: one protein per row."""
from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from src.core import Form, ReaderError
from src.reader.base import Reader
from ._xml20_common import attributes, descendants, frame_form, numeric


class ProtxmlReader(Reader):
    provider = 'operon-readers'
    parameters_file = 'protxml_reader.ProtxmlReader.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'ProtxmlReader',
     'version': '1.0.0',
     'kind': 'reader',
     'title': 'ProtxmlReader',
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
     'description': 'Reads .protxml files.',
     'extensions': ['.protxml'],
     'requires_siblings': [],
     'excludes_siblings': [],
     'handles_compression': False,
     'file_input': {'dims': ['protein', 'feature'],
                    'labels': {'protein': 'auto', 'feature': 'builtin'}}}

    def read(self, path: Path, dims: list, labels: dict, **args) -> Form:
        try:
            root = ET.parse(path).getroot()
        except (OSError, ET.ParseError) as exc:
            raise ReaderError(f"protXML reader: cannot parse {path}: {exc}") from exc
        records = []
        row_labels = []
        max_proteins = int(args.get("max_proteins", 200000))
        for group in descendants(root, "protein_group"):
            group_attrs = attributes(group)
            group_number = group_attrs.get("group_number", "")
            for protein in descendants(group, "protein"):
                if len(records) >= max_proteins:
                    break
                attrs = attributes(protein)
                name = attrs.get("protein_name") or attrs.get("protein") or f"protein:{len(records)}"
                records.append({
                    "protein_name": name,
                    "percent_coverage": numeric(attrs.get("percent_coverage")),
                    "total_peptides": numeric(attrs.get("total_number_peptides")),
                    "distinct_peptides": numeric(attrs.get("total_number_distinct_peptides")),
                    "protein_probability": numeric(attrs.get("probability")),
                    "n_indistinguishable": numeric(attrs.get("n_indistinguishable_proteins")),
                    "group_number": group_number,
                })
                row_labels.append(name)
        return frame_form(records, row_labels, dims, labels, "protXML", path,
                          args.get("encoders"), {})
