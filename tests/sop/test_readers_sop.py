"""SOP reader verification against independent parsers.

Each test reads real repository data through BioPipe and through a
different implementation (pandas, scipy, h5py, pysam, ...), then compares
the parts that define format semantics: shape, labels, coordinates,
missing values, and values. These tests are intentionally independent of
``tasks/verify_*.py`` and ``tasks/*_demo/test_*.py``.
"""
from __future__ import annotations

import gzip
from pathlib import Path

import h5py
import numpy as np
import pandas as pd
import pytest
from scipy.io import mmread

from src.reader import read_source

ROOT = Path(__file__).resolve().parents[2]
TASKS = ROOT / "tasks"


def _skip_if_missing(path: Path) -> None:
    if not path.exists() or path.stat().st_size == 0:
        pytest.skip(f"real SOP fixture is not present: {path.relative_to(ROOT)}")


def _read(path, dims, labels, **args):
    return read_source(path, dims, labels, **args)


def _unique(names):
    seen = set()
    result = []
    for i, name in enumerate(names):
        key = str(name)
        if key in seen:
            key = f"{key}#{i}"
        seen.add(key)
        result.append(key)
    return result


def _encode(form, dim, values):
    enc = form.info.get("encoders", {}).get(dim, {}).get(values)
    if enc is None:
        pytest.skip(f"no encoder for {dim}.{values}")
    return enc


# ---------------------------------------------------------------------------
# Tabular formats
# ---------------------------------------------------------------------------

def test_csv_matches_pandas():
    path = TASKS / "csv_demo/input/test_party_1.csv"
    _skip_if_missing(path)
    form = _read(path, ["sample", "feature"], {"sample": "auto", "feature": "builtin"})
    frame = pd.read_csv(path)
    assert form.data.shape == frame.shape
    assert list(form.labels["feature"]) == list(frame.columns)
    assert form.data.dtype == np.float32
    np.testing.assert_allclose(form.data, frame.to_numpy(dtype=np.float32))


def test_parquet_matches_pandas():
    path = TASKS / "parquet_demo/input/alltypes.parquet"
    _skip_if_missing(path)
    form = _read(path, ["sample", "feature"], {"sample": "auto", "feature": "builtin"})
    frame = pd.read_parquet(path).reset_index(drop=True)
    assert form.data.shape == frame.shape
    assert list(form.labels["feature"]) == [str(c) for c in frame.columns]


def test_tsv_and_txt_delegate_match_pandas(tmp_path):
    source = tmp_path / "table.tsv"
    frame = pd.DataFrame({"a": [1.0, 2.0], "b": [3.5, 4.5]})
    frame.to_csv(source, sep="\t", index=False)
    for suffix in (".tsv", ".txt"):
        path = tmp_path / ("table" + suffix)
        path.write_bytes(source.read_bytes())
        form = _read(path, ["sample", "feature"], {"sample": "auto", "feature": "builtin"})
        assert form.data.shape == (2, 2)
        np.testing.assert_allclose(form.data, frame.to_numpy(dtype=np.float32))


def test_bed_matches_manual_parse():
    path = TASKS / "bed_demo/input/example1.bed"
    _skip_if_missing(path)
    form = _read(path, ["region", "field"], {"region": "auto", "field": "builtin"})
    rows = [line.split() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert form.data.shape[0] == len(rows)
    labels = form.labels["field"]
    np.testing.assert_allclose(form.data[:, labels["chromStart"]], [float(r[1]) for r in rows])
    np.testing.assert_allclose(form.data[:, labels["chromEnd"]], [float(r[2]) for r in rows])
    chrom = _encode(form, "field", "chrom").inverse
    assert [chrom[int(v)] for v in form.data[:, labels["chrom"]]] == [r[0] for r in rows]


# ---------------------------------------------------------------------------
# Sequence and annotation
# ---------------------------------------------------------------------------

def test_fasta_matches_manual_parser():
    path = TASKS / "fasta_demo/input/sars_cov2.fasta"
    _skip_if_missing(path)
    form = _read(path, ["sequence", "position"], {"sequence": "builtin", "position": "auto"})
    ids, seqs = [], []
    current = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith(">"):
            if current:
                seqs.append("".join(current))
                current = []
            ids.append(line[1:].split()[0])
        elif line.strip():
            current.append(line.strip())
    if current:
        seqs.append("".join(current))
    assert list(form.labels["sequence"]) == ids
    assert form.data.shape[1] == max(map(len, seqs))
    codes = {"A": 0, "C": 1, "G": 2, "T": 3, "U": 3, "N": 4}
    for i, seq in enumerate(seqs):
        expected = [codes.get(ch.upper(), 5) for ch in seq]
        np.testing.assert_allclose(form.data[i, :len(seq)], expected)
    assert form.info["alphabet"] == "dna"


def test_gff3_and_gtf_match_manual_parse(tmp_path):
    cases = [
        (TASKS / "gff3_demo/input/homo_sapiens.gff3.gz", ".gff3", "seqid", "type"),
        (TASKS / "gtf_demo/input/homo_sapiens.gtf.gz", ".gtf", "seqname", "feature"),
    ]
    for source, suffix, seq_col, type_col in cases:
        _skip_if_missing(source)
        lines = []
        with gzip.open(source, "rt", encoding="utf-8") as handle:
            for line in handle:
                if line.startswith("##FASTA"):
                    break
                if line.startswith("#") or not line.strip():
                    continue
                lines.append(line.rstrip("\n").split("\t"))
                if len(lines) >= 300:
                    break
        path = tmp_path / ("subset" + suffix)
        path.write_text("\n".join("\t".join(r) for r in lines) + "\n", encoding="utf-8")
        form = _read(path, ["record", "field"], {"record": "auto", "field": "builtin"})
        assert form.data.shape[0] == len(lines)
        labels = form.labels["field"]
        np.testing.assert_allclose(form.data[:, labels["start"]], [float(r[3]) for r in lines])
        np.testing.assert_allclose(form.data[:, labels["end"]], [float(r[4]) for r in lines])
        seq_encoder = form.info.get("encoders", {}).get("field", {}).get(seq_col)
        if seq_encoder is None:
            # The first 300 records may all use numeric chromosome names.
            np.testing.assert_allclose(form.data[:, labels[seq_col]], [float(r[0]) for r in lines])
        else:
            assert [seq_encoder.inverse[int(v)] for v in form.data[:, labels[seq_col]]] == [r[0] for r in lines]
        type_encoder = form.info.get("encoders", {}).get("field", {}).get(type_col)
        assert type_encoder is not None
        assert [type_encoder.inverse[int(v)] for v in form.data[:, labels[type_col]]] == [r[2] for r in lines]


def test_gaf_matches_manual_parse(tmp_path):
    source = TASKS / "go_enrichment_demo/input/goa_human.gaf.gz"
    _skip_if_missing(source)
    lines = []
    with gzip.open(source, "rt", encoding="utf-8") as handle:
        for line in handle:
            if line.startswith("!") or not line.strip():
                continue
            lines.append(line.rstrip("\n").split("\t"))
            if len(lines) >= 200:
                break
    path = tmp_path / "subset.gaf"
    path.write_text("\n".join("\t".join(r) for r in lines) + "\n", encoding="utf-8")
    form = _read(path, ["annotation", "field"], {"annotation": "auto", "field": "builtin"})
    assert form.data.shape[0] == len(lines)
    go = _encode(form, "field", "go_id").inverse
    labels = form.labels["field"]
    assert [go[int(v)] for v in form.data[:, labels["go_id"]]] == [r[4] for r in lines]
    assert form.info["db_object_synonym"] == [r[10] for r in lines]


# ---------------------------------------------------------------------------
# Matrices and single cell
# ---------------------------------------------------------------------------

def test_mtx_matches_scipy(tmp_path):
    source = TASKS / "mtx_demo/input/matrix.mtx.gz"
    _skip_if_missing(source)
    form = _read(source, ["gene", "cell"], {"gene": "builtin", "cell": "builtin"})
    with gzip.open(source, "rt", encoding="utf-8") as handle:
        reference = mmread(handle).tocsr()
    assert form.data.shape == reference.shape
    assert form.data.sum() == pytest.approx(float(reference.sum()))
    dense = reference[:5, :20].toarray()
    np.testing.assert_allclose(form.data[:5, :20], dense)


def test_h5ad_matches_h5py():
    path = TASKS / "h5ad_demo/input/pbmc3k.h5ad"
    _skip_if_missing(path)
    form = _read(path, ["sample", "feature"], {"sample": "builtin", "feature": "builtin"})
    with h5py.File(path, "r") as handle:
        shape = tuple(int(v) for v in handle["X"].attrs["shape"])
        data = handle["X/data"][...]
        obs = [v.decode() if isinstance(v, bytes) else str(v) for v in handle["obs/index"][...]]
        var = [v.decode() if isinstance(v, bytes) else str(v) for v in handle["var/index"][...]]
    assert form.data.shape == shape
    assert form.data.sum() == pytest.approx(float(np.sum(data)))
    assert list(form.labels["sample"]) == obs
    assert list(form.labels["feature"]) == var


def test_tenx_h5_matches_h5py():
    path = TASKS / "multi_omics_route_demo/input/cite_seq_pbmc.h5"
    _skip_if_missing(path)
    form = _read(path, ["feature", "cell"], {"feature": "builtin", "cell": "builtin"},
                 feature_type="Gene Expression")
    with h5py.File(path, "r") as handle:
        features = handle["matrix/features"]
        names = [v.decode() if isinstance(v, bytes) else str(v) for v in features["name"][...]]
        types = [v.decode() if isinstance(v, bytes) else str(v) for v in features["feature_type"][...]]
        keep = [i for i, value in enumerate(types) if value == "Gene Expression"]
        data = handle["matrix/data"][...]
        indices = handle["matrix/indices"][...]
        selected = np.isin(indices, keep)
        expected_sum = float(np.sum(data[selected]))
        barcodes = [v.decode() if isinstance(v, bytes) else str(v) for v in handle["matrix/barcodes"][...]]
    assert form.data.shape == (len(keep), len(barcodes))
    assert form.data.sum() == pytest.approx(expected_sum)
    assert list(form.labels["feature"]) == _unique([names[i] for i in keep])
    assert list(form.labels["cell"]) == barcodes
