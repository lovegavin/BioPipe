"""Tests for the AMRFinderPlus operator."""

from __future__ import annotations

import pytest

from src.core.errors import StepError
from src.task.context import Context
from src.task.runner import run
from src.task.step.steps._sequence_common import encode_sequences
from src.task.step.steps.amrfinder_plus import parse_report

HEADER = ("Protein identifier\tContig id\tStart\tStop\tStrand\tElement symbol\tElement name\t"
          "Scope\tType\tSubtype\tClass\tSubclass\tMethod\tTarget length\t"
          "Reference sequence length\t% Coverage of reference sequence\t"
          "% Identity to reference sequence\tAlignment length\tAccession of closest sequence\t"
          "Name of closest sequence\tHMM id\tHMM description")
ROW = ("q1\tcontig1\t1\t286\t+\tblaTEM\tbeta-lactamase TEM\tcore\tAMR\t"
       "BETA-LACTAM\tBETA-LACTAM\tTEM\tAMR\t286\t286\t100.00\t100.00\t286\t"
       "WP_000000001.1\tbeta-lactamase TEM-1\tNA\tNA")
REPORT = HEADER + "\n" + ROW + "\n"

FAKE = r'''
import pathlib, sys
args = sys.argv[1:]
out = pathlib.Path(args[args.index("-o") + 1])
header = "Protein identifier\tContig id\tStart\tStop\tStrand\tElement symbol\tElement name\tScope\tType\tSubtype\tClass\tSubclass\tMethod\tTarget length\tReference sequence length\t% Coverage of reference sequence\t% Identity to reference sequence\tAlignment length\tAccession of closest sequence\tName of closest sequence\tHMM id\tHMM description"
row = "q1\tcontig1\t1\t286\t+\tblaTEM\tbeta-lactamase TEM\tcore\tAMR\tBETA-LACTAM\tBETA-LACTAM\tTEM\tAMR\t286\t286\t100.00\t100.00\t286\tWP_000000001.1\tbeta-lactamase TEM-1\tNA\tNA"
out.write_text(header + "\n" + row + "\n")
'''


def test_parse():
    hits = parse_report(REPORT)
    assert len(hits) == 1
    hit = hits[0]
    assert hit["gene"] == "blaTEM" and hit["class"] == "BETA-LACTAM"
    assert hit["coverage"] == pytest.approx(100.0)
    assert hit["identity"] == pytest.approx(100.0)


def test_run(tmp_path):
    binary = tmp_path / "amrfinder.py"
    binary.write_text(FAKE, encoding="utf-8")
    database = tmp_path / "db"
    database.mkdir()
    form = encode_sequences(["MKVLAAGIVGLLLA"], "sequence", "position", "protein")
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    ctx["protein"] = form
    run(ctx, [{"name": "amrfinder_plus", "inputs": ["protein"], "params": {
        "amrfinder_path": str(binary), "database_dir": str(database), "output": "hits"}}])
    out = ctx["hits"]
    assert out.dims == ["hit", "statistic"]
    assert out.data.shape == (1, 7)
    assert out.data[0, 4] == 100.0
    assert out.info["n_hits"] == 1
    assert out.info["genes"] == ["blaTEM"]


def test_run_errors(tmp_path):
    database = tmp_path / "db"
    database.mkdir()
    form = encode_sequences(["MKV"], "sequence", "position", "protein")
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    ctx["protein"] = form
    with pytest.raises((StepError, ValueError)):
        run(ctx, [{"name": "amrfinder_plus", "inputs": ["protein"], "params": {
            "database_dir": str(database), "mode": "dna"}}])
    with pytest.raises(StepError, match="is not a directory"):
        run(ctx, [{"name": "amrfinder_plus", "inputs": ["protein"], "params": {
            "database_dir": str(tmp_path / "missing")}}])
    with pytest.raises(StepError, match="was not found"):
        run(ctx, [{"name": "amrfinder_plus", "inputs": ["protein"], "params": {
            "database_dir": str(database), "amrfinder_path": str(tmp_path / "missing")}}])


TEM1 = (
    "MSIQHFRVALIPFFAAFCLPVFAHPETLVKVKDAEDQLGARVGYIELDLNSGKILESFRPEERFPMMSTFKVLLCGAVLSRIDAGQEQLGRRIHYSQNDLVEYSPVTEKHLTDGMTVRELCSAAITMSDNTAANLLLTTIGGPKELTAFLHNMGDHVTRLDRWEPELNEAIPNDERDTTMPVAMATTLRKLLTGELLTLASRQQLIDWMEADKVAGPLLRSALPAGWFIADKSGAGERGSRGIIAALGPDGKPSRIVVIYTTGSQATMDERNRQIAEIGASLIKHW"
)


def test_real_amrfinder_tem1(tmp_path):
    import os
    import shutil
    from pathlib import Path

    if os.environ.get("OPERON_AMRFINDER_REAL") != "1":
        pytest.skip("set OPERON_AMRFINDER_REAL=1 to run the real AMRFinderPlus check")
    binary = os.environ.get("OPERON_AMRFINDER_BIN", "/home/gavin/miniconda3/envs/amrfinder/bin/amrfinder")
    if not Path(binary).is_file() and shutil.which("amrfinder"):
        binary = shutil.which("amrfinder")
    database = Path(os.environ.get("OPERON_AMRFINDER_DB", "/home/gavin/tools/amrfinder_db/2026-10-29.1"))
    if not Path(binary).is_file() or not (database / "AMRProt.fa").is_file():
        pytest.skip("AMRFinderPlus or its database is missing")
    form = encode_sequences([TEM1], "sequence", "position", "protein")
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    ctx["protein"] = form
    run(ctx, [{"name": "amrfinder_plus", "inputs": ["protein"], "params": {
        "amrfinder_path": str(binary), "database_dir": str(database),
        "mode": "protein", "output": "hits"}}])
    out = ctx["hits"]
    assert out.info["n_hits"] >= 1
    genes = {hit["gene"] for hit in out.info["hits"]}
    assert any(gene.startswith("bla") for gene in genes), genes
