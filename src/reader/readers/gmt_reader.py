# src/reader/readers/gmt_reader.py
"""GMT gene-set reader.

A GMT file has one gene set per line::

    set_name<TAB>description<TAB>gene1<TAB>gene2 ...

The result is a binary gene x set matrix. Genes are ordered by first
appearance in the file; duplicate set names are rejected, while duplicate
genes inside one set are collapsed.

The reader deliberately does **not** perform enrichment. It only
preserves set membership so `ora` / `gsea` can apply their own
statistics and multiple-testing policy.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from src.core import Form, ReaderError
from src.core.contracts import reader_contract
from src.reader.base import Reader
from src.reader.readers._labels import unique_labels


class GmtReader(Reader):
    """Reader for .gmt gene-set files."""

    output_contract = reader_contract()

    file_input = {
        "dims": ["gene", "gene_set"],
        "labels": {"gene": "builtin", "gene_set": "builtin"},
    }
    extensions = [".gmt"]
    parameters_schema = {
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    }

    @staticmethod
    def _parse(path: Path):
        sets: list[tuple[str, list[str]]] = []
        genes: list[str] = []
        seen_genes: set[str] = set()
        seen_sets: set[str] = set()
        with Path(path).open("r", encoding="utf-8-sig") as handle:
            for line_no, raw in enumerate(handle, 1):
                line = raw.rstrip("\r\n")
                if not line.strip():
                    continue
                fields = line.split("\t")
                if len(fields) < 2:
                    raise ReaderError(
                        f"GMT line {line_no} must contain a set name and a description"
                    )
                name = fields[0].strip()
                if not name:
                    raise ReaderError(f"GMT line {line_no} has an empty set name")
                if name in seen_sets:
                    raise ReaderError(f"GMT contains duplicate gene set {name!r}")
                seen_sets.add(name)
                members = []
                for raw_gene in fields[2:]:
                    gene = raw_gene.strip()
                    if not gene:
                        continue
                    if gene not in members:
                        members.append(gene)
                    if gene not in seen_genes:
                        seen_genes.add(gene)
                        genes.append(gene)
                sets.append((name, members))
        if not sets:
            raise ReaderError("GMT file contains no gene sets")
        if not genes:
            raise ReaderError("GMT file contains no genes")
        return sets, genes

    def probe(self, path, **args):
        sets, genes = self._parse(path)
        return {
            "file_bytes": Path(path).stat().st_size,
            "shape": (len(genes), len(sets)),
            "dtype": "float32",
            "dense_bytes": len(genes) * len(sets) * 4,
        }

    def read(self, path: Path, dims: list, labels: dict, **args) -> Form:
        if len(dims) != 2:
            raise ReaderError(f"GMT reader requires exactly two dims, got {dims}")
        gene_dim, set_dim = dims
        sets, genes = self._parse(path)

        gene_pos = {gene: i for i, gene in enumerate(genes)}
        data = np.zeros((len(genes), len(sets)), dtype=np.float32)
        set_names = []
        for j, (name, members) in enumerate(sets):
            set_names.append(name)
            for gene in members:
                data[gene_pos[gene], j] = 1.0

        def resolve(dim: str, builtin: list[str], source: str):
            rule = labels.get(dim, "builtin")
            if rule in (None, "builtin"):
                return unique_labels(builtin, dim, source)
            if rule == "auto":
                return {str(i): i for i in range(len(builtin))}
            if isinstance(rule, dict):
                return {str(k): int(v) for k, v in rule.items()}
            raise ReaderError(f"GMT reader: unsupported label rule for {dim!r}: {rule!r}")

        form = Form(
            data=data,
            dims=[gene_dim, set_dim],
            labels={
                gene_dim: resolve(gene_dim, genes, "gmt"),
                set_dim: resolve(set_dim, set_names, "gmt"),
            },
            info={"missing_code": np.nan},
        )
        form.validate()
        return form
