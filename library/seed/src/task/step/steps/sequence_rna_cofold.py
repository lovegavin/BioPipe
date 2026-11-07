"""sequence_rna_cofold: cofolding and equilibrium concentrations via RNAcofold."""

from __future__ import annotations

import re
import subprocess
import tempfile
from pathlib import Path

import numpy as np

from src.core.errors import StepError
from src.core.forms import Form
from src.task.step.base import Step
from src.task.step.steps._sequence_common import decode_sequences

_ENERGY = re.compile(r"[\(\[]\s*(?P<energy>-?\d+(?:\.\d+)?)\s*[\)\]]")
_FREQ = re.compile(r"frequency of mfe structure in ensemble\s+(?P<freq>\d+(?:\.\d+)?);\s*delta G binding=\s*(?P<binding>-?\d+(?:\.\d+)?)")
_STRUCTURE = re.compile(r"^[.(){}()\[\],]+&[.(){}()\[\],]+$")


def parse_cofold(text: str) -> dict:
    """Parse RNAcofold -p -c output into one record."""

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    structures = [line for line in lines if "&" in line and _STRUCTURE.match(line.split()[0])]
    if not structures:
        raise StepError("sequence_rna_cofold: RNAcofold reported no cofolded structure")
    energies = []
    for line in structures:
        match = _ENERGY.search(line)
        if match:
            energies.append(float(match.group("energy")))
    match = re.search(r"frequency of mfe structure in ensemble\s+([\d.]+);\s*delta G binding=\s*(-?[\d.]+)", text)
    frequency = float(match.group(1)) if match else float("nan")
    binding = float(match.group(2)) if match else float("nan")
    equilibrium = {}
    for index, line in enumerate(lines):
        if line.startswith("Initial concentrations") or line.startswith("A\t"):
            continue
        tokens = line.split()
        if len(tokens) == 7 and all(re.fullmatch(r"-?\d+(?:\.\d+)?", token) for token in tokens):
            for name, token in zip(("A", "B", "AB", "AA", "BB", "Aeq", "Beq"), tokens):
                equilibrium[name] = float(token)
            break
    return {
        "structure": structures[0].split()[0],
        "mfe": energies[0] if energies else float("nan"),
        "ensemble": energies[1] if len(energies) > 1 else float("nan"),
        "frequency": frequency,
        "binding": binding,
        "equilibrium": equilibrium,
    }


def run_cofold(
    binary: str,
    sequences: tuple[str, str],
    concentrations: tuple[float, float],
    *,
    no_lonely_pairs: bool = False,
    timeout: int = 120,
) -> str:
    cleaned = []
    for index, sequence in enumerate(sequences):
        text = str(sequence).upper().replace("T", "U")
        if not text:
            raise StepError(f"sequence_rna_cofold: sequence {index + 1} is empty")
        if set(text) - set("ACGUN"):
            raise StepError(f"sequence_rna_cofold: sequence {index + 1} contains non-RNA characters (expected ACGUN)")
        cleaned.append(text)
    if min(concentrations) <= 0:
        raise StepError("sequence_rna_cofold: concentrations must be positive")
    command = [binary, "--noPS", "-p", "-c"]
    if no_lonely_pairs:
        command.append("--noLP")
    payload = f"{cleaned[0]}&{cleaned[1]}\n{concentrations[0]:g} {concentrations[1]:g}\n"
    workdir = Path(tempfile.mkdtemp(prefix="rnacofold_"))
    try:
        completed = subprocess.run(command, input=payload, capture_output=True, text=True, timeout=timeout, cwd=workdir)
    except FileNotFoundError:
        raise StepError(f"sequence_rna_cofold: RNAcofold executable '{binary}' was not found; install ViennaRNA") from None
    except subprocess.TimeoutExpired:
        raise StepError(f"sequence_rna_cofold: RNAcofold timed out after {timeout} s") from None
    if completed.returncode != 0:
        tail = ((completed.stderr or completed.stdout).strip().splitlines() or [""])[-1]
        raise StepError(f"sequence_rna_cofold: RNAcofold failed with exit code {completed.returncode}: {tail}")
    return completed.stdout


class SequenceRnaCofoldStep(Step):
    provider = "operon-core"
    parameters_file = "sequence_rna_cofold.SequenceRnaCofoldStep.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "sequence_rna_cofold",
        "version": "1.0.0",
        "kind": "operator",
        "title": "RNA 二聚体共折叠平衡",
        "description": (
            "Cofold two RNA strands with ViennaRNA RNAcofold and report the dimer MFE, "
            "ensemble energy, binding free energy, MFE frequency and equilibrium "
            "concentrations of the five dimer and monomer species."
        ),
        "category": "Sequence",
        "icon": "ShareNetwork",
        "contracts": {
            "version": 1,
            "inputs": [{"version": 1, "numeric": True, "dims": [{"param": "sequence_dim"}, {"param": "position_dim"}], "labels": [], "parallel": [], "ndim": 2}],
            "output": {"mode": "declare", "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": False}},
        },
        "resources": {"memory_modes": ["full"], "estimate": "estimate_memory"},
        "dependencies": [],
        "dependency_imports": [],
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
    }

    def run(self, ctx, inputs):
        params = ctx.step_params
        sequences = decode_sequences(inputs[0], str(params.get("sequence_dim", "sequence")), str(params.get("position_dim", "position")))
        if len(sequences) != 2:
            raise StepError(f"sequence_rna_cofold: expected exactly two sequences, got {len(sequences)}")
        record = parse_cofold(
            run_cofold(
                str(params.get("rnacofold_path", "RNAcofold")),
                (sequences[0], sequences[1]),
                (float(params.get("concentration_a", 1.0)), float(params.get("concentration_b", 1.0))),
                no_lonely_pairs=bool(params.get("no_lonely_pairs", False)),
                timeout=int(params.get("timeout_seconds", 120)),
            )
        )
        columns = ("mfe", "ensemble", "frequency", "binding", "conc_ab", "conc_aa", "conc_bb", "conc_a", "conc_b")
        equilibrium = record["equilibrium"]
        values = np.asarray(
            [[
                record["mfe"],
                record["ensemble"],
                record["frequency"],
                record["binding"],
                equilibrium.get("AB", np.nan),
                equilibrium.get("AA", np.nan),
                equilibrium.get("BB", np.nan),
                equilibrium.get("Aeq", np.nan),
                equilibrium.get("Beq", np.nan),
            ]],
            dtype=np.float32,
        )
        out_dim = str(params.get("dimer_dim", "dimer"))
        out_name = str(params.get("output", "cofold"))
        ctx[out_name] = Form(
            data=values,
            dims=[out_dim, "statistic"],
            labels={
                out_dim: {f"{sequences[0][:6]}&{sequences[1][:6]}": 0},
                "statistic": {name: index for index, name in enumerate(columns)},
            },
            info={
                "missing_code": np.nan,
                "structure": record["structure"],
                "sequences": list(sequences),
                "concentrations": [float(params.get("concentration_a", 1.0)), float(params.get("concentration_b", 1.0))],
                "n_duplex": 1,
            },
        )
        self._export_data = record

    def export(self, ctx):
        return getattr(self, "_export_data", {})
