"""Hand-computed checks for the 1.7.0 ecology, alignment and PDBML batches.

Moran's I is compared with values printed by ``ape::Moran.I``; the
indicator species scores with ``labdsv::indval``; the pairwise aligner
with Biopython's ``PairwiseAligner``; and the PDBML reader with a hand
written document whose atom fields are known.
"""
from __future__ import annotations

import numpy as np
import pytest

from src.core import Form, ReaderError, StepError
from src.reader.readers.pdbml_reader import PdbmlReader
from src.task.step.steps._sequence_common import encode_sequences
from src.task.step.steps.indicator_species import IndicatorSpeciesStep
from src.task.step.steps.moran import MoranStep
from src.task.step.steps.pairwise_alignment import PairwiseAlignmentStep


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = dict(params)
        self.metadata = {}


def _form(data, dims, labels):
    out = Form(
        data=np.asarray(data, dtype=np.float32),
        dims=list(dims),
        labels=labels,
        info={"missing_code": np.nan},
    )
    out.validate()
    return out


def _run(step, params, inputs):
    ctx = Ctx(params)
    step.run(ctx, inputs)
    out = ctx[params["output"]]
    out.validate()
    return out, step.export(ctx)


def _scalar(form, name):
    return float(np.asarray(form.data[form.labels["statistic"][name], 0]))


# --------------------------------------------------------------------- Moran
MORAN_X = [1.0, 2.0, 4.0, 3.0, 5.0]
MORAN_LABELS = [f"s{i}" for i in range(5)]
# ape::Moran.I(c(1, 2, 4, 3, 5), as.matrix(dist(1:5)), "two.sided")
R_MORAN = {
    "observed": -0.053568627450980386,
    "expected": -0.25,
    "sd": 0.1517516199117535,
    "p_value": 0.195518018489644,
}


def _moran_inputs(distance=None, values=MORAN_X):
    table = _form(
        np.asarray(values, dtype=float).reshape(-1, 1),
        ["sample", "feature"],
        {"sample": {name: i for i, name in enumerate(MORAN_LABELS)}, "feature": {"value": 0}},
    )
    if distance is None:
        distance = np.abs(
            np.arange(len(values))[:, None] - np.arange(len(values))[None, :]
        )
    weights = _form(
        np.asarray(distance, dtype=float),
        ["sample", "sample_b"],
        {
            "sample": {name: i for i, name in enumerate(MORAN_LABELS)},
            "sample_b": {name: i for i, name in enumerate(MORAN_LABELS)},
        },
    )
    return table, weights


def test_moran_matches_ape_values():
    out, exported = _run(
        MoranStep(),
        {"sample_dim": "sample", "feature_dim": "feature", "sample_b_dim": "sample_b",
         "output": "moran"},
        _moran_inputs(),
    )
    assert list(out.dims) == ["statistic", "value"]
    for name, expected in R_MORAN.items():
        assert np.isclose(_scalar(out, name), expected, atol=1e-9), name
    assert np.isclose(exported["observed"], R_MORAN["observed"], atol=1e-12)
    assert _scalar(out, "n_samples") == 5.0


def test_moran_binary_weights_hand_value():
    table, _weights = _moran_inputs()
    adjacency = np.array([
        [0.0, 1.0, 0.0, 0.0, 0.0],
        [1.0, 0.0, 1.0, 0.0, 0.0],
        [0.0, 1.0, 0.0, 1.0, 0.0],
        [0.0, 0.0, 1.0, 0.0, 1.0],
        [0.0, 0.0, 0.0, 1.0, 0.0],
    ])
    weights = _form(
        adjacency,
        ["sample", "sample_b"],
        {"sample": {name: i for i, name in enumerate(MORAN_LABELS)},
         "sample_b": {name: i for i, name in enumerate(MORAN_LABELS)}},
    )
    out, _exported = _run(
        MoranStep(),
        {"weighting": "binary", "output": "moran"},
        [table, weights],
    )
    # Path graph over five nodes: row-normalised adjacency, I = (n / S0) y'Wy / y'y
    # with y = (-2, -1, 1, 0, 2) gives S0 = 5 and y'Wy = 2, so I = 0.2.
    assert np.isclose(_scalar(out, "observed"), 0.2, atol=1e-9)
    assert np.isclose(_scalar(out, "expected"), -0.25, atol=1e-12)
    assert 0.0 <= _scalar(out, "p_value") <= 1.0


def test_moran_value_label_and_errors():
    values = np.column_stack([MORAN_X, [5.0, 4.0, 3.0, 2.0, 1.0]])
    table = _form(
        values,
        ["sample", "feature"],
        {"sample": {name: i for i, name in enumerate(MORAN_LABELS)},
         "feature": {"a": 0, "b": 1}},
    )
    _table, weights = _moran_inputs()
    out, _exported = _run(
        MoranStep(), {"value_label": "b", "output": "moran"}, [table, weights]
    )
    assert np.isfinite(_scalar(out, "observed"))
    with pytest.raises(StepError, match="exactly one value column"):
        _run(MoranStep(), {"output": "x"}, [table, weights])

    labels = {"sample": {"s0": 0, "s1": 1, "s2": 2},
              "sample_b": {"s0": 0, "s1": 1, "s2": 2}}
    short_table = _form([[1.0], [2.0], [3.0]], ["sample", "feature"],
                        {"sample": labels["sample"], "feature": {"value": 0}})
    short_weights = _form([[0.0, 1.0, 2.0], [1.0, 0.0, 1.0], [2.0, 1.0, 0.0]],
                          ["sample", "sample_b"], labels)
    with pytest.raises(StepError, match="at least four samples"):
        _run(MoranStep(), {"output": "x"}, [short_table, short_weights])

    constant_table, constant_weights = _moran_inputs(values=[2.0] * 5)
    with pytest.raises(StepError, match="constant"):
        _run(MoranStep(), {"output": "x"}, [constant_table, constant_weights])


# --------------------------------------------------------- Indicator species
IND_COUNTS = np.array([
    [10, 1, 0, 2],
    [8, 2, 1, 0],
    [12, 0, 0, 1],
    [0, 9, 3, 1],
    [1, 8, 4, 0],
    [0, 7, 5, 2],
], dtype=float)
IND_GROUPS = [0.0, 0.0, 0.0, 1.0, 1.0, 1.0]
IND_TAXA = ["t1", "t2", "t3", "t4"]
IND_SAMPLES = [f"s{i}" for i in range(6)]

# labdsv::indval(comm, grp, numitr = 0)
R_FIDELITY = np.array([[1.0, 1.0 / 3.0], [2.0 / 3.0, 1.0], [1.0 / 3.0, 1.0], [2.0 / 3.0, 2.0 / 3.0]])
R_SPECIFICITY = np.array([
    [0.96774194, 0.03225806],
    [0.11111111, 0.88888889],
    [0.07692308, 0.92307692],
    [0.5, 0.5],
])
R_INDVAL = R_FIDELITY * R_SPECIFICITY


def _indicator_inputs(counts=IND_COUNTS, groups=IND_GROUPS):
    table = _form(
        counts,
        ["sample", "taxon"],
        {"sample": {name: i for i, name in enumerate(IND_SAMPLES)},
         "taxon": {name: i for i, name in enumerate(IND_TAXA)}},
    )
    meta = _form(
        np.asarray(groups, dtype=float).reshape(-1, 1),
        ["sample", "feature"],
        {"sample": {name: i for i, name in enumerate(IND_SAMPLES)}, "feature": {"group": 0}},
    )
    return table, meta


def test_indicator_species_matches_labdsv():
    out, exported = _run(
        IndicatorSpeciesStep(),
        {"group_label": "group", "output": "indicator_species"},
        _indicator_inputs(),
    )
    assert list(out.dims) == ["taxon", "statistic"]
    names = out.labels["statistic"]
    for group_index, group in enumerate(["0", "1"]):
        fidelity = np.asarray(out.data[:, names[f"fidelity:{group}"]], dtype=float)
        specificity = np.asarray(out.data[:, names[f"specificity:{group}"]], dtype=float)
        indval = np.asarray(out.data[:, names[f"indval:{group}"]], dtype=float)
        assert np.allclose(fidelity, R_FIDELITY[:, group_index], atol=1e-6)
        assert np.allclose(specificity, R_SPECIFICITY[:, group_index], atol=1e-6)
        assert np.allclose(indval, R_INDVAL[:, group_index], atol=1e-6)
    assert np.isclose(exported["max_indval"], 0.9677419354838709, atol=1e-9)
    assert exported["groups"] == ["0", "1"]


def test_indicator_species_errors():
    table, meta = _indicator_inputs()
    with pytest.raises(StepError, match="at least two groups"):
        _run(
            IndicatorSpeciesStep(),
            {"group_label": "group", "output": "x"},
            _indicator_inputs(groups=[0.0] * 6),
        )
    absent = np.array(IND_COUNTS, dtype=float)
    absent[:, 3] = 0.0
    with pytest.raises(StepError, match="occur in at least one sample"):
        _run(
            IndicatorSpeciesStep(),
            {"group_label": "group", "output": "x"},
            _indicator_inputs(counts=absent),
        )


# ------------------------------------------------------- Pairwise alignment
def _sequences(first, second):
    return (
        encode_sequences([first], "sequence", "position", "dna"),
        encode_sequences([second], "sequence", "position", "dna"),
    )


def test_pairwise_alignment_global_matches_biopython():
    inputs = _sequences("ACGTACGT", "ACGTTACGT")
    out, exported = _run(
        PairwiseAlignmentStep(), {"mode": "global", "output": "alignment"}, list(inputs)
    )
    assert np.isclose(_scalar(out, "score"), 14.0, atol=1e-9)
    assert np.isclose(_scalar(out, "matches"), 8.0)
    assert np.isclose(_scalar(out, "mismatches"), 0.0)
    assert np.isclose(_scalar(out, "gap_opens"), 1.0)
    assert np.isclose(_scalar(out, "gap_bases"), 1.0)
    assert np.isclose(_scalar(out, "aligned_length"), 9.0)
    assert exported["aligned_target"] == "ACG-TACGT"
    assert exported["aligned_query"] == "ACGTTACGT"


def test_pairwise_alignment_local_matches_biopython():
    inputs = _sequences("TTACGTAAGG", "GGACGTAA")
    out, exported = _run(
        PairwiseAlignmentStep(), {"mode": "local", "output": "alignment"}, list(inputs)
    )
    assert np.isclose(_scalar(out, "score"), 12.0, atol=1e-9)
    assert exported["aligned_target"] == "ACGTAA"
    assert exported["aligned_query"] == "ACGTAA"
    assert np.isclose(_scalar(out, "identity"), 1.0, atol=1e-12)


def test_pairwise_alignment_identical_and_errors():
    inputs = _sequences("AAAA", "AAAA")
    out, _exported = _run(
        PairwiseAlignmentStep(), {"mode": "global", "output": "alignment"}, list(inputs)
    )
    assert np.isclose(_scalar(out, "score"), 8.0)
    assert np.isclose(_scalar(out, "identity"), 1.0)

    single = (inputs[0], encode_sequences(["AAAA", "AAAA"], "sequence", "position", "dna"))
    with pytest.raises(StepError, match="exactly two sequences"):
        _run(PairwiseAlignmentStep(), {"output": "x"}, list(single))
    with pytest.raises(StepError, match="mismatch score"):
        _run(PairwiseAlignmentStep(), {"mismatch": 1.0, "output": "x"}, list(inputs))
    with pytest.raises(StepError, match="too large"):
        _run(
            PairwiseAlignmentStep(),
            {"max_cells": 10, "output": "x"},
            list(_sequences("ACGTACGT", "ACGTACGT")),
        )


# ---------------------------------------------------------------- PDBML
PDBML_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<PDBx:datablock xmlns:PDBx="http://pdbml.pdb.org/schema/pdbx-v50.xsd" datablockName="TEST">
  <PDBx:atom_siteCategory>
{atoms}
  </PDBx:atom_siteCategory>
</PDBx:datablock>
"""

PDBML_ATOM = """    <PDBx:atom_site id="{serial}">
      <PDBx:group_PDB>{group}</PDBx:group_PDB>
      <PDBx:label_atom_id>{atom}</PDBx:label_atom_id>
      <PDBx:label_comp_id>{resname}</PDBx:label_comp_id>
      <PDBx:label_asym_id>{chain}</PDBx:label_asym_id>
      <PDBx:label_seq_id>{residue}</PDBx:label_seq_id>
      <PDBx:Cartn_x>{x}</PDBx:Cartn_x>
      <PDBx:Cartn_y>{y}</PDBx:Cartn_y>
      <PDBx:Cartn_z>{z}</PDBx:Cartn_z>
      <PDBx:occupancy>{occupancy}</PDBx:occupancy>
      <PDBx:B_iso_or_equiv>{bfactor}</PDBx:B_iso_or_equiv>
      <PDBx:type_symbol>{element}</PDBx:type_symbol>
      <PDBx:pdbx_PDB_model_num>{model}</PDBx:pdbx_PDB_model_num>
    </PDBx:atom_site>"""


def _pdbml_file(tmp_path, atoms):
    path = tmp_path / "structure.pdbml"
    path.write_text(PDBML_TEMPLATE.format(atoms="\n".join(atoms)))
    return path


def _atom(serial, x, y, z, model=1, group="ATOM", occupancy=1.0, bfactor=10.0):
    return PDBML_ATOM.format(
        serial=serial, group=group, atom="CA", resname="ALA", chain="A", residue=1,
        x=x, y=y, z=z, occupancy=occupancy, bfactor=bfactor, element="C", model=model,
    )


def test_pdbml_reader_parses_atoms(tmp_path):
    path = _pdbml_file(tmp_path, [
        _atom(1, 1.0, 2.0, 3.0, occupancy=1.0, bfactor=10.0),
        _atom(2, 4.5, 5.25, 6.125, occupancy=0.5, bfactor=22.5),
    ])
    form = PdbmlReader().read(path, ["atom", "field"], {})
    assert list(form.dims) == ["atom", "field"]
    assert form.data.shape == (2, 9)
    fields = form.labels["field"]
    assert list(fields) == ["x", "y", "z", "occupancy", "bfactor", "residue_number",
                            "chain", "resname", "element"]
    assert np.allclose(form.data[:, fields["x"]], [1.0, 4.5])
    assert np.allclose(form.data[:, fields["z"]], [3.0, 6.125])
    assert np.allclose(form.data[:, fields["occupancy"]], [1.0, 0.5])
    assert np.allclose(form.data[:, fields["bfactor"]], [10.0, 22.5])
    assert list(form.labels["atom"]) == ["atom:1", "atom:2"]
    assert form.info["n_atoms"] == 2


def test_pdbml_reader_model_filter_and_groups(tmp_path):
    path = _pdbml_file(tmp_path, [
        _atom(1, 1.0, 1.0, 1.0, model=1),
        _atom(2, 2.0, 2.0, 2.0, model=2),
        _atom(3, 3.0, 3.0, 3.0, model=2, group="HETATM"),
        _atom(4, 4.0, 4.0, 4.0, model=2, group="ANISOU"),
    ])
    all_atoms = PdbmlReader().read(path, ["atom", "field"], {})
    assert all_atoms.data.shape[0] == 3
    second = PdbmlReader().read(path, ["atom", "field"], {}, model=2)
    assert second.data.shape[0] == 2
    assert np.allclose(second.data[:, second.labels["field"]["y"]], [2.0, 3.0])


def test_pdbml_reader_errors(tmp_path):
    bad = tmp_path / "bad.pdbml"
    bad.write_text("<not-xml")
    with pytest.raises(ReaderError, match="invalid XML"):
        PdbmlReader().read(bad, ["atom", "field"], {})
    empty = _pdbml_file(tmp_path, [])
    with pytest.raises(ReaderError, match="no ATOM/HETATM"):
        PdbmlReader().read(empty, ["atom", "field"], {})
    missing = _pdbml_file(tmp_path, [_atom(1, 1.0, 2.0, 3.0).replace(
        "<PDBx:Cartn_z>3.0</PDBx:Cartn_z>", "<PDBx:Cartn_z>.</PDBx:Cartn_z>")])
    with pytest.raises(ReaderError, match="missing Cartesian coordinates"):
        PdbmlReader().read(missing, ["atom", "field"], {})


# ------------------------------------------------- Biopython authority checks
PDBML_FULL = """<?xml version="1.0" encoding="UTF-8"?>
<PDBx:datablock xmlns:PDBx="http://pdbml.pdb.org/schema/pdbx-v50.xsd" datablockName="TEST">
  <PDBx:structCategory><PDBx:struct id="TEST"><PDBx:title>Test structure</PDBx:title></PDBx:struct></PDBx:structCategory>
  <PDBx:struct_keywordsCategory><PDBx:struct_keywords id="TEST"><PDBx:text>test</PDBx:text></PDBx:struct_keywords></PDBx:struct_keywordsCategory>
  <PDBx:entryCategory><PDBx:entry id="TEST"/></PDBx:entryCategory>
  <PDBx:pdbx_database_statusCategory><PDBx:pdbx_database_status id="TEST"><PDBx:recvd_initial_deposition_date>2026-01-01</PDBx:recvd_initial_deposition_date></PDBx:pdbx_database_status></PDBx:pdbx_database_statusCategory>
  <PDBx:exptlCategory><PDBx:exptl id="TEST" method="X-RAY DIFFRACTION"/></PDBx:exptlCategory>
  <PDBx:atom_siteCategory>
{atoms}
  </PDBx:atom_siteCategory>
</PDBx:datablock>
"""

PDBML_FULL_ATOM = """    <PDBx:atom_site id="{serial}">
      <PDBx:group_PDB>ATOM</PDBx:group_PDB>
      <PDBx:label_atom_id>{atom}</PDBx:label_atom_id>
      <PDBx:label_alt_id>.</PDBx:label_alt_id>
      <PDBx:label_comp_id>{resname}</PDBx:label_comp_id>
      <PDBx:label_asym_id>{chain}</PDBx:label_asym_id>
      <PDBx:label_seq_id>{residue}</PDBx:label_seq_id>
      <PDBx:auth_asym_id>{chain}</PDBx:auth_asym_id>
      <PDBx:auth_seq_id>{residue}</PDBx:auth_seq_id>
      <PDBx:auth_comp_id>{resname}</PDBx:auth_comp_id>
      <PDBx:Cartn_x>{x}</PDBx:Cartn_x>
      <PDBx:Cartn_y>{y}</PDBx:Cartn_y>
      <PDBx:Cartn_z>{z}</PDBx:Cartn_z>
      <PDBx:occupancy>{occupancy}</PDBx:occupancy>
      <PDBx:B_iso_or_equiv>{bfactor}</PDBx:B_iso_or_equiv>
      <PDBx:type_symbol>{element}</PDBx:type_symbol>
      <PDBx:pdbx_PDB_model_num>{model}</PDBx:pdbx_PDB_model_num>
    </PDBx:atom_site>"""


def test_pairwise_alignment_matches_biopython():
    align = pytest.importorskip("Bio.Align")
    aligner = align.PairwiseAligner()
    aligner.match_score = 2.0
    aligner.mismatch_score = -1.0
    aligner.open_gap_score = -2.0
    aligner.extend_gap_score = -1.0
    pairs = [("ACGTACGT", "ACGTTACGT"), ("AAAA", "AAAA"), ("ACGT", "AGGT"),
             ("GATTACA", "GCATGCU")]
    for mode in ("global", "local"):
        aligner.mode = mode
        for first, second in pairs:
            expected = float(aligner.score(first, second))
            out, _exported = _run(
                PairwiseAlignmentStep(),
                {"mode": mode, "output": "alignment"},
                list(_sequences(first, second)),
            )
            assert np.isclose(_scalar(out, "score"), expected, atol=1e-9), (mode, first, second)


def test_pdbml_reader_matches_biopython(tmp_path):
    parser_module = pytest.importorskip("Bio.PDB.PDBMLParser")
    atoms = [
        dict(serial=1, atom="CA", resname="ALA", chain="A", residue=1,
             x=1.0, y=2.0, z=3.0, occupancy=1.0, bfactor=10.0, element="C", model=1),
        dict(serial=2, atom="N", resname="ALA", chain="A", residue=1,
             x=4.5, y=5.25, z=6.125, occupancy=0.5, bfactor=22.5, element="N", model=1),
    ]
    path = tmp_path / "full.pdbml"
    path.write_text(PDBML_FULL.format(atoms="\n".join(
        PDBML_FULL_ATOM.format(**atom) for atom in atoms)))
    form = PdbmlReader().read(path, ["atom", "field"], {})
    fields = form.labels["field"]
    with path.open() as handle:
        structure = parser_module.PDBMLParser().get_structure(handle)
    parsed = list(structure.get_atoms())
    assert len(parsed) == len(atoms)
    for index, atom in enumerate(parsed):
        assert np.allclose(form.data[index, [fields["x"], fields["y"], fields["z"]]],
                           atom.get_coord())
        assert np.isclose(form.data[index, fields["occupancy"]], atom.get_occupancy())
        assert np.isclose(form.data[index, fields["bfactor"]], atom.get_bfactor())
