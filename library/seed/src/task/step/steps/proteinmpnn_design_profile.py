"""Per-position amino-acid frequency matrix from ProteinMPNN sampled designs."""
from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step

from .proteinmpnn_design import MODELS
from .proteinmpnn_position_entropy import (
    AA_ORDER,
    read_fasta,
    run_designer,
    split_designs,
)


def amino_acid_profile(designs: list[str], native: str) -> list[dict]:
    """Count amino acids per designed position."""
    if not designs:
        raise StepError("proteinmpnn_design_profile: no designs were generated")
    lengths = {len(sequence) for sequence in designs}
    if lengths != {len(native)}:
        raise StepError(
            "proteinmpnn_design_profile: every design must match the native "
            f"length {len(native)}, got {sorted(lengths)}"
        )
    rows: list[dict] = []
    for position in range(len(native)):
        counts = np.zeros(len(AA_ORDER), dtype=np.float64)
        for sequence in designs:
            residue = sequence[position]
            if residue not in AA_ORDER:
                raise StepError(
                    "proteinmpnn_design_profile: design residue "
                    f"'{residue}' at position {position + 1} is not a standard amino acid"
                )
            counts[AA_ORDER.index(residue)] += 1.0
        frequencies = counts / float(counts.sum())
        rows.append(
            {
                "position": position + 1,
                "frequencies": frequencies,
                "consensus": AA_ORDER[int(np.argmax(frequencies))],
                "recovery": float(frequencies[AA_ORDER.find(native[position])]),
                "n_observed": int(counts.sum()),
            }
        )
    return rows


def profile_matrix(rows: list[dict]) -> np.ndarray:
    return np.asarray([row["frequencies"] for row in rows], dtype=np.float32)


class ProteinmpnnDesignProfileStep(Step):
    provider = "operon-core"
    parameters_file = (
        "proteinmpnn_design_profile.ProteinmpnnDesignProfileStep.parameters.json"
    )
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "proteinmpnn_design_profile",
        "version": "1.0.0",
        "kind": "operator",
        "title": "ProteinMPNN design profile",
        "category": "Machine Learning",
        "icon": "ChartBar",
        "contracts": {
            "version": 1,
            "inputs": [],
            "output": {
                "mode": "declare",
                "schema": {
                    "ndim": 2,
                    "numeric": True,
                    "info_open": True,
                    "axis_info_open": True,
                },
            },
        },
        "resources": {"memory_modes": ["full"], "supports_cuda": True},
        "dependencies": ["numpy>=1.24", "torch>=2.0"],
        "dependency_imports": ["numpy"],
        "inputs_arity": 0,
        "outputs": [],
        "output_parameter": "output",
    }

    def run(self, ctx: Context, inputs: list) -> None:
        params = ctx.step_params
        structure = Path(str(params.get("structure_path") or "")).expanduser()
        if not structure.is_file():
            raise StepError(
                "proteinmpnn_design_profile: structure_path must point at an existing PDB file"
            )
        repo = Path(str(params.get("proteinmpnn_path") or "")).expanduser()
        if not (repo / "protein_mpnn_run.py").is_file():
            raise StepError(
                "proteinmpnn_design_profile: proteinmpnn_path must contain protein_mpnn_run.py"
            )
        model_name = str(params.get("model_name") or "v_48_020")
        if model_name not in MODELS:
            raise StepError(
                f"proteinmpnn_design_profile: model_name must be one of {list(MODELS)}"
            )
        device = str(params.get("device") or "cpu")
        if device not in {"cpu", "cuda"}:
            raise StepError(
                "proteinmpnn_design_profile: device must be 'cpu' or 'cuda'"
            )
        raw_samples = params.get("num_seq_per_target")
        num_samples = 16 if raw_samples is None else int(raw_samples)
        if num_samples < 2:
            raise StepError(
                "proteinmpnn_design_profile: num_seq_per_target must be at least 2"
            )
        raw_temperature = params.get("sampling_temp")
        temperature = 0.1 if raw_temperature is None else float(raw_temperature)
        if not 0.0 < temperature <= 1.0:
            raise StepError(
                "proteinmpnn_design_profile: sampling_temp must be in (0, 1]"
            )
        seed = int(params["seed"]) if params.get("seed") is not None else 1
        if seed < 0:
            raise StepError("proteinmpnn_design_profile: seed must not be negative")
        raw_timeout = params.get("timeout")
        timeout = 1800 if raw_timeout is None else int(raw_timeout)
        position_dim = str(params.get("position_dim") or "position")
        residue_dim = str(params.get("amino_acid_dim") or "amino_acid")
        if position_dim == residue_dim:
            raise StepError(
                "proteinmpnn_design_profile: position_dim and amino_acid_dim must differ"
            )
        out_name = params["output"]
        with tempfile.TemporaryDirectory(prefix="operon-mpnn-profile-") as tmp:
            out_dir = Path(tmp)
            run_designer(
                repo,
                structure,
                out_dir,
                {
                    "python_executable": params.get("python_executable") or "",
                    "weights_path": params.get("weights_path") or "",
                    "num_seq_per_target": num_samples,
                    "sampling_temp": temperature,
                    "seed": seed,
                    "model_name": model_name,
                    "chains": params.get("chains") or "",
                    "device": device,
                    "timeout": timeout,
                },
            )
            fasta = out_dir / "seqs" / f"{structure.stem}.fa"
            if not fasta.is_file():
                raise StepError(
                    "proteinmpnn_design_profile: the designer produced no FASTA at "
                    f"'{fasta}'"
                )
            native, designs = split_designs(read_fasta(fasta))
        rows = amino_acid_profile(designs, native)
        data = profile_matrix(rows)
        if not np.isfinite(data).all():
            raise StepError(
                "proteinmpnn_design_profile: the profile contains non-finite values"
            )
        labels = {
            position_dim: {str(index + 1): index for index in range(len(rows))},
            residue_dim: {residue: index for index, residue in enumerate(AA_ORDER)},
        }
        form = Form(
            data=data,
            dims=[position_dim, residue_dim],
            labels=labels,
            info={
                "missing_code": np.nan,
                "native_sequence": native,
                "consensus": [row["consensus"] for row in rows],
                "recovery": [round(row["recovery"], 6) for row in rows],
                "model_name": model_name,
                "num_samples": len(designs),
                "sampling_temp": temperature,
                "seed": seed,
                "chains": str(params.get("chains") or ""),
                "n_positions": len(rows),
                "aa_order": AA_ORDER,
            },
        )
        form.validate()
        ctx[out_name] = form
        self._export_data = {
            "positions": len(rows),
            "amino_acids": len(AA_ORDER),
            "num_samples": len(designs),
            "model_name": model_name,
            "consensus": "".join(row["consensus"] for row in rows),
            "native_sequence": native,
        }
        print(
            f"[proteinmpnn_design_profile] {len(rows)} positions x "
            f"{len(designs)} designs, model {model_name}"
        )

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
