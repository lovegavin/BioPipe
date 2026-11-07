"""PLINK 1.9 transposed pedigree (.tped / .tfam) reader."""
from __future__ import annotations

from pathlib import Path

import numpy as np

from src.core import Form, ReaderError
from src.reader.base import Reader
from src.reader.readers._labels import unique_labels


class TpedReader(Reader):
    """Reader for PLINK 1.9 transposed genotype files.

    Each ``.tped`` row is ``chrom id cm pos`` followed by two allele codes
    per sample; ``.tfam`` lists the samples. Codes are ``0`` (missing),
    ``1`` (first allele) and ``2`` (second allele); the value stored for a
    call is the count of the first allele, so heterozygous calls are ``1``.
    """

    provider = 'operon-readers'
    parameters_file = 'tped_reader.TpedReader.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'TpedReader',
     'version': '1.0.0',
     'kind': 'reader',
     'title': 'PLINK .tped genotype reader',
     'category': 'Data',
     'contracts': {'version': 1,
                   'inputs': [],
                   'output': {'version': 1,
                              'numeric': True,
                              'info': {'missing_code': {'type': ['number', 'null']},
                                       'representation': {'type': 'string', 'const': 'hard_call'},
                                       'ploidy': {'type': 'integer', 'min': 1, 'const': 2},
                                       'chrom': {'type': 'array', 'items': 'string'},
                                       'pos': {'type': 'array', 'items': 'integer'},
                                       'coding': {'type': 'string'}},
                              'dims': [],
                              'labels': [],
                              'parallel': [],
                              'ndim': 2,
                              'values': 'allele_count',
                              'axis_fields': [{'axis': 0, 'fields': ['chrom', 'pos']}],
                              'info_open': False}},
     'resources': {'memory_modes': ['full'], 'supports_cuda': False},
     'dependencies': ['numpy>=1.24'],
     'dependency_imports': ['numpy'],
     'description': 'PLINK 1.9 .tped/.tfam hard-call genotypes.',
     'extensions': ['.tped'],
     'requires_siblings': ['.tfam'],
     'excludes_siblings': [],
     'handles_compression': False,
     'file_input': {'dims': ['variant', 'sample'],
                    'labels': {'variant': 'builtin', 'sample': 'builtin'}}}

    def read(self, path: Path, dims: list, labels: dict, **args) -> Form:
        if len(dims) != 2:
            raise ReaderError(f"TPED reader requires exactly two dims, got {dims}")
        variant_dim, sample_dim = dims
        path = Path(path)
        tfam_path = path.with_suffix(".tfam")
        if not tfam_path.exists():
            raise ReaderError(f"TPED reader requires the sibling {tfam_path.name}")

        sample_ids: list[str] = []
        for line in tfam_path.read_text(encoding="utf-8", errors="replace").splitlines():
            fields = line.split()
            if not fields:
                continue
            if len(fields) < 2:
                raise ReaderError(
                    f"TPED reader: .tfam line needs at least two columns: {line!r}"
                )
            sample_ids.append(fields[1])
        if not sample_ids:
            raise ReaderError("TPED reader: .tfam has no samples")
        n_samples = len(sample_ids)

        variants: list[str] = []
        chroms: list[str] = []
        positions: list[int] = []
        rows: list[np.ndarray] = []
        for number, line in enumerate(
            path.read_text(encoding="utf-8", errors="replace").splitlines(), start=1
        ):
            fields = line.split()
            if not fields:
                continue
            if len(fields) != 4 + 2 * n_samples:
                raise ReaderError(
                    f"TPED reader: line {number} has {len(fields)} columns but "
                    f"{4 + 2 * n_samples} were expected for {n_samples} samples"
                )
            chrom, variant_id, _cm, pos = fields[:4]
            try:
                position = int(pos)
            except ValueError as exc:
                raise ReaderError(
                    f"TPED reader: line {number} has a non-integer position {pos!r}"
                ) from exc
            codes = fields[4:]
            dosage = np.empty(n_samples, dtype=np.float32)
            for index in range(n_samples):
                first = codes[2 * index]
                second = codes[2 * index + 1]
                if first not in ("0", "1", "2") or second not in ("0", "1", "2"):
                    raise ReaderError(
                        f"TPED reader: line {number} has an invalid allele code "
                        f"{first!r}/{second!r}"
                    )
                if first == "0" or second == "0":
                    dosage[index] = np.nan
                else:
                    dosage[index] = float((first == "1") + (second == "1"))
            chroms.append(chrom)
            positions.append(position)
            variants.append(variant_id if variant_id != "." else f"{chrom}:{position}")
            rows.append(dosage)

        if not rows:
            raise ReaderError("TPED reader: file has no variants")

        final: dict[str, dict[str, int]] = {}
        for dim_name, builtin in (
            (variant_dim, variants),
            (sample_dim, sample_ids),
        ):
            rule = labels.get(dim_name, "builtin")
            if rule in (None, "builtin"):
                final[dim_name] = unique_labels(builtin, dim_name, "tped")
            elif rule == "auto":
                final[dim_name] = {str(i): i for i in range(len(builtin))}
            elif isinstance(rule, dict):
                final[dim_name] = {str(key): int(value) for key, value in rule.items()}
            else:
                raise ReaderError(
                    f"TPED reader: unsupported label rule for '{dim_name}': {rule!r}"
                )

        return Form(
            data=np.vstack(rows).astype(np.float32),
            dims=list(dims),
            labels=final,
            info={
                "missing_code": np.nan,
                "representation": "hard_call",
                "ploidy": 2,
                "chrom": chroms,
                "pos": positions,
                "coding": "1=first allele, 2=second allele, 0=missing",
            },
            axis_info={variant_dim: ["chrom", "pos"]},
        )
