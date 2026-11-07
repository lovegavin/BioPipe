"""esm3_fold: sequence-to-structure prediction with ESM-3."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import numpy as np

from src.core.errors import StepError
from src.core.forms import Form
from src.reader import read_source
from src.task.step.base import Step
from src.task.step.steps._sequence_common import decode_sequences
from src.task.step.steps._native_results import output_directory, remember_native, result_file

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
            "esm3_fold: the ESM-3 package is required; install it with "
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


def fold_sequence(model, sequence: str, *, num_steps: int) -> tuple[object, Path]:
    """Fold one sequence and write the resulting PDB to a temporary path."""

    try:
        from esm.sdk.api import ESMProtein, GenerationConfig
    except ImportError:
        raise StepError("esm3_fold: esm.sdk.api is unavailable in the installed ESM package") from None
    protein = ESMProtein(sequence=sequence)
    config = GenerationConfig(track="structure", num_steps=int(num_steps))
    result = model.generate(protein, config)
    if getattr(result, "coordinates", None) is None:
        raise StepError("esm3_fold: ESM-3 returned no coordinates")
    target = Path(tempfile.mkdtemp(prefix="esm3_fold_")) / "predicted.pdb"
    result.to_pdb(str(target))
    if not target.is_file() or target.stat().st_size == 0:
        raise StepError("esm3_fold: ESM-3 produced no PDB file")
    return result, target


class Esm3FoldStep(Step):
    provider = "operon-core"
    parameters_file = "esm3_fold.Esm3FoldStep.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "esm3_fold",
        "version": "1.0.0",
        "kind": "operator",
        "title": "ESM-3 结构预测",
        "description": (
            "Predict a protein structure from sequence with the official ESM-3 open model "
            "and return the annotated atom table together with pLDDT and pTM summaries."
        ),
        "category": "Machine Learning",
        "icon": "Atom",
        "contracts": {
            "version": 1,
            "inputs": [{"version": 1, "numeric": True, "dims": [{"param": "sequence_dim"}, {"param": "position_dim"}], "labels": [], "parallel": [], "ndim": 2}],
            "output": {"mode": "declare", "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": False}},
        },
        "resources": {"memory_modes": ["full"], "estimate": "estimate_memory", "environment": "esm3"},
        "dependencies": [],
        "dependency_imports": ["esm"],
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
    }

    def run(self, ctx, inputs):
        params = ctx.step_params
        sequences = decode_sequences(inputs[0], str(params.get("sequence_dim", "sequence")), str(params.get("position_dim", "position")))
        if len(sequences) != 1:
            raise StepError(f"esm3_fold: expected exactly one sequence, got {len(sequences)}")
        sequence = sequences[0]
        device = str(params.get("device", "cpu"))
        if device not in ("cpu", "cuda"):
            raise StepError("esm3_fold: device must be 'cpu' or 'cuda'")
        steps = int(params.get("num_steps", 20))
        if steps < 1:
            raise StepError("esm3_fold: num_steps must be at least 1")
        model = load_model("esm3_sm_open_v1", device)
        result, path = fold_sequence(model, sequence, num_steps=steps)
        form = read_source(str(path), ["atom", "field"], {"atom": "auto", "field": "builtin"})
        directory = output_directory(ctx, "esm3_fold")
        native_pdb = directory / "prediction.pdb"
        shutil.copyfile(path, native_pdb)
        path = native_pdb
        if form.data.size == 0:
            raise StepError("esm3_fold: the predicted structure carries no atoms")
        plddt = getattr(result, "plddt", None)
        values = None
        if plddt is not None:
            try:
                values = np.asarray(plddt, dtype=float)
            except (TypeError, ValueError):
                values = None
        mean_plddt = float(np.mean(values)) if values is not None and values.size else float("nan")
        ptm = getattr(result, "ptm", None)
        output_path = str(params.get("output_path", "") or "")
        if output_path:
            target = Path(output_path).expanduser()
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
        form.info.update(
            {
                "mean_plddt": mean_plddt,
                "ptm": float(ptm) if ptm is not None else np.nan,
                "sequence": sequence,
                "n_atoms": int(form.data.shape[0]),
                "num_steps": steps,
                "model": "esm3_sm_open_v1",
            }
        )
        out_name = str(params.get("output", "structure"))
        result_files = [result_file("structure", path, "pdb", "ESM-3 prediction")]
        remember_native(ctx, out_name, result_files)
        ctx[out_name] = form
        self._export_data = {
            "result_files": result_files,
            "n_atoms": int(form.data.shape[0]),
            "mean_plddt": mean_plddt if mean_plddt == mean_plddt else None,
            "ptm": float(ptm) if ptm is not None else None,
            "sequence": sequence,
            "output_path": output_path or None,
        }

    def export(self, ctx):
        return getattr(self, "_export_data", {})
