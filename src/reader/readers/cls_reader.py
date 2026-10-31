"""GSEA .cls phenotype reader."""
from __future__ import annotations

from pathlib import Path

from src.core import Form
from src.core.contracts import reader_contract
from src.reader.base import Reader
from src.reader.readers._gsea_common import parse_phenotype, phenotype_form


class ClsReader(Reader):
    """Reader for GSEA .cls categorical phenotype files.

    The output is ``[sample, feature]`` with one encoded ``class`` column.
    Class names are stored in the label encoder, so ``group_values`` can
    recover them for differential-expression operators.
    """

    output_contract = reader_contract()
    file_input = {
        "dims": ["sample", "feature"],
        "labels": {"sample": "builtin", "feature": "builtin"},
    }
    extensions = [".cls"]
    parameters_schema = {
        "type": "object",
        "properties": {
            "encoders": {
                "type": "object",
                "title": "Encoders",
                "additionalProperties": True,
            },
            "feature_label": {
                "type": "string",
                "title": "Phenotype column label",
                "default": "class",
                "minLength": 1,
            },
        },
        "additionalProperties": False,
    }

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
