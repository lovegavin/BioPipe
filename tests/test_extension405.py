from __future__ import annotations

import math

import numpy as np
import pytest

from src.core import FileArtifact, Form, StepError
from src.task.step.steps.gwas_association import GwasAssociationStep
from src.task.step.steps.gwas_inflation import GwasInflationStep
from src.task.step.steps.gwas_top_hits import GwasTopHitsStep


class Ctx(dict):
    def __init__(self, params, root):
        super().__init__()
        self.step_params = dict(params)


HEADER = (
    "##fileformat=VCFv4.2\n"
    "##contig=<ID=22,length=1000000>\n"
    "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT"
)


def write_vcf(path, rows, samples):
    lines = [HEADER + "\t" + "\t".join(samples)]
    lines.extend(rows)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return path


def phenotype_form(values, samples):
    data = np.asarray(values, dtype=float).reshape(-1, 1)
    return Form(
        data,
        dims=["sample", "field"],
        labels={
            "sample": {name: index for index, name in enumerate(samples)},
            "field": {"value": 0},
        },
    )


SAMPLES = ("S1", "S2", "S3", "S4", "S5", "S6")


def toy_vcf(tmp_path):
    rows = [
        "22\t100\t.\tA\tG\t50\tPASS\t.\tGT\t0/0\t0/0\t0/1\t0/1\t1/1\t1/1",
        "22\t200\t.\tC\tT\t50\tPASS\t.\tGT\t0/0\t0/1\t0/1\t1/1\t0/0\t0/1",
        "22\t300\t.\tG\tA\t50\tPASS\t.\tGT\t0/0\t0/0\t0/0\t0/0\t0/0\t0/0",
    ]
    return write_vcf(tmp_path / "toy.vcf", rows, SAMPLES)


def run_association(tmp_path, values, model="linear"):
    source = toy_vcf(tmp_path)
    params = {
        "model": model,
        "min_maf": 0.0,
        "max_variants": 0,
        "row_dim": "sample",
        "field_dim": "field",
        "value_field": "value",
        "output": "assoc",
    }
    ctx = Ctx(params, tmp_path)
    step = GwasAssociationStep()
    step.run(ctx, [FileArtifact("vcf", {"variants": str(source)}), phenotype_form(values, SAMPLES)])
    out = ctx["assoc"]
    columns = out.labels["statistic"]
    variants = {index: name for name, index in out.labels["variant"].items()}
    rows = {}
    for index, name in variants.items():
        rows[name] = {key: float(out.data[index][column]) for key, column in columns.items()}
    return rows, out


def test_linear_association_matches_hand_calculation(tmp_path):
    values = [0.0, 1.0, 1.0, 2.0, 2.0, 3.0]
    rows, out = run_association(tmp_path, values)
    assert len(rows) == 2  # monomorphic variant 300 is skipped
    hit = rows["22:100:A:G"]
    assert hit["beta"] == pytest.approx(1.0, abs=1e-12)
    assert hit["se"] == pytest.approx(math.sqrt(0.375 / 4.0), rel=1e-12)
    assert hit["stat"] == pytest.approx(1.0 / math.sqrt(0.375 / 4.0), rel=1e-12)
    assert 0.01 < hit["p"] < 0.05
    assert hit["n"] == 6
    assert hit["maf"] == pytest.approx(0.5, rel=1e-12)


def test_logistic_association_runs(tmp_path):
    values = [0.0, 1.0, 0.0, 1.0, 1.0, 0.0]
    rows, _ = run_association(tmp_path, values, model="logistic")
    assert "22:100:A:G" in rows
    assert 0.0 <= rows["22:100:A:G"]["p"] <= 1.0


def test_logistic_rejects_continuous_phenotype(tmp_path):
    values = [0.0, 0.3, 0.5, 0.7, 0.9, 1.2]
    with pytest.raises(StepError, match="binary phenotype"):
        run_association(tmp_path, values, model="logistic")


def test_missing_phenotype_column(tmp_path):
    source = toy_vcf(tmp_path)
    flat = phenotype_form([0.0, 1.0, 1.0, 2.0, 2.0, 3.0], SAMPLES)
    flat.labels["field"] = {"other": 0}
    ctx = Ctx({"output": "assoc"}, tmp_path)
    with pytest.raises(StepError, match="column 'value' is missing"):
        GwasAssociationStep().run(
            ctx, [FileArtifact("vcf", {"variants": str(source)}), flat]
        )


def association_form(rows, samples=("v1",)):
    names = [row[0] for row in rows]
    columns = {"p": 0, "beta": 1, "se": 2}
    data = [[row[1], row[2], row[3]] for row in rows]
    return Form(
        data,
        dims=["variant", "statistic"],
        labels={
            "variant": {name: index for index, name in enumerate(names)},
            "statistic": columns,
        },
    )


def test_inflation_lambda_is_one_for_uniform_pvalues(tmp_path):
    rows = [(f"22:{i}:A:G", 0.5, 0.0, 0.1) for i in range(20)]
    ctx = Ctx({"output": "infl"}, tmp_path)
    GwasInflationStep().run(ctx, [association_form(rows)])
    out = ctx["infl"]
    values = {name: float(out.data[index][0]) for name, index in out.labels["statistic"].items()}
    assert values["lambda"] == pytest.approx(1.0, abs=0.15)
    assert values["n_variants"] == 20


def test_inflation_detects_signal(tmp_path):
    rows = [(f"22:{i}:A:G", 1e-9 if i == 0 else 0.5, 0.0, 0.1) for i in range(50)]
    ctx = Ctx({"output": "infl"}, tmp_path)
    GwasInflationStep().run(ctx, [association_form(rows)])
    out = ctx["infl"]
    values = {name: float(out.data[index][0]) for name, index in out.labels["statistic"].items()}
    assert 0.8 < values["lambda"] < 1.2
    assert values["min_p"] == pytest.approx(1e-9)


def test_top_hits_clumps_nearby_variants(tmp_path):
    rows = [
        ("22:100:A:G", 1e-9, 0.5, 0.05),
        ("22:200:A:G", 1e-8, 0.4, 0.06),
        ("22:5000:A:G", 1e-20, 0.9, 0.02),
        ("22:300:A:G", 0.2, 0.1, 0.1),
    ]
    ctx = Ctx({"output": "hits", "threshold": 5e-8, "clump_distance": 1000000}, tmp_path)
    GwasTopHitsStep().run(ctx, [association_form(rows)])
    out = ctx["hits"]
    names = {index: name for name, index in out.labels["variant"].items()}
    assert list(names.values()) == ["22:5000:A:G"]


def test_top_hits_keeps_distant_variants(tmp_path):
    rows = [
        ("22:100:A:G", 1e-9, 0.5, 0.05),
        ("22:9000000:A:G", 1e-8, 0.4, 0.06),
    ]
    ctx = Ctx({"output": "hits", "threshold": 5e-8, "clump_distance": 1000000}, tmp_path)
    GwasTopHitsStep().run(ctx, [association_form(rows)])
    out = ctx["hits"]
    assert len(out.labels["variant"]) == 2


def test_top_hits_reports_empty_selection(tmp_path):
    rows = [("22:100:A:G", 0.5, 0.1, 0.1)]
    ctx = Ctx({"output": "hits", "threshold": 5e-8, "clump_distance": 1000}, tmp_path)
    with pytest.raises(StepError, match="no variant passed"):
        GwasTopHitsStep().run(ctx, [association_form(rows)])
