"""GSEA .rnk ranked-list reader."""
from __future__ import annotations

from pathlib import Path

import numpy as np

from src.core import Form, ReaderError
from src.core.contracts import reader_contract
from src.core.numeric import compact_numeric
from src.reader.base import Reader
from src.reader.readers._gsea_common import parse_rnk
from src.reader.readers._table_common import labels_for


class RnkReader(Reader):
    """Reader for GSEA .rnk ranked gene lists.

    The output is ``[gene, feature]`` with a single numeric ``score``
    feature. File order is preserved because rank order is meaningful for
    preranked GSEA.
    """

    output_contract = reader_contract()
    file_input = {
        "dims": ["gene", "feature"],
        "labels": {"gene": "builtin", "feature": "builtin"},
    }
    extensions = [".rnk"]
    parameters_schema = {
        "type": "object",
        "properties": {
            "header": {"type": "boolean", "title": "Header row", "default": False},
            "comment": {
                "type": "string",
                "title": "Comment prefix",
                "default": "#",
                "description": "Lines starting with this prefix are ignored; empty disables comments.",
            },
            "gene_column": {
                "type": "integer",
                "title": "Gene column",
                "default": 0,
                "minimum": 0,
            },
            "score_column": {
                "type": "integer",
                "title": "Score column",
                "default": 1,
                "minimum": 0,
            },
            "feature_label": {
                "type": "string",
                "title": "Score label",
                "default": "score",
                "minLength": 1,
            },
        },
        "additionalProperties": False,
    }

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
