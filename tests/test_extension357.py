"""Regression tests for defects found by the 3.0.1 verification pass."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import numpy as np
import pytest

from src.core.errors import StepError
from src.core.forms.form import Form
from src.reader.readers._encoder import LabelEncoder
from src.task.context import Context
from src.task.runner import run
from src.task.step.steps._sequence_common import encode_sequences
from src.task.step.steps.antismash_bgc import parse_antismash_json
from src.task.step.steps.structure_dssp_segments import parse_dssp
from src.task.step.steps.structure_interface_core import relative_sasa

COLUMNS = ("x", "y", "z", "residue_number", "resname", "chain", "atom_name", "element")


def _pdb_form(rows) -> Form:
    columns = list(zip(*rows))
    numerics = [np.asarray(columns[index], dtype=np.float64) for index in (0, 1, 2, 3)]
    encoders = {}
    encoded = {}
    for index, name in zip((4, 5, 6, 7), ("resname", "chain", "atom_name", "element")):
        encoder = LabelEncoder()
        encoded[name] = encoder.fit_transform(list(columns[index]))
        encoders[name] = encoder
    matrix = np.column_stack(
        [
            numerics[0],
            numerics[1],
            numerics[2],
            numerics[3],
            encoded["resname"],
            encoded["chain"],
            encoded["atom_name"],
            encoded["element"],
        ]
    ).astype(np.float32)
    return Form(
        data=matrix,
        dims=["atom", "field"],
        labels={
            "atom": {f"atom:{index}": index for index in range(len(rows))},
            "field": {name: index for index, name in enumerate(COLUMNS)},
        },
        info={"missing_code": np.nan, "encoders": {"field": encoders}},
    )


def test_interface_core_ignores_third_chain() -> None:
    """A third chain contacting the target must not inflate A/B burial."""

    from src.task.step.steps.interface_bsa import vdw_radii

    rows = [
        (0.0, 0.0, 0.0, 1, "ALA", "A", "CA", "C"),
        (0.0, 1.5, 0.0, 1, "ALA", "A", "CB", "C"),
        (2.6, 0.0, 0.0, 2, "GLY", "B", "CA", "C"),
        (2.6, 1.5, 0.0, 2, "GLY", "B", "CB", "C"),
        (5.2, 0.0, 0.0, 3, "SER", "C", "CA", "C"),
        (5.2, 1.5, 0.0, 3, "SER", "C", "CB", "C"),
        (5.2, 3.0, 0.0, 3, "SER", "C", "CG", "C"),
        (5.2, 4.5, 0.0, 3, "SER", "C", "CD", "C"),
    ]
    ctx = Context("/tmp/bp357-interface", {"params": {}})
    ctx["pdb"] = _pdb_form(rows)
    run(
        ctx,
        [
            {
                "name": "structure_interface_core",
                "inputs": ["pdb"],
                "params": {"output": "core", "binder_chains": "A", "target_chains": "B"},
            }
        ],
    )
    core = ctx["core"]
    total = float(np.asarray(core.data)[:, 0].sum())
    coordinates = np.asarray([[row[0], row[1], row[2]] for row in rows], dtype=np.float64)
    radii = vdw_radii([row[7] for row in rows])
    masks = [
        np.asarray([row[5] == "A" for row in rows]),
        np.asarray([row[5] == "B" for row in rows]),
    ]
    keep = masks[0] | masks[1]
    complex_ab, isolated = relative_sasa(
        coordinates[keep], radii[keep], [masks[0][keep], masks[1][keep]]
    )
    expected = isolated[0].sum() + isolated[1].sum() - complex_ab.sum()
    assert expected > 0.5
    assert total == pytest.approx(expected, rel=1e-6)
    assert set(core.info["chain_counts"]) == {"A", "B"}


def test_relative_sasa_complex_mask_excludes_spectator() -> None:
    coordinates = np.asarray([[0.0, 0.0, 0.0], [2.8, 0.0, 0.0], [20.0, 0.0, 0.0]])
    radii = np.asarray([1.7, 1.7, 1.7])
    masks = [np.asarray([True, False, False]), np.asarray([False, True, False])]
    complex_sasa, isolated = relative_sasa(
        coordinates,
        radii,
        masks,
        complex_mask=np.asarray([True, True, False]),
        n_points=32,
    )
    delta = isolated[0].sum() + isolated[1].sum() - complex_sasa.sum()
    assert delta > 0.5
    assert complex_sasa[2] == 0.0


def test_dssp_parser_uses_fixed_columns() -> None:
    def row(index: int, number: int, chain: str, aa: str, ss: str) -> str:
        return f"{index:5d}{number:5d} {chain}{aa:>2}  {ss}"

    text = "\n".join(
        [
            "  #  RESIDUE AA STRUCTURE BP1 BP2  ACC",
            row(1, 1, "A", "M", "H"),
            row(2, 2, "A", "K", " "),
            "  518  4 12 12  0 TOTAL",
        ]
    )
    records = parse_dssp(text)
    assert [record["state"] for record in records] == ["helix", "coil"]
    assert {record["chain"] for record in records} == {"A"}
    assert [record["number"] for record in records] == [1, 2]


def test_ligand_pdbqt_flexible_persists_native_result_files(tmp_path) -> None:
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    run(
        ctx,
        [
            {
                "name": "ligand_pdbqt_flexible",
                "params": {"output": "ligand", "smiles": "CCO"},
            }
        ],
    )
    report = json.loads(
        (ctx.out_dir / "steps/01_ligand_pdbqt_flexible.json").read_text()
    )
    files = report["result_files"]
    assert files and files[0]["format"] == "pdbqt"
    path = Path(files[0]["path"])
    assert path.is_file()
    assert path.is_relative_to(ctx.out_dir)


FAKE_VINA = '''#!/usr/bin/env python
import pathlib
import sys
args = sys.argv[1:]
out = pathlib.Path(args[args.index("--out") + 1])
out.write_text("MODEL 1\\nENDMDL\\n")
print("mode | affinity | dist from best mode")
print("     | (kcal/mol) | rmsd l.b.| rmsd u.b.")
print("-----+------------+----------+----------")
print("   1       -7.5          0.000      0.000")
'''


def test_vina_dock_batch_keeps_duplicate_stems_distinct(tmp_path) -> None:
    receptor = tmp_path / "receptor.pdbqt"
    receptor.write_text("RECEPTOR\n")
    ligand_paths = []
    for folder in ("a", "b"):
        directory = tmp_path / folder
        directory.mkdir()
        ligand = directory / "ligand.pdbqt"
        ligand.write_text("LIGAND\n")
        ligand_paths.append(str(ligand))
    binary = tmp_path / "fake_vina.py"
    binary.write_text(FAKE_VINA)
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    run(
        ctx,
        [
            {
                "name": "vina_dock_batch",
                "params": {
                    "receptor_path": str(receptor),
                    "ligand_paths": ",".join(ligand_paths),
                    "vina_path": str(binary),
                    "center_x": 0,
                    "center_y": 0,
                    "center_z": 0,
                    "output": "batch",
                },
            }
        ],
    )
    batch = ctx["batch"]
    poses = list(batch.info["poses"].values())
    assert len(set(poses)) == 2
    assert len({Path(path).name for path in poses}) == 2
    for path in poses:
        assert Path(path).is_file()


QUAST = shutil.which("quast.py") or "/home/gavin/miniconda3/envs/assembly/bin/quast.py"


@pytest.mark.skipif(not Path(QUAST).is_file(), reason="QUAST is not installed")
def test_assembly_stats_runs_python_entry_point(tmp_path) -> None:
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    ctx["contigs"] = encode_sequences(["ACGT" * 100, "TTTT" * 40], "sequence", "position", "dna")
    run(
        ctx,
        [
            {
                "name": "assembly_stats",
                "inputs": ["contigs"],
                "params": {"output": "stats", "quast_path": QUAST, "threads": 1, "min_contig": 0},
            }
        ],
    )
    stats = ctx["stats"]
    assert stats.info["n_contigs"] == 2


def test_antismash_deduplicates_gene_and_cds() -> None:
    payload = {
        "records": [
            {
                "id": "contig1",
                "areas": [
                    {
                        "area_type": "region",
                        "start": 0,
                        "end": 100,
                        "products": ["T1PKS"],
                        "protoclusters": [],
                    }
                ],
                "features": [
                    {"type": "gene", "location": "[0:50](+)", "qualifiers": {"locus_tag": ["a"]}},
                    {"type": "CDS", "location": "[0:50](+)", "qualifiers": {"locus_tag": ["a"]}},
                    {"type": "gene", "location": "[60:90](-)", "qualifiers": {"locus_tag": ["b"]}},
                    {"type": "CDS", "location": "[60:90](-)", "qualifiers": {"locus_tag": ["b"]}},
                ],
            }
        ]
    }
    parsed = parse_antismash_json(json.dumps(payload))
    region = parsed["regions"][0]
    assert region["n_genes"] == 2
    assert [gene["locus_tag"] for gene in region["genes"]] == ["a", "b"]


def test_vina_dock_python_default_seed_is_deterministic() -> None:
    root = Path(__file__).resolve().parents[1]
    path = (
        root
        / "library/seed/src/task/step/steps/"
        "vina_dock_python.VinaDockPythonStep.parameters.json"
    )
    schema = json.loads(path.read_text())
    assert schema["properties"]["seed"]["default"] == 42


def test_colabfold_scores_survive_workdir_cleanup(tmp_path, monkeypatch) -> None:
    from src.task.step.steps import colabfold_predict

    pdb = (
        "ATOM      1  N   MET A   1      11.104  13.207   2.100  1.00 70.00           N\n"
        "ATOM      2  CA  MET A   1      12.560  13.207   2.100  1.00 70.00           C\n"
        "ATOM      3  C   MET A   1      13.000  14.500   2.100  1.00 70.00           C\n"
        "END\n"
    )

    def fake_predict(sequence, *, binary, workdir, **kwargs):
        workdir = Path(workdir)
        structure = workdir / "prediction.pdb"
        structure.write_text(pdb)
        scores = workdir / "scores.json"
        scores.write_text(json.dumps({"plddt": [80.0, 90.0], "ptm": 0.7, "pae": [[1.0, 2.0]]}))
        return structure, scores

    monkeypatch.setattr(colabfold_predict, "predict", fake_predict)
    binary = tmp_path / "colabfold_batch"
    binary.write_text("#!/bin/sh\n")
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    ctx["sequence"] = encode_sequences(["MKV"], "sequence", "position", "protein")
    run(
        ctx,
        [
            {
                "name": "colabfold_predict",
                "inputs": ["sequence"],
                "params": {"output": "structure", "colabfold_path": str(binary)},
            }
        ],
    )
    structure = ctx["structure"]
    scores_path = Path(structure.info["scores_path"])
    assert scores_path.is_file()
    assert scores_path.is_relative_to(ctx.out_dir)


def test_protein_properties_molecular_weight_is_peptide_mass() -> None:
    ctx = Context("/tmp/bp357-mw", {"params": {}})
    ctx["sequence"] = encode_sequences(["ACDEFGHIK"], "sequence", "position", "protein")
    run(
        ctx,
        [
            {
                "name": "protein_properties",
                "inputs": ["sequence"],
                "params": {"output": "props"},
            }
        ],
    )
    props = ctx["props"]
    column = props.labels["statistic"]["molecular_weight"]
    assert float(props.data[0, column]) == pytest.approx(1019.138, abs=0.01)


@pytest.mark.skipif(shutil.which("RNAfold") is None, reason="ViennaRNA is not installed")
def test_rna_fold_reports_ensemble_free_energy() -> None:
    ctx = Context("/tmp/bp357-fold", {"params": {}})
    ctx["sequence"] = encode_sequences(["GGGGAAAACCCC"], "sequence", "position", "rna")
    run(
        ctx,
        [
            {
                "name": "sequence_rna_fold",
                "inputs": ["sequence"],
                "params": {"output": "fold"},
            }
        ],
    )
    fold = ctx["fold"]
    column = fold.labels["statistic"]["ensemble"]
    assert float(fold.data[0, column]) == pytest.approx(-5.51, abs=0.02)


@pytest.mark.skipif(shutil.which("RNAcofold") is None, reason="ViennaRNA is not installed")
def test_rna_cofold_reports_ensemble_free_energy() -> None:
    ctx = Context("/tmp/bp357-cofold", {"params": {}})
    ctx["sequences"] = encode_sequences(
        ["GGGGAAAACCCC", "CCCCUUUUGGGG"], "sequence", "position", "rna"
    )
    run(
        ctx,
        [
            {
                "name": "sequence_rna_cofold",
                "inputs": ["sequences"],
                "params": {"output": "cofold"},
            }
        ],
    )
    cofold = ctx["cofold"]
    column = cofold.labels["statistic"]["ensemble"]
    assert float(cofold.data[0, column]) == pytest.approx(-11.95, abs=0.02)


@pytest.mark.skipif(shutil.which("RNAduplex") is None, reason="ViennaRNA is not installed")
def test_rna_duplex_default_energy_range_has_output() -> None:
    sequence = "GGGCAUUCGUUCGCGAAUGCCC" + "A" * 18
    reverse = sequence.translate(str.maketrans("ACGU", "UGCA"))[::-1]
    ctx = Context("/tmp/bp357-duplex", {"params": {}})
    ctx["sequences"] = encode_sequences([sequence, reverse], "sequence", "position", "rna")
    run(
        ctx,
        [
            {
                "name": "sequence_rna_duplex",
                "inputs": ["sequences"],
                "params": {"output": "duplex"},
            }
        ],
    )
    assert ctx["duplex"].data.shape[0] >= 1
