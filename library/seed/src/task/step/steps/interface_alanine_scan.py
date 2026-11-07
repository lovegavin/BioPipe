"""Computational alanine scanning on a protein interface with MM/GBSA."""

from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np

from src.core.errors import StepError
from src.core.forms import Form
from src.task.step import Step
from src.task.step.steps.interface_mmgbsa_delta import mmgbsa_terms, parse_chains
from src.task.step.steps.structure_openmm_energy import write_pdb

_BACKBONE = {"N", "CA", "C", "O", "OXT", "CB"}


def interface_contacts(pdb_path: Path, binder: tuple[str, ...], target: tuple[str, ...], cutoff: float) -> list[tuple[str, int]]:
    """Return target residues within ``cutoff`` of any binder heavy atom."""

    from openmm.app import PDBFile

    pdb = PDBFile(str(pdb_path))
    positions = np.asarray(pdb.positions.value_in_unit(pdb.positions.unit), dtype=np.float64) * 10.0
    atoms = list(pdb.topology.atoms())
    binder_mask = np.array([atom.residue.chain.id in binder and atom.element.symbol != "H" for atom in atoms])
    counts: dict[tuple[str, int], int] = {}
    binder_positions = positions[binder_mask]
    if binder_positions.size == 0:
        raise StepError("interface_alanine_scan: the binder side has no heavy atoms")
    for index, atom in enumerate(atoms):
        chain = atom.residue.chain.id
        if chain not in target or atom.element.symbol == "H":
            continue
        distances = np.linalg.norm(binder_positions - positions[index], axis=1)
        contacts = int((distances <= cutoff).sum())
        if contacts:
            key = (chain, atom.residue.id and atom.residue.index)
            key = (chain, atom.residue.index)
            counts[key] = max(counts.get(key, 0), contacts)
    labels: list[tuple[str, int]] = []
    for atom in atoms:
        chain = atom.residue.chain.id
        if chain in target:
            key = (chain, atom.residue.index)
            if key in counts and key not in labels:
                labels.append(key)
    return labels


def residue_label(atoms, residue_index: int) -> tuple[str, str, int]:
    for atom in atoms:
        if atom.residue.index == residue_index:
            return atom.residue.chain.id, atom.residue.name, int(atom.residue.id)
    raise StepError(f"interface_alanine_scan: residue index {residue_index} is not in the topology")


def mutate_to_alanine(text: str, chain: str, number: int) -> str:
    """Truncate one residue to ALA (N/CA/C/O/CB) and drop its hydrogens."""

    output: list[str] = []
    changed = False
    for line in text.splitlines():
        if line.startswith(("ATOM", "HETATM")) and line[21] == chain and line[22:26].strip() == str(number):
            name = line[12:16].strip()
            element = line[76:78].strip().upper() or name[:1].upper()
            if element == "H":
                continue
            if name not in _BACKBONE:
                continue
            changed = True
            line = f"{line[:17]}ALA{line[20:]}"
        output.append(line)
    if not changed:
        raise StepError(f"interface_alanine_scan: residue {chain}:{number} is not in the structure file")
    return "\n".join(output) + "\n"


def scan_residues(pdb_path: Path, text: str, binder: tuple[str, ...], target: tuple[str, ...], cutoff: float, max_residues: int, ph: float, forcefield: str, implicit: str) -> list[dict]:
    from openmm.app import PDBFile

    pdb = PDBFile(str(pdb_path))
    atoms = list(pdb.topology.atoms())
    contacts = interface_contacts(pdb_path, binder, target, cutoff)
    scored = []
    seen: set[tuple[str, int]] = set()
    for chain, residue_index in contacts:
        if residue_index in seen:
            continue
        seen.add(residue_index)
        residue_chain, name, number = residue_label(atoms, residue_index)
        if name == "ALA":
            continue
        scored.append((number, residue_chain, name))
    scored.sort()
    scored = scored[:max_residues]
    if not scored:
        raise StepError("interface_alanine_scan: no non-alanine residue lies within the interface cutoff")

    workdir = Path(tempfile.mkdtemp(prefix="alanine_"))
    wt = mmgbsa_terms(pdb_path, forcefield_name=forcefield, implicit=implicit, ph=ph, binder=binder, target=target)
    wt_delta = wt["complex"]["total"] - wt["binder"]["total"] - wt["target"]["total"]
    results: list[dict] = []
    for position, (number, chain, name) in enumerate(scored, start=1):
        mutant_text = mutate_to_alanine(text, chain, number)
        mutant_path = workdir / f"mutant_{chain}{number}.pdb"
        mutant_path.write_text(mutant_text)
        mutant = mmgbsa_terms(mutant_path, forcefield_name=forcefield, implicit=implicit, ph=ph, binder=binder, target=target)
        mutant_delta = mutant["complex"]["total"] - mutant["binder"]["total"] - mutant["target"]["total"]
        results.append(
            {
                "chain": chain,
                "number": number,
                "residue": name,
                "wt_delta": wt_delta,
                "mutant_delta": mutant_delta,
                "delta_delta": mutant_delta - wt_delta,
            }
        )
    return results


class InterfaceAlanineScanStep(Step):
    provider = "operon-core"
    parameters_file = "interface_alanine_scan.InterfaceAlanineScanStep.parameters.json"

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "interface_alanine_scan",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Interface alanine scan",
        "description": "Computational alanine scanning of interface residues with single-point MM/GBSA energy differences.",
        "category": "Structure",
        "icon": "BatteryFull",
        "contracts": {
            "version": 1,
            "inputs": [
                {
                    "version": 1,
                    "numeric": True,
                    "dims": [{"param": "atom_dim"}, {"param": "field_dim"}],
                    "labels": [],
                    "parallel": [],
                    "ndim": 2,
                }
            ],
            "output": {"mode": "declare", "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": False}},
            "outputs": [],
        },
        "resources": {"memory_modes": ["full"], "estimate": "estimate_memory"},
        "dependencies": [],
        "dependency_imports": ["openmm", "pdbfixer"],
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
    }

    def run(self, ctx, inputs):
        params = ctx.step_params
        binder = parse_chains(params.get("binder_chains", ""), "binder_chains")
        target = parse_chains(params.get("target_chains", ""), "target_chains")
        overlap = set(binder) & set(target)
        if overlap:
            raise StepError(f"interface_alanine_scan: chain(s) {sorted(overlap)} are in both sides")
        form = inputs[0]
        if form.data.size == 0:
            raise StepError("interface_alanine_scan: the structure form is empty")
        cutoff = float(params.get("cutoff", 4.5))
        if not 1.0 <= cutoff <= 12.0:
            raise StepError("interface_alanine_scan: cutoff must be between 1 and 12 angstrom")
        max_residues = int(params.get("max_residues", 10))
        if max_residues < 1:
            raise StepError("interface_alanine_scan: max_residues must be at least 1")
        ph = float(params.get("ph", 7.0))
        if not 0.0 < ph < 14.0:
            raise StepError("interface_alanine_scan: ph must be between 0 and 14")
        workdir = Path(tempfile.mkdtemp(prefix="alanine_scan_"))
        pdb_path = workdir / "complex.pdb"
        write_pdb(form, str(params.get("atom_dim", "atom")), str(params.get("field_dim", "field")), pdb_path)
        text = pdb_path.read_text()
        rows = scan_residues(
            pdb_path,
            text,
            binder,
            target,
            cutoff,
            max_residues,
            ph,
            str(params.get("forcefield", "amber14-all.xml")),
            str(params.get("implicit_model", "implicit/gbn2.xml")),
        )
        mutation_dim = str(params.get("mutation_dim", "mutation"))
        data = np.array(
            [[row["wt_delta"], row["mutant_delta"], row["delta_delta"]] for row in rows],
            dtype=np.float32,
        )
        labels = {f"{row['chain']}:{row['number']}:{row['residue']}": index for index, row in enumerate(rows)}
        info = {
            "n_mutations": len(rows),
            "wt_delta_kj": rows[0]["wt_delta"],
            "binder_chains": list(binder),
            "target_chains": list(target),
            "cutoff": cutoff,
            "max_residues": max_residues,
            "mutations": [{key: row[key] for key in ("chain", "number", "residue", "delta_delta")} for row in rows],
        }
        output = Form(
            data=data,
            dims=[mutation_dim, "statistic"],
            labels={mutation_dim: labels, "statistic": {"wt_delta_kj": 0, "mutant_delta_kj": 1, "delta_delta_kj": 2}},
            info={"missing_code": np.nan, **info},
        )
        ctx[str(params.get("output", "scan"))] = output
        self._export_summary = {
            "dims": list(output.dims),
            "labels": {name: dict(mapping) for name, mapping in output.labels.items()},
            "info": info,
        }
