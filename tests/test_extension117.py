"""AutoDock PDBQT reader (v1.21.0)."""
from __future__ import annotations

import pytest

from src.core import ReaderError
from src.reader import pick_reader
from src.reader.readers.pdbqt_reader import PdbqtReader, _charge_and_type, _element


def _atom(serial, name, resname, chain, number, x, y, z, charge, atom_type,
          record="ATOM"):
    line = (
        f"{record:<6}{serial:>5} {name:<4} {resname:>3} {chain}{number:>4}    "
        f"{x:>8.3f}{y:>8.3f}{z:>8.3f}{1.00:>6.2f}{0.00:>6.2f}"
    )
    assert len(line) == 66, len(line)
    padded = line + " " * 4 + f"{charge:>6.3f}" + " " + f"{atom_type:>2}"
    assert len(padded) == 79, (len(padded), padded)
    return padded


PDBQT = [
    _atom(1, "N", "ALA", "A", 1, 0.0, 0.0, 0.0, -0.30, "N"),
    _atom(2, "CA", "ALA", "A", 1, 1.4, 0.0, 0.0, 0.10, "C"),
    _atom(3, "O", "ALA", "A", 1, 2.0, 1.0, 0.0, -0.40, "OA"),
    _atom(4, "CL1", "UNL", "B", 9, 3.0, 0.0, 0.0, -0.10, "Cl", record="HETATM"),
]


def _form(tmp_path, lines=PDBQT, name="lig.pdbqt"):
    path = tmp_path / name
    path.write_text("\n".join(lines) + "\n")
    return PdbqtReader().read(
        path,
        dims=["atom", "field"],
        labels={"atom": "auto", "field": "builtin"},
    )


def test_charge_and_type_reads_fixed_columns():
    charge, atom_type = _charge_and_type(PDBQT[1])
    assert charge == pytest.approx(0.10)
    assert atom_type == "C"


def test_charge_and_type_falls_back_to_tokens():
    prefix = "ATOM      7  CB  ALA A   1       1.000   2.000   3.000  1.00  0.00"
    assert len(prefix) == 66
    # Non-numeric junk in the fixed 71-76 window, charge/type given as tokens.
    line = prefix + "    " + "x" + " " * 5 + "-0.20" + "  " + "C "
    assert line[70:76] == "x     "
    assert _charge_and_type(line) == pytest.approx((-0.20, "C"))


def test_element_maps_two_letter_halogens():
    assert _element("CL1", "Cl") == "CL"
    assert _element("BR1", "Br") == "BR"
    assert _element("CA", "C") == "C"
    assert _element("", "") == "X"


def test_reader_dispatch_and_columns(tmp_path):
    path = tmp_path / "lig.pdbqt"
    path.write_text("\n".join(PDBQT) + "\n")
    reader = pick_reader(path)
    assert isinstance(reader.implementation(), PdbqtReader)

    form = _form(tmp_path)
    assert form.dims == ["atom", "field"]
    assert list(form.data.shape) == [4, 14]
    fields = form.info["fields"]
    assert fields[-2:] == ["partial_charge", "atom_type"]
    charge_col = fields.index("partial_charge")
    name_col = fields.index("atom_name")
    element_col = fields.index("element")
    assert form.data[1, charge_col] == pytest.approx(0.10, rel=1e-6)
    assert form.labels["atom"] == {
        f"atom:{index}": index - 1 for index in range(1, 5)
    }
    encoders = form.info["encoders"]["field"]
    assert encoders["atom_name"].inverse_transform(form.data[:, name_col]) == [
        "N", "CA", "O", "CL1"
    ]
    # Element comes from the AutoDock type, so the two-letter chlorine wins.
    assert encoders["element"].inverse_transform(
        form.data[:, element_col]
    ) == ["N", "C", "O", "CL"]
    assert encoders["atom_type"].inverse_transform(
        form.data[:, fields.index("atom_type")]
    ) == ["N", "C", "OA", "Cl"]
    assert form.info["n_atoms"] == 4
    assert form.info["has_partial_charge"] is True


def test_reader_errors(tmp_path):
    with pytest.raises(ReaderError, match="no ATOM/HETATM records"):
        _form(tmp_path, ["REMARK nothing here"], name="empty.pdbqt")

    broken = PDBQT[0][:30] + "   bad  " + PDBQT[0][38:]
    with pytest.raises(ReaderError, match="malformed coordinate line"):
        _form(tmp_path, [broken], name="broken.pdbqt")

    # Only 11 whitespace tokens and an empty fixed window -> no charge/type.
    truncated = (
        "ATOM      7  CB  ALA A   1       1.000   2.000   3.000  1.00  0.00"
    )
    with pytest.raises(ReaderError, match="malformed charge/atom-type columns"):
        _form(tmp_path, [truncated], name="truncated.pdbqt")

    with pytest.raises(ReaderError, match="requires exactly two dims"):
        PdbqtReader().read(
            tmp_path / "lig.pdbqt", dims=["atom"], labels={"atom": "auto"}
        )
