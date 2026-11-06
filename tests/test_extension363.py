"""B1 VCF operators: hand-built small inputs with exact expected values."""
from __future__ import annotations

import numpy as np
import pytest

from src.core import FileArtifact, Form, StepError
from src.task.context import Context
from src.task.step.steps.vcf_concordance import VcfConcordanceStep
from src.task.step.steps.vcf_filter import VcfFilterStep
from src.task.step.steps.vcf_relatedness import VcfRelatednessStep
from src.task.step.steps.vcf_stats import VcfStatsStep


HEADER = (
    "##fileformat=VCFv4.2\n"
    "##contig=<ID=chr1,length=1000000>\n"
    "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\t{samples}\n"
)


def _artifact(tmp_path, name, body, samples=("S1", "S2")):
    path = tmp_path / name
    path.write_text(HEADER.format(samples="\t".join(samples)) + body, encoding="utf-8")
    return FileArtifact("vcf", {"variants": str(path)}, {})


def _run(step, params, inputs, tmp_path):
    ctx = Context(tmp_path / "task", {})
    ctx.step_params = dict(params)
    step.run(ctx, inputs)
    return ctx, step.export(ctx)


def _values(form):
    axis = form.dims[0]
    return {
        label: float(form.data[index, 0])
        for label, index in form.labels[axis].items()
    }


BODY = (
    "chr1\t100\t.\tA\tG\t50\tPASS\t.\tGT:DP\t0/0:10\t0/1:12\n"
    "chr1\t200\t.\tC\tT\t10\tq10\t.\tGT:DP\t1/1:8\t0/1:9\n"
    "chr1\t300\t.\tAT\tA\t60\tPASS\t.\tGT:DP\t0/1:11\t0/0:10\n"
    "chr1\t400\t.\tG\tA,C\t30\tPASS\t.\tGT:DP\t1/2:7\t0/0:9\n"
    "chr1\t500\t.\tT\tC\t.\tPASS\t.\tGT:DP\t./.:.\t0/0:6\n"
)


def test_vcf_stats_hand_counts(tmp_path):
    ctx, report = _run(
        VcfStatsStep(),
        {"region": "", "max_records": 0, "output": "stats"},
        [_artifact(tmp_path, "sites.vcf", BODY)],
        tmp_path,
    )
    values = _values(ctx["stats"])
    assert values["n_variants"] == 5
    assert values["n_snps"] == 5  # per ALT allele; 400 contributes two
    assert values["n_indels"] == 1
    assert values["n_other"] == 0
    assert values["n_multiallelic"] == 1
    assert values["n_pass"] == 4
    assert values["n_transitions"] == 4  # A>G, C>T, T>C, G>A
    assert values["n_transversions"] == 1  # G>C at 400
    assert values["ts_tv_ratio"] == pytest.approx(4.0)
    assert values["mean_qual"] == pytest.approx(37.5)
    assert values["n_samples"] == 2
    assert values["n_chromosomes"] == 1
    assert values["n_no_alt"] == 0
    assert report["n_variants"] == 5


def test_vcf_stats_region_and_empty_input(tmp_path):
    artifact = _artifact(tmp_path, "sites.vcf", BODY)
    ctx, _ = _run(VcfStatsStep(), {"region": "1:200-400", "output": "s"}, [artifact], tmp_path)
    assert _values(ctx["s"])["n_variants"] == 3

    empty = _artifact(tmp_path, "empty.vcf", "")
    ctx, _ = _run(VcfStatsStep(), {"output": "s2"}, [empty], tmp_path)
    assert _values(ctx["s2"])["n_variants"] == 0
    assert _values(ctx["s2"])["ts_tv_ratio"] == 0.0


def test_vcf_filter_preserves_header_and_selected_lines(tmp_path):
    artifact = _artifact(tmp_path, "sites.vcf", BODY)
    ctx, report = _run(
        VcfFilterStep(),
        {"require_pass": True, "biallelic_only": True, "output": "kept"},
        [artifact],
        tmp_path,
    )
    kept = ctx["kept"]
    assert isinstance(kept, FileArtifact) and kept.format == "vcf"
    text = open(kept.files["variants"], encoding="utf-8").read()
    assert text.startswith("##fileformat=VCFv4.2")
    lines = [line for line in text.splitlines() if not line.startswith("#")]
    assert [line.split("\t")[1] for line in lines] == ["100", "300", "500"]
    assert report["n_input"] == 5 and report["n_output"] == 3
    assert report["removed"]["filter"] == 1  # 200
    assert report["removed"]["type"] == 1  # 400 is multi-allelic
    path = kept.files["variants"]
    assert path.startswith(str(ctx.out_dir))


def test_vcf_filter_rejects_empty_result(tmp_path):
    artifact = _artifact(tmp_path, "sites.vcf", BODY)
    with pytest.raises(StepError, match="no records passed"):
        _run(
            VcfFilterStep(),
            {"min_qual": 1e6, "output": "kept"},
            [artifact],
            tmp_path,
        )


def test_vcf_concordance_hand_metrics(tmp_path):
    truth_body = (
        "chr1\t100\t.\tA\tG\t50\tPASS\t.\tGT\t0/1\n"
        "chr1\t200\t.\tC\tT\t50\tPASS\t.\tGT\t0/1\n"
        "chr1\t300\t.\tG\tA\t50\tPASS\t.\tGT\t0/0\n"
        "chr1\t400\t.\tT\tC\t50\tPASS\t.\tGT\t0/0\n"
        "chr1\t600\t.\tC\tG\t50\tPASS\t.\tGT\t0/1\n"
        "chr1\t700\t.\tA\tG\t50\tPASS\t.\tGT\t0/1\n"
    )
    query_body = (
        "chr1\t100\t.\tA\tG\t50\tPASS\t.\tGT\t0/1\n"
        "chr1\t200\t.\tC\tT\t50\tPASS\t.\tGT\t1/1\n"
        "chr1\t300\t.\tG\tA\t50\tPASS\t.\tGT\t0/0\n"
        "chr1\t400\t.\tT\tC\t50\tPASS\t.\tGT\t0/1\n"
        "chr1\t500\t.\tA\tT\t50\tPASS\t.\tGT\t0/1\n"
        "chr1\t700\t.\tA\tC\t50\tPASS\t.\tGT\t0/1\n"
    )
    query = _artifact(tmp_path, "query.vcf", query_body, samples=("Q1",))
    truth = _artifact(tmp_path, "truth.vcf", truth_body, samples=("T1",))
    ctx, report = _run(
        VcfConcordanceStep(),
        {"output": "conc"},
        [query, truth],
        tmp_path,
    )
    values = _values(ctx["conc"])
    assert values["n_query_sites"] == 6
    assert values["n_truth_sites"] == 6
    assert values["n_matched_sites"] == 4  # 100,200,300,400
    assert values["n_query_only"] == 1  # 500
    assert values["n_truth_only"] == 2  # 600, 700 G
    assert values["n_allele_mismatch"] == 1  # 700 A>C vs A>G
    assert values["n_genotypes_compared"] == 4
    assert values["n_genotypes_discordant"] == 2  # 200 and 400
    assert values["genotype_concordance"] == pytest.approx(0.5)
    assert values["allele_concordance"] == pytest.approx(4 / 6)
    assert report["n_genotypes_discordant"] == 2


def _dosage_gt(value, rng):
    if value == 0:
        return "0/0"
    if value == 2:
        return "1/1"
    return rng.choice(["0/1", "1/0"])


def test_vcf_relatedness_duplicate_child_unrelated(tmp_path):
    rng = np.random.default_rng(7)

    def draw(p):
        return int(rng.binomial(2, p))

    def alleles(dosage):
        return [0, 0] if dosage == 0 else ([0, 1] if dosage == 1 else [1, 1])

    def gt(pair):
        return f"{pair[0]}/{pair[1]}"

    rows = []
    n_sites = 800
    for index in range(n_sites):
        p = float(rng.uniform(0.1, 0.9))
        d1 = draw(p)
        unrelated = draw(p)
        first = alleles(d1)
        second = alleles(unrelated)
        child = [int(rng.choice(first)), int(rng.choice(second))]
        rows.append(
            "	".join(
                [
                    "chr1",
                    str(1000 + index * 10),
                    ".",
                    "A",
                    "G",
                    "50",
                    "PASS",
                    ".",
                    "GT",
                    gt(first),
                    gt(first),
                    gt(second),
                    gt(child),
                ]
            )
            + "\n"
        )
    artifact = _artifact(
        tmp_path,
        "family.vcf",
        "".join(rows),
        samples=("D1", "D2", "U", "C"),
    )
    ctx, report = _run(
        VcfRelatednessStep(),
        {"min_maf": 0.05, "min_call_rate": 0.9, "output": "kin"},
        [artifact],
        tmp_path,
    )
    kin = ctx["kin"]
    labels = kin.labels["sample"]
    assert set(labels) == {"D1", "D2", "U", "C"}
    assert kin.data.shape == (4, 4)
    matrix = kin.data
    assert matrix[labels["D1"], labels["D1"]] == pytest.approx(0.5, abs=1e-6)
    assert matrix[labels["D1"], labels["D2"]] == pytest.approx(0.5, abs=1e-6)
    assert abs(float(matrix[labels["D1"], labels["U"]])) < 0.12
    assert 0.15 < matrix[labels["D1"], labels["C"]] < 0.35
    assert matrix[labels["D1"], labels["C"]] > matrix[labels["D1"], labels["U"]]
    assert np.allclose(matrix, matrix.T)
    assert report["n_samples"] == 4


def test_vcf_relatedness_between_family_formula(tmp_path):
    """Eq. 11 (min-heterozygosity denominator), matching plink2 --make-king-table.

    A is heterozygous at two sites, B at one site, never both; one site is
    IBS1-only and the rest are IBS2.  N_IBS1 = 3, min(N_Aa) = 1, so
    phi = 0.5 - 3 / (4 * 1) = -0.25.  The within-family Eq. 9 would give 0.
    """
    sites = [
        ("100", "0/0", "0/1"),
        ("200", "0/1", "0/0"),
        ("300", "0/1", "0/0"),
        ("400", "0/0", "0/0"),
    ]
    rows = [
        "\t".join(["chr1", pos, ".", "A", "G", "50", "PASS", ".", "GT", ga, gb]) + "\n"
        for pos, ga, gb in sites
    ]
    artifact = _artifact(tmp_path, "between.vcf", "".join(rows), samples=("A", "B"))
    ctx, _ = _run(
        VcfRelatednessStep(),
        {"min_maf": 0.0, "min_call_rate": 0.9, "output": "kin"},
        [artifact],
        tmp_path,
    )
    kin = ctx["kin"]
    labels = kin.labels["sample"]
    assert kin.data[labels["A"], labels["B"]] == pytest.approx(-0.25, abs=1e-6)
    assert kin.data[labels["A"], labels["A"]] == pytest.approx(0.5, abs=1e-6)


def test_vcf_relatedness_rejects_empty_filter(tmp_path):
    artifact = _artifact(tmp_path, "sites.vcf", BODY)
    with pytest.raises(StepError, match="no biallelic SNP"):
        _run(VcfRelatednessStep(), {"min_maf": 0.5, "output": "k"}, [artifact], tmp_path)


def test_file_artifact_contract_rejects_non_vcf(tmp_path):
    path = tmp_path / "x.fa"
    path.write_text(">a\nAC\n", encoding="utf-8")
    artifact = FileArtifact("fasta", {"x": str(path)}, {})
    with pytest.raises(StepError, match="VCF"):
        _run(VcfStatsStep(), {"output": "s"}, [artifact], tmp_path)

def test_vcf_concordance_multiallelic_alt_keys(tmp_path):
    truth_body = (
        "chr1\t900\t.\tA\tG\t50\tPASS\t.\tGT\t0/1\n"
        "chr1\t900\t.\tA\tT\t50\tPASS\t.\tGT\t0/0\n"
    )
    query_body = "chr1\t900\t.\tA\tG,T\t50\tPASS\t.\tGT\t1/2\n"
    query = _artifact(tmp_path, "query_multi.vcf", query_body, samples=("Q1",))
    truth = _artifact(tmp_path, "truth_multi.vcf", truth_body, samples=("T1",))
    ctx, report = _run(
        VcfConcordanceStep(),
        {"output": "conc"},
        [query, truth],
        tmp_path,
    )
    values = _values(ctx["conc"])
    assert values["n_query_sites"] == 2
    assert values["n_matched_sites"] == 2
    assert values["n_genotypes_compared"] == 2
    assert values["n_genotypes_discordant"] == 1  # T: 1 vs 0
    assert report["n_genotypes_discordant"] == 1
