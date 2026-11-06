"""PRS harmonisation, frequency filtering and LD clumping tests (extension 384)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from src.core import FileArtifact, Form, StepError
from src.task.step.steps.prs_af_filter import PrsAfFilterStep
from src.task.step.steps.prs_harmonize import PrsHarmonizeStep
from src.task.step.steps.prs_ld_clump import PrsLdClumpStep


_VCF = """##fileformat=VCFv4.2
##contig=<ID=22,length=50818468>
#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tS1\tS2\tS3\tS4\tS5\tS6
22\t100\trs1\tA\tG\t.\tPASS\t.\tGT\t0/0\t0/1\t1/1\t0/1\t0/0\t1/1
22\t150\trs4\tT\tC\t.\tPASS\t.\tGT\t0/0\t0/0\t0/0\t0/0\t0/0\t0/1
22\t200\trs2\tC\tT\t.\tPASS\t.\tGT\t0/0\t0/1\t1/1\t0/1\t0/0\t1/1
22\t300\trs3\tA\tG\t.\tPASS\t.\tGT\t0/1\t0/1\t0/1\t0/1\t0/1\t0/1
"""

_WEIGHTS = """#genome_build=GRCh37
rsID\tchr_name\tchr_position\teffect_allele\tother_allele\teffect_weight
rs1\t22\t100\tG\tA\t0.5
rs4\t22\t150\tC\tT\t0.1
rs2\t22\t200\tC\tT\t0.4
rs3\t22\t300\tT\tA\t0.3
rs5\t22\t999\tA\tG\t0.2
"""


class Ctx(dict):
    def __init__(self, params, root=None):
        super().__init__()
        self.step_params = dict(params)
        self._root = root or Path(".")

    def artifact_path(self, name):
        return str(self._root / name)


def _vcf_artifact(tmp_path):
    path = Path(tmp_path) / "genotypes.vcf"
    path.write_text(_VCF, encoding="utf-8")
    return FileArtifact("vcf", {"genotypes": str(path)})


def _weights_artifact(tmp_path):
    path = Path(tmp_path) / "weights.tsv"
    path.write_text(_WEIGHTS, encoding="utf-8")
    return FileArtifact("tsv", {"weights": str(path)})


def _weights_form(names, betas):
    form = Form(
        np.asarray(betas, dtype=float).reshape(-1, 1),
        dims=["variant", "statistic"],
        labels={"variant": {name: index for index, name in enumerate(names)},
                "statistic": {"weight": 0}},
    )
    return form


def _run(cls, ctx, inputs):
    step = cls()
    step.name = step.definition["id"]
    step.run(ctx, inputs)
    return step


def test_harmonize_form_values(tmp_path):
    ctx = Ctx({"output": "h", "variant_dim": "variant", "statistic_dim": "statistic"}, tmp_path)
    _run(PrsHarmonizeStep, ctx, [_vcf_artifact(tmp_path), _weights_artifact(tmp_path)])
    form = ctx["h"]
    weights = {name: float(form.data[pos, 0]) for name, pos in form.labels["variant"].items()}
    assert set(weights) == {"rs1", "rs4", "rs2"}
    assert weights["rs1"] == pytest.approx(0.5)
    assert weights["rs2"] == pytest.approx(-0.4)
    assert weights["rs4"] == pytest.approx(0.1)
    assert form.info["n_ambiguous"] == 1
    assert form.info["n_absent"] == 1
    assert form.info["effect_allele"] == "ALT"


def test_harmonize_missing_ids_are_absent(tmp_path):
    ctx = Ctx({"output": "h"}, tmp_path)
    _run(PrsHarmonizeStep, ctx, [_vcf_artifact(tmp_path), _weights_artifact(tmp_path)])
    assert ctx["h"].info["n_variants"] == 3


def test_af_filter_drops_rare_variant(tmp_path):
    weights = _weights_form(["rs1", "rs4", "rs2"], [0.5, 0.1, -0.4])
    ctx = Ctx({"output": "f", "min_maf": 0.2, "max_missing_rate": 0.5}, tmp_path)
    _run(PrsAfFilterStep, ctx, [_vcf_artifact(tmp_path), weights])
    form = ctx["f"]
    assert form.info["n_kept"] == 2
    assert form.info["n_dropped_rare"] == 1
    assert set(form.labels["variant"]) == {"rs1", "rs2"}


def test_af_filter_keeps_common_variants(tmp_path):
    weights = _weights_form(["rs1", "rs2"], [0.5, -0.4])
    ctx = Ctx({"output": "f", "min_maf": 0.2}, tmp_path)
    _run(PrsAfFilterStep, ctx, [_vcf_artifact(tmp_path), weights])
    assert ctx["f"].info["n_kept"] == 2


def test_ld_clump_prunes_correlated_weaker_weight(tmp_path):
    weights = _weights_form(["rs1", "rs2"], [0.5, -0.4])
    ctx = Ctx({"output": "c", "r2_threshold": 0.2, "window_bp": 1000}, tmp_path)
    _run(PrsLdClumpStep, ctx, [_vcf_artifact(tmp_path), weights])
    form = ctx["c"]
    assert form.info["n_kept"] == 1
    assert form.info["n_pruned"] == 1
    assert set(form.labels["variant"]) == {"rs1"}


def test_ld_clump_keeps_unlinked_weights(tmp_path):
    weights = _weights_form(["rs1", "rs2"], [0.5, -0.4])
    ctx = Ctx({"output": "c", "r2_threshold": 1.0, "window_bp": 1000}, tmp_path)
    _run(PrsLdClumpStep, ctx, [_vcf_artifact(tmp_path), weights])
    assert ctx["c"].info["n_kept"] == 2


def test_ld_clump_respects_window(tmp_path):
    weights = _weights_form(["rs1", "rs2"], [0.5, -0.4])
    ctx = Ctx({"output": "c", "r2_threshold": 0.0, "window_bp": 10}, tmp_path)
    _run(PrsLdClumpStep, ctx, [_vcf_artifact(tmp_path), weights])
    assert ctx["c"].info["n_kept"] == 2


def test_harmonize_rejects_non_file(tmp_path):
    step = PrsHarmonizeStep()
    with pytest.raises(StepError):
        step.run(Ctx({"output": "h"}, tmp_path), [object(), _weights_artifact(tmp_path)])
