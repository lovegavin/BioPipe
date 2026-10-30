from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from src.core import Form
from src.reader import pick_reader
from src.reader.readers.bim_reader import BimReader
from src.reader.readers.fam_reader import FamReader
from src.reader.readers.genepred_reader import GenePredReader
from src.reader.readers.gro_reader import GroReader
from src.reader.readers.hapmap_reader import HapmapReader
from src.reader.readers.hmmer_domtbl_reader import HmmerDomtblReader
from src.reader.readers.mgf_reader import MgfReader
from src.reader.readers.mol_reader import MolReader
from src.reader.readers.psl_reader import PslReader
from src.reader.readers.xyz_reader import XyzReader
from src.task.step.steps._sequence_common import encode_sequences
from src.task.step.steps.cell_cycle_score import CellCycleScoreStep
from src.task.step.steps.codon_usage import CodonUsageStep
from src.task.step.steps.fst import FstStep
from src.task.step.steps.hvg import HvgStep
from src.task.step.steps.kendall_tau import KendallTauStep
from src.task.step.steps.mcnemar import McnemarStep
from src.task.step.steps.pca_loadings import PcaLoadingsStep
from src.task.step.steps.peptide_qvalue import PeptideQvalueStep
from src.task.step.steps.protein_properties import ProteinPropertiesStep
from src.task.step.steps.relatedness import RelatednessStep
from src.task.step.steps.restriction_sites import RestrictionSitesStep
from src.task.step.steps.reverse_complement import ReverseComplementStep
from src.task.step.steps.rmst import RmstStep
from src.task.step.steps.translate import TranslateStep


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = params
        self.metadata = {}


def _form(data, dims, labels, info=None):
    form = Form(np.asarray(data, dtype=np.float32), list(dims), labels, info or {"missing_code": np.nan})
    form.validate()
    return form


def _run(step, params, inputs):
    ctx = Ctx(params)
    step.run(ctx, inputs)
    return ctx[params.get("output", step.name)], step.export(ctx)


def _seq_form(seqs, alphabet="dna"):
    return encode_sequences(seqs, "sequence", "position", alphabet)


def test_sequence_helpers_encode_codon_table():
    from src.task.step.steps._sequence_common import CODON_TABLE, reverse_complement

    assert CODON_TABLE["ATG"] == "M"
    assert reverse_complement("ATGCGA", "dna") == "TCGCAT"


def test_sequence_operators_hand_values():
    dna = _seq_form(["ATGCGA"])
    rc, _ = _run(ReverseComplementStep(), {}, [dna])
    assert rc.labels["sequence"] == {"seq1": 0}
    decoded = "".join(
        {v: k for k, v in rc.info["alphabet_map"].items()}[int(rc.data[0, i])]
        for i in range(rc.data.shape[1])
    )
    assert decoded == "TCGCAT"

    protein, _ = _run(TranslateStep(), {"to_stop": False}, [dna])
    assert protein.info["alphabet"] == "protein"
    assert protein.data.shape == (1, 2)
    assert "".join({v: k for k, v in protein.info["alphabet_map"].items()}[int(x)] for x in protein.data[0]) == "MR"

    codon, _ = _run(CodonUsageStep(), {}, [dna])
    assert codon.data.shape == (64, 2)
    atg = codon.labels["codon"]["ATG"]
    cga = codon.labels["codon"]["CGA"]
    assert codon.data[atg, 0] == 1
    assert codon.data[cga, 0] == 1

    sites, _ = _run(RestrictionSitesStep(), {"enzymes": {"BamHI": "GGATCC", "EcoRI": "GAATTC"}}, [_seq_form(["GGATCC"])])
    assert sites.labels["enzyme"] == {"BamHI": 0, "EcoRI": 1}
    assert sites.data[0, 0] == 1
    assert sites.data[0, 1] == 0

    props, _ = _run(ProteinPropertiesStep(), {}, [_seq_form(["ACDEFGHIK"], alphabet="protein")])
    assert props.labels["statistic"] == {
        "length": 0, "molecular_weight": 1, "isoelectric_point": 2, "gravy": 3, "aromaticity": 4,
    }
    assert props.data[0, 0] == 9
    assert props.data[0, 1] == pytest.approx(1181.2753, abs=0.01)
    assert props.data[0, 2] == pytest.approx(5.185, abs=0.01)
    assert props.data[0, 3] == pytest.approx(-0.3222, abs=1e-4)
    assert props.data[0, 4] == pytest.approx(0.111111, abs=1e-5)


def test_pca_hvg_and_cell_cycle_operators():
    rng = np.random.default_rng(7)
    data = rng.normal(size=(8, 4)).astype(np.float32)
    form = _form(data, ["sample", "feature"],
                 {"sample": {f"s{i}": i for i in range(8)}, "feature": {f"g{i}": i for i in range(4)}})
    pca, pca_info = _run(PcaLoadingsStep(), {"n_components": 3}, [form])
    assert pca.data.shape == (4, 3)
    assert pca.labels["component"] == {"PC1": 0, "PC2": 1, "PC3": 2}
    assert np.allclose(np.linalg.norm(pca.data, axis=0), 1.0, atol=1e-5)
    assert len(pca_info["explained_variance_ratio"]) == 3

    hv, hv_info = _run(HvgStep(), {"n_top": 2, "feature_dim": "feature"}, [form])
    assert hv.data.shape == (4, 4)
    assert hv.labels["statistic"] == {"mean": 0, "variance": 1, "dispersion": 2, "highly_variable": 3}
    assert int(hv.data[:, 3].sum()) == 2
    assert hv_info["n_selected"] == 2

    expr = _form(
        rng.normal(size=(12, 30)).astype(np.float32), ["cell", "gene"],
        {"cell": {f"c{i}": i for i in range(12)}, "gene": {f"g{i}": i for i in range(30)}},
    )
    sets = np.zeros((30, 2), dtype=np.float32)
    sets[0:8, 0] = 1
    sets[8:16, 1] = 1
    sets_form = _form(sets, ["gene", "gene_set"],
                      {"gene": {f"g{i}": i for i in range(30)}, "gene_set": {"S": 0, "G2M": 1}})
    cc, cc_info = _run(CellCycleScoreStep(), {"ctrl_size": 5, "n_bins": 5, "random_state": 1}, [expr, sets_form])
    assert cc.data.shape == (12, 3)
    assert cc.labels["statistic"] == {"S_score": 0, "G2M_score": 1, "phase_code": 2}
    assert set(np.unique(cc.data[:, 2]).tolist()) <= {0.0, 1.0}
    assert cc_info["phase_counts"]["S"] + cc_info["phase_counts"]["G2M"] == 12


def test_fst_relatedness_rmst_operators():
    geno = _form(
        np.array([[0, 0, 2, 2], [0, 1, 1, 2]], dtype=np.float32), ["variant", "sample"],
        {"variant": {"v0": 0, "v1": 1}, "sample": {f"s{i}": i for i in range(4)}},
    )
    meta = _form(np.array([[0], [0], [1], [1]], dtype=np.float32), ["sample", "group"],
                 {"sample": {f"s{i}": i for i in range(4)}, "group": {"group": 0}})
    fst, fst_info = _run(FstStep(), {"group_label": "group", "group_a": 0, "group_b": 1}, [geno, meta])
    assert fst.data.shape == (2, 5)
    assert fst.data[0, 0] == pytest.approx(1.0)
    assert fst_info["group_a"] == 0 and fst_info["group_b"] == 1

    rel, rel_info = _run(RelatednessStep(), {"min_maf": 0.01}, [geno])
    assert rel.data.shape == (4, 4)
    assert rel.dims == ["sample", "sample_b"]
    assert np.allclose(rel.data, rel.data.T, atol=1e-6)
    assert rel_info["n_samples"] == 4

    clinical = _form(
        np.array([[1, 1], [2, 1], [3, 1], [4, 1], [5, 1], [6, 1]], dtype=np.float32),
        ["sample", "feature"],
        {"sample": {f"s{i}": i for i in range(6)},
         "feature": {"time": 0, "event": 1}},
    )
    rmst, rmst_info = _run(RmstStep(), {"time_label": "time", "event_label": "event", "tau": 3}, [clinical])
    assert rmst.data.shape == (1, 6)
    assert rmst.data[0, 0] == pytest.approx(2.5, abs=1e-6)
    assert rmst_info["tau"] == 3


def test_peptide_qvalue_mcnemar_and_kendall():
    psm = _form(
        np.array([[10, 0], [9, 0], [8, 0], [7, 1]], dtype=np.float32), ["psm", "feature"],
        {"psm": {f"p{i}": i for i in range(4)}, "feature": {"score": 0, "decoy": 1}},
    )
    q, q_info = _run(PeptideQvalueStep(), {"score_label": "score", "decoy_label": "decoy"}, [psm])
    assert q.data.shape == (4, 3)
    assert np.all(q.data[:, 0] <= 1)
    assert np.all(np.diff(q.data[:, 0]) <= 1e-6)
    assert q_info["n_psms"] == 4

    labels = _form(
        np.array([[0, 1], [0, 1], [0, 0], [1, 1], [1, 0], [0, 1], [0, 1]], dtype=np.float32),
        ["sample", "feature"],
        {"sample": {f"s{i}": i for i in range(7)}, "feature": {"a": 0, "b": 1}},
    )
    mcn, mcn_info = _run(McnemarStep(), {"label_a": "a", "label_b": "b"}, [labels])
    assert mcn.data.shape == (4, 1)
    assert mcn_info["b01"] == 4 and mcn_info["b10"] == 1
    assert 0 < mcn_info["p"] <= 1

    x = _form(
        np.array([[1, 2], [2, 4], [3, 6], [4, 8], [5, 10]], dtype=np.float32), ["sample", "feature_x"],
        {"sample": {f"s{i}": i for i in range(5)}, "feature_x": {"x0": 0, "x1": 1}},
    )
    y = _form(
        np.array([[1, 2], [2, 4], [3, 6], [4, 8], [5, 10]], dtype=np.float32), ["sample", "feature_y"],
        {"sample": {f"s{i}": i for i in range(5)}, "feature_y": {"y0": 0, "y1": 1}},
    )
    tau, _ = _run(KendallTauStep(), {"feature_x": "feature_x", "feature_y": "feature_y"}, [x, y])
    assert tau.data.shape == (2, 2)
    assert np.allclose(tau.data, 1.0, atol=1e-6)


def _read(reader, path, dims, labels):
    result = reader.read(path, dims, labels)
    result.validate()
    return result


def test_plink_fam_bim_and_hapmap_readers(tmp_path: Path):
    fam = tmp_path / "cohort.fam"
    fam.write_text("F1 I1 0 0 1 1\nF1 I2 I1 0 2 2\n", encoding="utf-8")
    form = _read(FamReader(), fam, ["sample", "feature"], {"sample": "auto", "feature": "builtin"})
    assert form.data.shape == (2, 5)
    assert set(form.labels["sample"]) == {"I1", "I2"}
    assert form.data[0, 3] == 1 and form.data[1, 3] == 2

    bim = tmp_path / "cohort.bim"
    bim.write_text("1 rs1 0 100 A G\n", encoding="utf-8")
    form = _read(BimReader(), bim, ["variant", "feature"], {"variant": "auto", "feature": "builtin"})
    assert form.data.shape == (1, 5)
    assert form.labels["variant"] == {"rs1": 0}
    assert form.data[0, form.labels["feature"]["pos"]] == 100

    hap = tmp_path / "cohort.hapmap"
    header = "rs# chrom pos strand assembly# center# protLSID assayLSID panelLSID QCcode S1 S2"
    hap.write_text(header + "\nrs1 1 100 + NCBI36 0 0 0 0 0 AG AA\n", encoding="utf-8")
    form = _read(HapmapReader(), hap, ["variant", "sample"], {"variant": "auto", "sample": "auto"})
    assert form.data.shape == (1, 2)
    assert form.labels["sample"] == {"S1": 0, "S2": 1}
    assert form.data[0, 0] == 1 and form.data[0, 1] == 0


def test_structure_and_alignment_readers(tmp_path: Path):
    mol = tmp_path / "water.mol"
    mol.write_text(
        "water\n  test\n\n"
        "  2  1  0  0  0  0  0  0  0  0999 V2000\n"
        "    0.0000    0.0000    0.0000 O   0  0  0  0  0  0  0  0  0  0  0  0\n"
        "    1.0000    0.0000    0.0000 H   0  0  0  0  0  0  0  0  0  0  0  0\n"
        "  1  2  1  0\nM  END\n",
        encoding="utf-8",
    )
    form = _read(MolReader(), mol, ["molecule", "feature"], {"molecule": "auto", "feature": "builtin"})
    assert form.data.shape == (1, 4)
    assert form.data[0, 0] == 2 and form.data[0, 1] == 1 and form.data[0, 2] == 1

    xyz = tmp_path / "water.xyz"
    xyz.write_text("3\nwater\nO 0 0 0\nH 1 0 0\nH 0 1 0\n", encoding="utf-8")
    form = _read(XyzReader(), xyz, ["atom", "feature"], {"atom": "auto", "feature": "builtin"})
    assert form.data.shape == (3, 5)
    assert form.data[0, 3] == 8 and form.data[1, 3] == 1

    gro = tmp_path / "water.gro"
    lines = ["water", "    2"]
    for name, x, y, z in [("O", 0.0, 0.0, 0.0), ("H", 1.0, 0.0, 0.0)]:
        lines.append(f"{1:5d}{'SOL':>5}{name:>5}{1:5d}{x:8.3f}{y:8.3f}{z:8.3f}")
    lines.append("   1.0   1.0   1.0")
    gro.write_text("\n".join(lines) + "\n", encoding="utf-8")
    form = _read(GroReader(), gro, ["atom", "feature"], {"atom": "auto", "feature": "builtin"})
    assert form.data.shape == (2, 7)
    assert form.data[0, 0] == 0 and form.data[1, 0] == 1


def test_psl_genepred_mgf_and_domtbl_readers(tmp_path: Path):
    psl = tmp_path / "hit.psl"
    psl.write_text(
        "10\t0\t0\t0\t0\t0\t0\t0\t+\tq1\t100\t0\t10\tt1\t200\t5\t15\t1\t10,\t0,\t5,\n",
        encoding="utf-8",
    )
    form = _read(PslReader(), psl, ["alignment", "feature"], {"alignment": "auto", "feature": "builtin"})
    assert form.data.shape == (1, 21)
    assert form.data[0, form.labels["feature"]["q_size"]] == 100

    gp = tmp_path / "gene.genepred"
    gp.write_text("g1 chr1 + 100 200 120 180 2 100,150, 130,200,\n", encoding="utf-8")
    form = _read(GenePredReader(), gp, ["gene", "feature"], {"gene": "auto", "feature": "builtin"})
    assert form.data.shape == (1, 9)
    assert form.labels["gene"] == {"g1": 0}

    mgf = tmp_path / "spectra.mgf"
    mgf.write_text(
        "BEGIN IONS\nTITLE=pep1\nPEPMASS=500.2 1234\nCHARGE=2+\nRTINSECONDS=12.5\n100.0 10\n200.0 20\nEND IONS\n",
        encoding="utf-8",
    )
    form = _read(MgfReader(), mgf, ["spectrum", "feature"], {"spectrum": "auto", "feature": "builtin"})
    assert form.data.shape == (1, 6)
    assert form.data[0, form.labels["feature"]["n_peaks"]] == 2
    assert form.data[0, form.labels["feature"]["base_peak_intensity"]] == 20

    dom = tmp_path / "hits.domtblout"
    fields = (
        "target - 100 query - 50 1e-10 50.0 0.1 1 2 1e-5 1e-8 40.0 0.2 "
        "5 40 3 42 2 45 0.95 description"
    )
    dom.write_text("# header\n" + fields + "\n", encoding="utf-8")
    form = _read(HmmerDomtblReader(), dom, ["domain", "feature"], {"domain": "auto", "feature": "builtin"})
    assert form.data.shape == (1, 23)
    assert form.data[0, form.labels["feature"]["target_length"]] == 100
    assert form.data[0, form.labels["feature"]["domain_of"]] == 2


def test_new_readers_pick_reader_dispatch(tmp_path: Path):
    cases = {
        "x.fam": FamReader, "x.bim": BimReader, "x.hapmap": HapmapReader,
        "x.mol": MolReader, "x.xyz": XyzReader, "x.gro": GroReader,
        "x.psl": PslReader, "x.genepred": GenePredReader, "x.mgf": MgfReader,
        "x.domtblout": HmmerDomtblReader,
    }
    for name, cls in cases.items():
        path = tmp_path / name
        path.write_text("", encoding="utf-8")
        assert isinstance(pick_reader(path), cls)
