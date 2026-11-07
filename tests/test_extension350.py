"""Tests for the antiSMASH BGC operator."""

from __future__ import annotations

import json

import pytest

from src.core.errors import StepError
from src.task.context import Context
from src.task.runner import run
from src.task.step.steps._sequence_common import encode_sequences
from src.task.step.steps.antismash_bgc import parse_antismash_json

PAYLOAD = {
    "records": [{
        "id": "contig1",
        "features": [
            {"type": "CDS", "location": "[9:300](+)",
             "qualifiers": {"locus_tag": ["ctg1_1"], "gene": ["a"], "product": ["PKS"]}},
            {"type": "CDS", "location": "[399:700](-)",
             "qualifiers": {"locus_tag": ["ctg1_2"]}},
            {"type": "CDS", "location": "[1999:2300](+)",
             "qualifiers": {"locus_tag": ["ctg1_3"]}},
        ],
        "areas": [{
            "area_type": "region", "start": 0, "end": 1000,
            "products": ["T1PKS"], "protoclusters": [{"product": "T1PKS"}],
            "region_number": 1,
        }],
    }],
}

FAKE = r'''
import json, pathlib, sys
args = sys.argv[1:]
out = pathlib.Path(args[args.index("--output-dir") + 1])
out.mkdir(parents=True)
payload = {
    "records": [{
        "id": "contig1",
        "features": [{"type": "CDS", "location": "[9:300](+)",
                      "qualifiers": {"locus_tag": ["ctg1_1"]}}],
        "areas": [{"area_type": "region", "start": 0, "end": 1000,
                   "products": ["T1PKS"], "protoclusters": [{"product": "T1PKS"}],
                   "region_number": 1}],
    }],
}
(out / "input.json").write_text(json.dumps(payload))
'''


def test_parse():
    parsed = parse_antismash_json(json.dumps(PAYLOAD))
    assert parsed["n_records"] == 1
    region = parsed["regions"][0]
    assert region["products"] == ["T1PKS"]
    assert region["n_genes"] == 2
    assert region["genes"][1]["strand"] == -1
    assert parsed["product_counts"] == {"T1PKS": 1}


def test_parse_rejects_bad_json():
    with pytest.raises(StepError, match="invalid"):
        parse_antismash_json("{")


def test_run(tmp_path):
    binary = tmp_path / "antismash.py"
    binary.write_text(FAKE, encoding="utf-8")
    database = tmp_path / "db"
    database.mkdir()
    form = encode_sequences(["ATGC" * 300], "sequence", "position", "dna")
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    ctx["dna"] = form
    run(ctx, [{"name": "antismash_bgc", "inputs": ["dna"], "params": {
        "antismash_path": str(binary), "database_dir": str(database), "output": "regions"}}])
    out = ctx["regions"]
    assert out.dims == ["region", "statistic"]
    assert out.data.shape == (1, 5)
    assert out.data[0, 0] == 1 and out.data[0, 1] == 1000
    assert out.info["n_regions"] == 1
    assert out.info["product_counts"] == {"T1PKS": 1}
    assert list(out.labels["region"]) == ["contig1:region1"]


def test_run_errors(tmp_path):
    form = encode_sequences(["ATGC"], "sequence", "position", "dna")
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    ctx["dna"] = form
    with pytest.raises(StepError, match="database_dir"):
        run(ctx, [{"name": "antismash_bgc", "inputs": ["dna"], "params": {
            "database_dir": str(tmp_path / "missing")}}])
    binary = tmp_path / "noop.py"
    binary.write_text("import sys\nsys.exit(3)\n", encoding="utf-8")
    with pytest.raises(StepError, match="failed with exit code"):
        run(ctx, [{"name": "antismash_bgc", "inputs": ["dna"], "params": {
            "antismash_path": str(binary), "database_dir": str(tmp_path)}}])


def test_real_antismash_nisin(tmp_path):
    import os
    from pathlib import Path

    if os.environ.get("OPERON_ANTISMASH_REAL") != "1":
        pytest.skip("set OPERON_ANTISMASH_REAL=1 to run the real antiSMASH check")
    binary = Path(os.environ.get("OPERON_ANTISMASH_BIN", "/home/gavin/miniconda3/envs/antismash/bin/antismash"))
    database = Path(os.environ.get("OPERON_ANTISMASH_DB", "/home/gavin/tools/antismash_db"))
    fixture = Path(__file__).resolve().parent / "fixtures" / "antismash_nisin.gbk"
    if not binary.is_file() or not database.is_dir() or not fixture.is_file():
        pytest.skip("antiSMASH, its databases, or the nisin fixture is missing")
    SeqIO = pytest.importorskip("Bio.SeqIO")
    sequence = str(SeqIO.read(fixture, "genbank").seq)
    form = encode_sequences([sequence], "sequence", "position", "dna")
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    ctx["dna"] = form
    run(ctx, [{"name": "antismash_bgc", "inputs": ["dna"], "params": {
        "antismash_path": str(binary), "database_dir": str(database),
        "taxon": "bacteria", "output": "regions"}}])
    out = ctx["regions"]
    assert out.info["n_regions"] >= 1
    products = {product for region in out.info["regions"] for product in region["products"]}
    assert any("lanthipeptide" in product or product == "LAP" for product in products), products
