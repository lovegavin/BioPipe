"""protXML reader: one protein per row."""
from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from src.core import Form, ReaderError
from src.core.contracts import reader_contract
from src.reader.base import Reader
from ._xml20_common import attributes, descendants, frame_form, numeric


class ProtxmlReader(Reader):
    output_contract = reader_contract()
    file_input = {"dims": ["protein", "feature"], "labels": {"protein": "auto", "feature": "builtin"}}
    extensions = [".protxml"]
    handles_compression = False
    parameters_schema = {
        "type": "object",
        "properties": {
            "encoders": {"type": "object", "additionalProperties": True},
            "max_proteins": {"type": "integer", "minimum": 1, "default": 200000},
        },
        "additionalProperties": False,
    }

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
