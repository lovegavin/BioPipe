"""Shared parsing helpers for GSEA ranked-list and phenotype files."""
from __future__ import annotations

import math
from pathlib import Path

import pandas as pd

from src.core import Form, ReaderError
from src.reader.readers._table_common import table_form


def read_lines(path: Path, source: str) -> list[str]:
    try:
        return Path(path).read_text(encoding="utf-8-sig").splitlines()
    except OSError as exc:
        raise ReaderError(f"{source} reader: cannot read {path}: {exc}") from exc


def parse_rnk(
    path: Path,
    *,
    header: bool,
    comment: str,
    gene_column: int,
    score_column: int,
) -> tuple[list[str], list[float]]:
    """Parse a two-or-more-column GSEA .rnk ranked list."""
    lines = read_lines(path, "RNK")
    genes: list[str] = []
    scores: list[float] = []
    seen: set[str] = set()
    first_data = True
    for line_no, raw in enumerate(lines, 1):
        line = raw.strip()
        if not line:
            continue
        if comment and line.startswith(comment):
            continue
        if header and first_data:
            first_data = False
            continue
        first_data = False
        fields = line.split("\t") if "\t" in line else line.split()
        if len(fields) <= max(gene_column, score_column):
            raise ReaderError(
                f"RNK line {line_no}: expected at least "
                f"{max(gene_column, score_column) + 1} columns, got {len(fields)}"
            )
        gene = fields[gene_column].strip()
        if not gene:
            raise ReaderError(f"RNK line {line_no}: empty gene identifier")
        if gene in seen:
            raise ReaderError(f"RNK contains duplicate gene {gene!r}")
        try:
            score = float(fields[score_column])
        except ValueError as exc:
            raise ReaderError(
                f"RNK line {line_no}: score {fields[score_column]!r} is not numeric"
            ) from exc
        if not math.isfinite(score):
            raise ReaderError(f"RNK line {line_no}: score must be finite")
        seen.add(gene)
        genes.append(gene)
        scores.append(score)
    if not genes:
        raise ReaderError("RNK file contains no ranked genes")
    return genes, scores


def parse_phenotype(path: Path, source: str) -> tuple[list[str], list[str], list[str]]:
    """Parse GSEA .cls or .grp phenotype labels.

    Returns (sample_names, class_names, sample_classes). The first line
    carries sample/class counts (an optional trailing ``1`` is accepted),
    the second line starts with ``#`` and lists class names, and the
    remaining whitespace-separated integers index those classes.
    """
    lines = [raw.strip() for raw in read_lines(path, source) if raw.strip()]
    if len(lines) < 3:
        raise ReaderError(f"{source} reader: file has fewer than 3 non-empty lines")

    header = lines[0].split()
    if len(header) not in (2, 3):
        raise ReaderError(
            f"{source} reader: header must be '<n_samples> <n_classes>' "
            f"optionally followed by 1, got {lines[0]!r}"
        )
    try:
        n_samples = int(header[0])
        n_classes = int(header[1])
    except ValueError as exc:
        raise ReaderError(f"{source} reader: invalid header {lines[0]!r}") from exc
    if n_samples < 1 or n_classes < 1:
        raise ReaderError(f"{source} reader: sample and class counts must be positive")

    class_line = lines[1]
    if not class_line.startswith("#"):
        raise ReaderError(
            f"{source} reader: second line must start with '#' and list class names"
        )
    classes = class_line[1:].split()
    if len(classes) != n_classes:
        raise ReaderError(
            f"{source} reader: expected {n_classes} class names, got {len(classes)}"
        )
    if len(set(classes)) != len(classes):
        raise ReaderError(f"{source} reader: duplicate class names in {classes!r}")

    tokens: list[str] = []
    for line in lines[2:]:
        tokens.extend(line.split())
    if len(tokens) != n_samples:
        raise ReaderError(
            f"{source} reader: expected {n_samples} sample class indices, got {len(tokens)}"
        )
    sample_classes: list[str] = []
    for i, token in enumerate(tokens):
        try:
            code = int(token)
        except ValueError as exc:
            raise ReaderError(
                f"{source} reader: sample {i + 1} class index {token!r} is not an integer"
            ) from exc
        if not 0 <= code < n_classes:
            raise ReaderError(
                f"{source} reader: sample {i + 1} class index {code} is outside "
                f"0..{n_classes - 1}"
            )
        sample_classes.append(classes[code])

    samples = [f"S{i + 1}" for i in range(n_samples)]
    return samples, classes, sample_classes


def phenotype_form(
    path: Path,
    dims: list,
    labels: dict,
    args: dict,
    source: str,
) -> Form:
    """Return a one-column [sample, phenotype] Form."""
    if len(dims) != 2:
        raise ReaderError(f"{source} reader requires exactly two dims, got {dims}")
    sample_dim, feature_dim = dims
    samples, classes, sample_classes = parse_phenotype(path, source)
    feature_label = str(args.get("feature_label", "class")).strip()
    if not feature_label:
        raise ReaderError(f"{source} reader: feature_label must not be empty")
    df = pd.DataFrame({feature_label: sample_classes})
    return table_form(
        df,
        [sample_dim, feature_dim],
        labels,
        source,
        encoders_cfg=args.get("encoders") or {},
        row_labels=samples,
        col_labels=[feature_label],
        info_extra={
            "classes": classes,
            "n_samples": len(samples),
            "n_classes": len(classes),
        },
    )
