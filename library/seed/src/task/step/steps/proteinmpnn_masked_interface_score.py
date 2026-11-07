"""Interface-restricted ProteinMPNN score: mean NLL over interface residues."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step

from src.task.step.steps._protein_common import (
    column_index,
    decode_column,
    heavy_atom_mask,
    residue_labels,
)
from src.task.step.steps._structure_common import pick_chain_sides
from src.task.step.steps.proteinmpnn_design import MODELS, pdb_chains
from src.task.step.steps.proteinmpnn_interface_redesign import _THREE_TO_ONE
from src.task.step.steps.proteinmpnn_masked_interface_design import (
    _protein_hits,
    interface_residues,
)

_STATISTICS = ("mean_nll", "min_nll", "max_nll", "n_residues")


_ALPHABET = "ACDEFGHIKLMNPQRSTVWYX"


def load_scores(path: Path) -> tuple[np.ndarray, str]:
    """Return per-residue NLL values from a ``conditional_probs_only`` archive."""

    with np.load(path, allow_pickle=True) as archive:
        if "log_p" not in archive or "S" not in archive:
            raise StepError(
                "proteinmpnn_masked_interface_score: the archive carries no "
                "log_p/S arrays; run with --conditional_probs_only"
            )
        log_p = np.asarray(archive["log_p"], dtype=np.float64)
        native = np.asarray(archive["S"], dtype=int).ravel()
    if log_p.ndim != 3 or log_p.shape[0] != 1 or log_p.shape[1] != native.size:
        raise StepError(
            "proteinmpnn_masked_interface_score: unexpected log_p shape "
            f"{log_p.shape} for {native.size} residues"
        )
    rows = np.arange(native.size)
    clipped = np.clip(native, 0, log_p.shape[2] - 1)
    scores = -log_p[0, rows, clipped]
    sequence = "".join(
        _ALPHABET[int(code)] if 0 <= int(code) < len(_ALPHABET) else "X"
        for code in native
    )
    if not np.all(np.isfinite(scores)):
        raise StepError(
            "proteinmpnn_masked_interface_score: the per-residue scores contain "
            "non-finite values"
        )
    return scores, sequence


def sequential_indices(chains: dict[str, list[int]]) -> dict[str, int]:
    """Map ``chain:number`` keys to the 1-based ProteinMPNN residue index.

    The official runner numbers residues across every chain in the order the
    chains appear in the file, so chain-local indices would collide.
    """

    mapping: dict[str, int] = {}
    position = 0
    for chain in sorted(chains):
        numbers = chains[chain]
        for number in numbers:
            position += 1
            mapping[f"{chain}:{int(number)}"] = position
    return mapping


def sequential_index(chains: dict[str, list[int]], label: str) -> int:
    """Map a ``chain:resname:number`` label to the 1-based ProteinMPNN index."""

    parts = str(label).split(":")
    chain = parts[0]
    if chain not in chains:
        raise StepError(
            "proteinmpnn_masked_interface_score: interface residue "
            f"'{label}' belongs to chain '{chain}' which is absent from the "
            "structure file"
        )
    try:
        number = int(float(parts[-1]))
    except ValueError as error:
        raise StepError(
            "proteinmpnn_masked_interface_score: unexpected residue label "
            f"'{label}'"
        ) from error
    if number not in chains[chain]:
        raise StepError(
            "proteinmpnn_masked_interface_score: interface residue "
            f"'{label}' is not an author residue number of the structure file"
        )
    return sequential_indices(chains)[f"{chain}:{number}"]


def summary(scores: np.ndarray, indices: list[int], name: str) -> tuple[float, float, float, int]:
    if not indices:
        raise StepError(
            f"proteinmpnn_masked_interface_score: no residue falls in the {name} "
            "region"
        )
    values = np.asarray([scores[index - 1] for index in indices], dtype=np.float64)
    return (
        float(values.mean()),
        float(values.min()),
        float(values.max()),
        int(values.size),
    )


def score_interface(params, repo: Path, weights: Path, structure: Path) -> tuple[list[float], str, list[str]]:
    """Run the official runner in --conditional_probs_only mode."""

    python = str(params.get("python_executable", "") or "").strip() or sys.executable
    timeout = float(params.get("timeout_seconds", 1800.0))
    device = str(params.get("device", "cpu") or "cpu").strip().lower()
    model = str(params.get("model_name", "v_48_020") or "v_48_020").strip()
    chains_text = str(params.get("chains", "") or "").strip()
    runner = repo / "protein_mpnn_run.py"
    if not runner.is_file():
        raise StepError(
            f"proteinmpnn_masked_interface_score: '{runner}' is missing from the "
            "ProteinMPNN checkout"
        )
    with tempfile.TemporaryDirectory(prefix="mpnn_iface_score_") as tmp:
        out_dir = Path(tmp) / "out"
        command = [
            python,
            str(runner),
            "--pdb_path",
            structure.as_posix(),
            "--out_folder",
            out_dir.as_posix(),
            "--model_name",
            model,
            "--suppress_print",
            "1",
            "--conditional_probs_only",
            "1",
            "--path_to_model_weights",
            weights.as_posix(),
        ]
        if chains_text:
            command.extend(["--pdb_path_chains", chains_text])
        environment = dict(os.environ)
        if device == "cpu":
            environment["CUDA_VISIBLE_DEVICES"] = ""
        try:
            completed = subprocess.run(
                command,
                cwd=repo,
                check=False,
                capture_output=True,
                text=True,
                timeout=timeout,
                env=environment,
            )
        except subprocess.TimeoutExpired as error:
            raise StepError(
                "proteinmpnn_masked_interface_score: the scorer timed out after "
                f"{timeout:.0f} s"
            ) from error
        if completed.returncode != 0:
            tail = (completed.stderr or completed.stdout or "").strip().splitlines()
            message = " | ".join(tail[-3:])
            raise StepError(
                "proteinmpnn_masked_interface_score: the scorer failed with exit "
                f"code {completed.returncode}: {message}"
            )
        folder = out_dir / "conditional_probs_only"
        candidates = sorted(folder.glob(f"{structure.stem}*.npz")) or sorted(folder.glob("*.npz"))
        if not candidates:
            raise StepError(
                "proteinmpnn_masked_interface_score: the scorer produced no "
                f"conditional_probs_only npz under '{folder}'"
            )
        scores, sequence = load_scores(candidates[0])
    return scores.tolist(), sequence, command



def _jsonable(value):
    """Convert numpy values into JSON-serialisable Python objects."""
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


def _export_summary(form) -> dict:
    """Build the export payload for one result Form."""
    return {
        "dims": list(form.dims),
        "labels": _jsonable(form.labels),
        "info": _jsonable(
            {key: value for key, value in form.info.items() if key != "missing_code"}
        ),
    }

class ProteinmpnnMaskedInterfaceScoreStep(Step):
    provider = "operon-core"
    parameters_file = (
        "proteinmpnn_masked_interface_score."
        "ProteinmpnnMaskedInterfaceScoreStep.parameters.json"
    )
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "proteinmpnn_masked_interface_score",
        "version": "1.0.0",
        "kind": "operator",
        "title": "ProteinMPNN interface score",
        "category": "Machine Learning",
        "icon": "Brain",
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
            "output": {
                "mode": "declare",
                "schema": {
                    "ndim": 2,
                    "numeric": True,
                    "info_open": True,
                    "axis_info_open": True,
                    "info": {"missing_code": {"type": ["number", "null"]}},
                },
            },
        },
        "resources": {
            "memory_modes": ["full"],
            "supports_cuda": True,
            "estimate": "estimate_memory",
        },
        "dependencies": ["numpy>=1.24"],
        "dependency_imports": [],
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
        "description": (
            "Score an existing structure/sequence pair with the official "
            "ProteinMPNN runner in --score_only mode and split the per-residue "
            "negative log-likelihood into interface and non-interface residues."
        ),
    }

    def run(self, ctx: Context, inputs) -> None:
        params = ctx.step_params
        form = inputs[0]
        atom_dim = str(params.get("atom_dim", "atom"))
        field_dim = str(params.get("field_dim", "field"))
        out_name = params.get("output", self.name)

        structure_text = str(params.get("structure_path", "") or "").strip()
        structure = Path(structure_text).expanduser()
        if not structure.is_file():
            raise StepError(
                "proteinmpnn_masked_interface_score: structure_path "
                f"'{structure}' is not a file"
            )
        repo = Path(
            str(params.get("proteinmpnn_path", "") or "").strip()
            or os.environ.get("OPERON_PROTEINMPNN_PATH", "")
        ).expanduser()
        if not (repo / "protein_mpnn_run.py").is_file():
            raise StepError(
                "proteinmpnn_masked_interface_score: proteinmpnn_path "
                f"'{repo}' does not look like the official ProteinMPNN checkout"
            )
        weights_text = str(params.get("weights_path", "") or "").strip()
        weights = Path(weights_text).expanduser() if weights_text else repo / "vanilla_model_weights"
        if not weights.is_dir():
            raise StepError(
                "proteinmpnn_masked_interface_score: weights directory "
                f"'{weights}' does not exist"
            )
        model = str(params.get("model_name", "v_48_020") or "v_48_020").strip()
        if model not in MODELS:
            raise StepError(
                "proteinmpnn_masked_interface_score: model_name must be one of "
                + ", ".join(MODELS)
            )
        cutoff = float(params.get("cutoff", 4.5))
        if not 1.0 <= cutoff <= 12.0:
            raise StepError(
                "proteinmpnn_masked_interface_score: cutoff must be between 1 and "
                "12 angstrom"
            )

        column_index(form, field_dim, "chain")
        mask = heavy_atom_mask(form, field_dim)
        if not mask.any():
            raise StepError(
                "proteinmpnn_masked_interface_score: the structure form has no "
                "heavy atoms"
            )
        chains = np.asarray(decode_column(form, field_dim, "chain"), dtype=object)
        labels = residue_labels(form, field_dim)
        coords = np.asarray(form.data[mask][:, [0, 1, 2]], dtype=np.float64)
        if coords.shape[0] == 0:
            raise StepError(
                "proteinmpnn_masked_interface_score: the structure form has no "
                "coordinates"
            )
        binder, target = pick_chain_sides(
            set(str(value) for value in chains),
            params.get("binder_chains", ""),
            params.get("target_chains", ""),
            "proteinmpnn_masked_interface_score",
        )
        binder_hits, target_hits, pairs = interface_residues(
            coords, np.asarray(labels, dtype=object), chains, binder, target, cutoff
        )
        interface = _protein_hits(binder_hits, "binder") | _protein_hits(target_hits, "target")

        scores, sequence, _command = score_interface(params, repo, weights, structure)
        author = pdb_chains(structure)
        total = sum(len(numbers) for numbers in author.values())
        if len(scores) != total:
            raise StepError(
                "proteinmpnn_masked_interface_score: the runner reported "
                f"{len(scores)} residues but the structure file holds {total}"
            )
        index_of = {label: sequential_index(author, label) for label in interface}
        interface_indices = sorted(set(index_of.values()))
        other_indices = [
            index
            for index in range(1, len(scores) + 1)
            if index not in set(interface_indices)
        ]

        rows = [
            summary(scores, interface_indices, "interface"),
            summary(scores, other_indices, "other"),
        ]
        data = np.asarray(rows, dtype=np.float32)
        names = ("interface", "other")
        result = Form(
            data=data,
            dims=["region", "statistic"],
            labels={
                "region": {name: index for index, name in enumerate(names)},
                "statistic": {
                    name: index for index, name in enumerate(_STATISTICS)
                },
            },
            info={
                "missing_code": np.nan,
                "n_interface_residues": len(interface_indices),
                "n_residues": len(scores),
                "n_contact_pairs": int(pairs),
                "interface_residues": sorted(interface),
                "binder_chains": list(binder),
                "target_chains": list(target),
                "cutoff": cutoff,
                "model_name": model,
                "structure_path": structure.as_posix(),
                "sequence": sequence,
            },
        )
        self._export_data = _export_summary(result)
        ctx[out_name] = result

    def export(self, ctx: Context):
        return self._export_data
