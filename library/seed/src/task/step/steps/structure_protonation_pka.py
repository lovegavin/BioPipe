"""PROPKA titration states and per-residue charges through pdb2pqr."""

from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

from src.core.errors import StepError
from src.core.forms import Form
from src.task.step import Step
from src.task.step.steps.structure_openmm_energy import write_pdb

PROPKA_LINE = re.compile(r"^(ASP|GLU|LYS|HIS|CYS|TYR|ARG)\s+(\d+)\s+([A-Za-z0-9])\s+(-?\d+\.\d+)")
ACID = {"ASP", "GLU", "CYS", "TYR"}
BASE = {"LYS", "ARG", "HIS"}


def parse_propka(text: str) -> list[dict]:
    """Parse the PROPKA summary table from the pdb2pqr log."""

    records: list[dict] = []
    seen: set[tuple[str, int, str]] = set()
    for line in text.splitlines():
        match = PROPKA_LINE.match(line.strip())
        if not match:
            continue
        residue, number, chain, pka = match.groups()
        key = (residue, int(number), chain)
        if key in seen:
            continue
        seen.add(key)
        records.append({"residue": residue, "number": int(number), "chain": chain, "pka": float(pka)})
    return records


def charge_at_ph(residue: str, pka: float, ph: float) -> float:
    if residue in ACID:
        return -1.0 / (1.0 + 10.0 ** (pka - ph))
    if residue in BASE:
        return 1.0 / (1.0 + 10.0 ** (ph - pka))
    return 0.0


def parse_pqr_charges(text: str) -> dict[tuple[str, int, str], float]:
    totals: dict[tuple[str, int, str], float] = {}
    for line in text.splitlines():
        if not line.startswith("ATOM"):
            continue
        tokens = line.split()
        if len(tokens) < 9:
            continue
        try:
            charge = float(tokens[9])
        except (IndexError, ValueError):
            continue
        residue = tokens[3]
        residue_chain = tokens[4]
        try:
            number = int(tokens[5])
        except ValueError:
            continue
        key = (residue, number, residue_chain)
        totals[key] = totals.get(key, 0.0) + charge
    return totals


def run_pdb2pqr(binary: str, pdb_path: Path, out_pqr: Path, ph: float, timeout: int) -> tuple[str, str]:
    # Relocatable runtimes intentionally omit pip's absolute-path launchers.
    # Preserve explicit executables, but resolve default package commands here.
    launcher = [sys.executable, "-m", "pdb2pqr"] if binary in {"pdb2pqr", "pdb2pqr30"} else [binary]
    command = [
        *launcher,
        "--ff=AMBER",
        "--titration-state-method=propka",
        f"--with-ph={ph}",
        "--keep-chain",
        str(pdb_path),
        str(out_pqr),
    ]
    environment = dict(os.environ)
    environment["CUDA_VISIBLE_DEVICES"] = ""
    if binary in {"pdb2pqr", "pdb2pqr30"}:
        # Dependency repair can place packages in a shared or isolated target.
        environment["PYTHONPATH"] = os.pathsep.join(dict.fromkeys(map(str, sys.path)))
        environment["PYTHONNOUSERSITE"] = "1"
    try:
        completed = subprocess.run(command, capture_output=True, text=True, timeout=timeout, env=environment)
    except FileNotFoundError as exc:
        raise StepError(f"structure_protonation_pka: '{binary}' was not found; install pdb2pqr") from exc
    except subprocess.TimeoutExpired as exc:
        raise StepError(f"structure_protonation_pka: pdb2pqr timed out after {timeout} s") from exc
    log = (completed.stdout or "") + "\n" + (completed.stderr or "")
    if completed.returncode != 0 or not out_pqr.is_file():
        tail = " ".join(log.splitlines()[-3:])
        raise StepError(f"structure_protonation_pka: pdb2pqr failed with exit code {completed.returncode}: {tail}")
    return log, out_pqr.read_text()


class StructureProtonationPkaStep(Step):
    provider = "operon-core"
    parameters_file = "structure_protonation_pka.StructureProtonationPkaStep.parameters.json"

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "structure_protonation_pka",
        "version": "1.0.0",
        "kind": "operator",
        "title": "PROPKA protonation states",
        "description": "Predict per-residue pKa with PROPKA and read the resulting protonation charges at a target pH.",
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
        "dependencies": ["pdb2pqr>=3.6"],
        "dependency_imports": ["pdb2pqr"],
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
    }

    def run(self, ctx, inputs):
        params = ctx.step_params
        form = inputs[0]
        if form.data.size == 0:
            raise StepError("structure_protonation_pka: the structure form is empty")
        ph = float(params.get("ph", 7.0))
        if not 0.0 < ph < 14.0:
            raise StepError("structure_protonation_pka: ph must be between 0 and 14")
        binary = str(params.get("pdb2pqr_path", "pdb2pqr30"))
        timeout = int(params.get("timeout_seconds", 600))
        workdir = Path(tempfile.mkdtemp(prefix="pka_"))
        pdb_path = workdir / "input.pdb"
        write_pdb(form, str(params.get("atom_dim", "atom")), str(params.get("field_dim", "field")), pdb_path)
        pqr_path = workdir / "out.pqr"
        log, pqr_text = run_pdb2pqr(binary, pdb_path, pqr_path, ph, timeout)
        records = parse_propka(log)
        if not records:
            raise StepError("structure_protonation_pka: PROPKA returned no titratable residue")
        charges = parse_pqr_charges(pqr_text)
        rows = []
        for record in records:
            key = (record["residue"], record["number"], record["chain"])
            predicted = charge_at_ph(record["residue"], record["pka"], ph)
            observed = charges.get(key, float("nan"))
            rows.append({**record, "charge_hh": predicted, "charge_pqr": observed})
        residue_dim = str(params.get("residue_dim", "residue"))
        data = np.array([[row["pka"], row["charge_hh"], row["charge_pqr"]] for row in rows], dtype=np.float32)
        labels = {f"{row['chain']}:{row['number']}:{row['residue']}": index for index, row in enumerate(rows)}
        missing = sum(1 for row in rows if not np.isfinite(row["charge_pqr"]))
        info = {
            "n_residues": len(rows),
            "n_missing_pqr": missing,
            "ph": ph,
            "pdb2pqr": binary,
            "net_charge_hh": float(sum(row["charge_hh"] for row in rows)),
            "net_charge_pqr": float(sum(row["charge_pqr"] for row in rows if np.isfinite(row["charge_pqr"]))),
            "titratable": [row["residue"] for row in rows],
        }
        output = Form(
            data=data,
            dims=[residue_dim, "statistic"],
            labels={residue_dim: labels, "statistic": {"pka": 0, "charge_hh": 1, "charge_pqr": 2}},
            info={"missing_code": np.nan, **info},
        )
        ctx[str(params.get("output", "pka"))] = output
        self._export_summary = {
            "dims": list(output.dims),
            "labels": {name: dict(mapping) for name, mapping in output.labels.items()},
            "info": info,
        }
