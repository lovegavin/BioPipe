"""Reader checks: protein FASTA coding and full-atom PDB columns."""
from __future__ import annotations

import numpy as np
import pytest

from src.core import ReaderError
from src.reader.readers.fasta_reader import FastaReader
from src.reader.readers.pdb_reader import PdbReader
from src.task.step.steps._sequence_common import PROTEIN_MAP

DIMS = ["sequence", "position"]
LABELS = {"sequence": "builtin", "position": "auto"}
FIELD_LABELS = {"atom": "auto", "field": "builtin"}


def _fasta(tmp_path, text):
    path = tmp_path / "input.fasta"
    path.write_text(text, encoding="utf-8")
    return path


def test_protein_fasta_codes(tmp_path):
    path = _fasta(tmp_path, ">p1 description\nACDEFG\n>p2\nACDEBZ*\n")
    form = FastaReader().read(path, DIMS, LABELS, alphabet="protein")
    assert list(form.dims) == DIMS
    assert form.labels["sequence"] == {"p1": 0, "p2": 1}
    assert form.info["alphabet"] == "protein"
    assert form.info["representation"] == "sequence_codes"
    assert form.info["unknown_code"] == 21

    expected = [PROTEIN_MAP[character] for character in "ACDEFG"]
    np.testing.assert_allclose(form.data[0, :6], expected)
    assert np.isnan(form.data[0, 6])

    proteins = [PROTEIN_MAP[character] for character in "ACDE"]
    np.testing.assert_allclose(form.data[1, :4], proteins)
    assert form.data[1, 4] == 21
    assert form.data[1, 5] == 21
    assert form.data[1, 6] == PROTEIN_MAP["*"]


def test_protein_fasta_is_inferred(tmp_path):
    path = _fasta(tmp_path, ">p1\nMKWVTFISLL\n")
    form = FastaReader().read(path, DIMS, LABELS)
    assert form.info["alphabet"] == "protein"
    np.testing.assert_allclose(
        form.data[0], [PROTEIN_MAP[character] for character in "MKWVTFISLL"]
    )


def test_nucleotide_legacy_codes_still_apply(tmp_path):
    dna = FastaReader().read(_fasta(tmp_path, ">dna\nACGTN\n"), DIMS, LABELS)
    assert dna.info["alphabet"] == "dna"
    assert dna.info["unknown_code"] == 5
    np.testing.assert_allclose(dna.data[0], [0, 1, 2, 3, 4])

    rna = FastaReader().read(_fasta(tmp_path, ">rna\nACGUN\n"), DIMS, LABELS)
    assert rna.info["alphabet"] == "rna"
    np.testing.assert_allclose(rna.data[0], [0, 1, 2, 3, 4])

    mixed = FastaReader().read(
        _fasta(tmp_path, ">mixed\nACGTUN\n"), DIMS, LABELS
    )
    assert mixed.info["alphabet"] == "rna"
    np.testing.assert_allclose(mixed.data[0], [0, 1, 2, 3, 3, 4])

    protein = _fasta(tmp_path, ">p\nACDEFG\n")
    forced = FastaReader().read(protein, DIMS, LABELS, alphabet="dna")
    assert forced.info["alphabet"] == "dna"
    assert forced.info["unknown_code"] == 5
    assert forced.data[0, 3] == 5


def test_fasta_errors(tmp_path):
    path = _fasta(tmp_path, ">p\nACDE\n")
    with pytest.raises(ReaderError, match="alphabet must be one of"):
        FastaReader().read(path, DIMS, LABELS, alphabet="codons")
    with pytest.raises(ReaderError, match="requires exactly two dims"):
        FastaReader().read(path, ["sequence"], LABELS)
    with pytest.raises(ReaderError, match="no sequences"):
        FastaReader().read(_fasta(tmp_path, ""), DIMS, LABELS)
    with pytest.raises(ReaderError, match="before the first"):
        FastaReader().read(_fasta(tmp_path, "ACGT\n"), DIMS, LABELS)


def _atom(record, serial, name, altloc, resname, chain, number, x, y, z, element,
          icode=" "):
    return (
        f"{record:<6}{serial:5d} {name:^4}{altloc:1}{resname:>3} {chain:1}"
        f"{number:4d}{icode:1}   "
        f"{x:8.3f}{y:8.3f}{z:8.3f}{1.00:6.2f}{0.00:6.2f}          "
        f"{element:>2}"
    )


def test_pdb_full_atom_columns(tmp_path):
    path = tmp_path / "full.pdb"
    path.write_text(
        "\n".join([
            _atom("ATOM", 1, "N", " ", "ALA", "A", 1, 0.0, 0.0, 0.0, "N"),
            _atom("ATOM", 2, "CA", " ", "ALA", "A", 1, 1.4, 0.0, 0.0, "C"),
            _atom("ATOM", 3, "CB", "A", "ALA", "A", 1, 1.4, 1.0, 0.0, "C", "A"),
            _atom("HETATM", 4, "O", " ", "HOH", "A", 2, 2.0, 0.0, 0.0, "O"),
        ]) + "\nEND\n",
        encoding="utf-8",
    )
    form = PdbReader().read(path, ["atom", "field"], FIELD_LABELS)
    assert form.data.shape == (4, 12)
    fields = form.labels["field"]
    for name in (
        "x", "y", "z", "occupancy", "bfactor", "residue_number",
        "chain", "resname", "element", "atom_name", "altloc", "insertion_code",
    ):
        assert name in fields, name

    encoders = form.info["encoders"]["field"]
    names = [
        encoders["atom_name"].inverse_transform([form.data[row, fields["atom_name"]]])[0]
        for row in range(4)
    ]
    assert names == ["N", "CA", "CB", "O"]
    chains = [
        encoders["chain"].inverse_transform([form.data[row, fields["chain"]]])[0]
        for row in range(4)
    ]
    assert chains == ["A", "A", "A", "A"]
    resnames = [
        encoders["resname"].inverse_transform([form.data[row, fields["resname"]]])[0]
        for row in range(4)
    ]
    assert resnames == ["ALA", "ALA", "ALA", "HOH"]
    np.testing.assert_allclose(form.data[:, fields["residue_number"]], [1, 1, 1, 2])
    np.testing.assert_allclose(
        form.data[:, fields["x"]], [0.0, 1.4, 1.4, 2.0], rtol=1e-6
    )
    assert form.info["fields"] == list(fields)
    assert form.info["n_atoms"] == 4


def test_pdb_matches_biopython(tmp_path):
    bio_pdb = pytest.importorskip("Bio.PDB")
    path = tmp_path / "oracle.pdb"
    path.write_text(
        "\n".join([
            _atom("ATOM", 1, "N", " ", "GLY", "A", 1, 1.0, 2.0, 3.0, "N"),
            _atom("ATOM", 2, "CA", " ", "GLY", "A", 1, 2.0, 3.0, 4.0, "C"),
            _atom("ATOM", 3, "CA", "B", "SER", "B", 5, 5.0, 6.0, 7.0, "C"),
        ]) + "\nEND\n",
        encoding="utf-8",
    )
    form = PdbReader().read(path, ["atom", "field"], FIELD_LABELS)
    fields = form.labels["field"]
    structure = bio_pdb.PDBParser(QUIET=True).get_structure("x", str(path))
    atoms = list(structure.get_atoms())
    assert len(atoms) == form.data.shape[0] == 3
    encoders = form.info["encoders"]["field"]
    for row, atom in enumerate(atoms):
        assert float(form.data[row, fields["x"]]) == pytest.approx(atom.coord[0])
        assert float(form.data[row, fields["y"]]) == pytest.approx(atom.coord[1])
        assert float(form.data[row, fields["z"]]) == pytest.approx(atom.coord[2])
        assert float(form.data[row, fields["residue_number"]]) == atom.get_parent().id[1]
        assert atom.get_parent().get_resname() == (
            encoders["resname"].inverse_transform(
                [form.data[row, fields["resname"]]]
            )[0]
        )


def test_pdb_errors(tmp_path):
    bad = tmp_path / "bad.pdb"
    bad.write_text(
        "ATOM      1  CA  ALA A   1       x.xxx   0.000   0.000  1.00  0.00\n",
        encoding="utf-8",
    )
    with pytest.raises(ReaderError, match="malformed coordinate line"):
        PdbReader().read(bad, ["atom", "field"], FIELD_LABELS)

    empty = tmp_path / "empty.pdb"
    empty.write_text("HEADER    NOTHING\nEND\n", encoding="utf-8")
    with pytest.raises(ReaderError, match="no ATOM/HETATM"):
        PdbReader().read(empty, ["atom", "field"], FIELD_LABELS)
