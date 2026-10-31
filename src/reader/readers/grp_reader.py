"""GSEA .grp phenotype reader."""
from __future__ import annotations

from pathlib import Path

from src.core import Form
from src.core.contracts import reader_contract
from src.reader.base import Reader
from src.reader.readers._gsea_common import parse_phenotype, phenotype_form


class GrpReader(Reader):
    """Reader for GSEA .grp phenotype group files.

    The layout is the same as CLS: counts, a ``#`` class-name line, then
    one class index per sample. Output is ``[sample, feature]`` with one
    encoded phenotype column.
    """

    output_contract = reader_contract()
    file_input = {
        "dims": ["sample", "feature"],
        "labels": {"sample": "builtin", "feature": "builtin"},
    }
    extensions = [".grp"]
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
        samples, classes, _ = parse_phenotype(path, "GRP")
        return {
            "file_bytes": Path(path).stat().st_size,
            "shape": (len(samples), 1),
            "dtype": "float32",
            "dense_bytes": len(samples) * 4,
        }

    def read(self, path: Path, dims: list, labels: dict, **args) -> Form:
        return phenotype_form(path, dims, labels, args, "GRP")
