"""esm3_inverse_folding: structure-conditioned sequence design with ESM-3."""

from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np

from src.core.errors import StepError
from src.core.forms import Form
from src.task.step.base import Step
from src.task.step.steps._sequence_common import encode_sequences

_CACHE: dict[tuple[str, str], object] = {}


def load_model(name: str, device: str):
    key = (name, device)
    if key in _CACHE:
        return _CACHE[key]
    try:
        import torch
        from esm.models.esm3 import ESM3
    except ImportError:
        raise StepError(
            "esm3_inverse_folding: the ESM-3 package is required; install it with "
            "'python -m pip install git+https://github.com/evolutionaryscale/esm.git'"
        ) from None
    model = ESM3.from_pretrained(name, device=torch.device(device))
    model.eval()
    try:
        model = model.float()
    except Exception:  # noqa: BLE001
        pass
    _CACHE[key] = model
    return model


def chain_pdb(structure_path: Path, chain: str, workdir: Path) -> tuple[Path, str]:
    """Extract one chain from a PDB file and return its path and native sequence."""

    structure = Path(structure_path).expanduser()
    if not structure.is_file():
        raise StepError(f"esm3_inverse_folding: structure_path {structure} is not a file")
    lines = structure.read_text(errors="replace").splitlines()
    selected = [line for line in lines if line.startswith(("ATOM", "HETATM")) and line[21].strip() == chain]
    if not selected:
        raise StepError(f"esm3_inverse_folding: chain '{chain}' was not found in {structure}")
    target = workdir / f"chain_{chain}.pdb"
    target.write_text("HEADER    ESM3 INPUT\n" + "\n".join(selected) + "\n")
    return target, ""


def three_to_one(resname: str) -> str:
    from src.task.step.steps.proteinmpnn_interface_redesign import _THREE_TO_ONE

    return _THREE_TO_ONE.get(resname.upper(), "X")


def native_sequence(lines: list[str]) -> str:
    sequence = []
    seen = set()
    for line in lines:
        if not line.startswith("ATOM"):
            continue
        key = (line[21].strip(), int(line[22:26]))
        if key in seen:
            continue
        seen.add(key)
        sequence.append(three_to_one(line[17:20].strip()))
    return "".join(sequence)


def recovery(generated: str, native: str) -> float:
    if len(generated) != len(native) or not native:
        return float("nan")
    matches = sum(1 for left, right in zip(generated, native) if left == right)
    return matches / len(native)


def design_rows(sequences: list[str], native: str) -> list[dict]:
    rows = []
    for index, sequence in enumerate(sequences):
        rows.append(
            {
                "design": f"design{index + 1}",
                "sequence": sequence,
                "n_residues": len(sequence),
                "recovery": recovery(sequence, native),
            }
        )
    return rows


class Esm3InverseFoldingStep(Step):
    provider = "operon-core"
    parameters_file = "esm3_inverse_folding.Esm3InverseFoldingStep.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "esm3_inverse_folding",
        "version": "1.0.0",
        "kind": "operator",
        "title": "ESM-3 逆折叠序列设计",
        "description": (
            "Design a sequence for a protein backbone with the official ESM-3 open model, "
            "using coordinates as the only condition, and report recovery against the "
            "native sequence when it is available."
        ),
        "category": "Machine Learning",
        "icon": "Dna",
        "contracts": {
            "version": 1,
            "inputs": [],
            "output": {"mode": "declare", "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": False}},
        },
        "resources": {"memory_modes": ["full"], "estimate": "estimate_memory", "environment": "esm3"},
        "dependencies": [],
        "dependency_imports": ["esm"],
        "inputs_arity": 0,
        "outputs": [],
        "output_parameter": "output",
    }

    def run(self, ctx, inputs):
        params = ctx.step_params
        structure = Path(str(params.get("structure_path", "")))
        chain = str(params.get("chain", "A")).strip() or "A"
        if not structure.is_file():
            raise StepError(f"esm3_inverse_folding: structure_path {structure} is not a file")
        if structure.suffix.lower() not in (".pdb", ".ent"):
            raise StepError("esm3_inverse_folding: structure_path must name a .pdb file")
        device = str(params.get("device", "cpu"))
        if device not in ("cpu", "cuda"):
            raise StepError("esm3_inverse_folding: device must be 'cpu' or 'cuda'")
        steps = int(params.get("num_steps", 20))
        temperature = float(params.get("temperature", 1.0))
        if steps < 1:
            raise StepError("esm3_inverse_folding: num_steps must be at least 1")
        if temperature <= 0:
            raise StepError("esm3_inverse_folding: temperature must be positive")
        workdir = Path(tempfile.mkdtemp(prefix="esm3_if_"))
        chain_file, _ = chain_pdb(structure, chain, workdir)
        lines = chain_file.read_text().splitlines()
        native = native_sequence(lines)
        model = load_model("esm3_sm_open_v1", device)
        try:
            from esm.sdk.api import ESMProtein, GenerationConfig
        except ImportError:
            raise StepError("esm3_inverse_folding: esm.sdk.api is unavailable in the installed ESM package") from None
        protein = ESMProtein.from_pdb(str(chain_file))
        protein.sequence = None
        config = GenerationConfig(
            track="sequence",
            num_steps=steps,
            temperature=temperature,
            condition_on_coordinates_only=True,
        )
        result = model.generate(protein, config)
        sequence = (result.sequence or "").strip().upper()
        if not sequence:
            raise StepError("esm3_inverse_folding: ESM-3 generated an empty sequence")
        if set(sequence) - set("ACDEFGHIKLMNPQRSTVWYX"):
            raise StepError("esm3_inverse_folding: ESM-3 returned non-protein characters")
        rows = design_rows([sequence], native)
        data = np.asarray([[row["n_residues"], row["recovery"] if row["recovery"] == row["recovery"] else np.nan] for row in rows], dtype=np.float32)
        out_name = str(params.get("output", "designs"))
        out_dim = str(params.get("design_dim", "design"))
        ctx[out_name] = Form(
            data=data,
            dims=[out_dim, "statistic"],
            labels={
                out_dim: {row["design"]: index for index, row in enumerate(rows)},
                "statistic": {"n_residues": 0, "recovery": 1},
            },
            info={
                "missing_code": np.nan,
                "sequences": [row["sequence"] for row in rows],
                "native": native,
                "n_residues": len(sequence),
                "recovery": rows[0]["recovery"],
                "num_steps": steps,
                "temperature": temperature,
                "chain": chain,
                "model": "esm3_sm_open_v1",
                "structure_path": str(structure),
            },
        )
        self._export_data = {"recovery": rows[0]["recovery"], "n_residues": len(sequence), "steps": steps}

    def export(self, ctx):
        return getattr(self, "_export_data", {})
