"""Structure prediction with the official ESMFold implementation of ``fair-esm``."""

from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np

from src.core.errors import StepError
from src.reader import read_source
from src.task.step.base import Step
from src.task.step.steps._protein_common import column_index, has_column
from src.task.step.steps._resources_common import remedy, check_resource, load_resources
from src.task.step.steps._sequence_common import decode_sequences


def _load_model(device: str, chunk_size: int, weights_dir: str = ""):
    """Load ESMFold 3B (lazy import so the operator stays importable without fair-esm)."""

    if weights_dir:
        try:
            from transformers import EsmForProteinFolding
        except ImportError as exc:  # pragma: no cover - depends on the environment
            raise StepError(
                "esmfold_predict: weights_dir needs transformers; install it with "
                "'python -m pip install transformers'"
            ) from exc
        model = EsmForProteinFolding.from_pretrained(weights_dir)
        model = model.eval()
        if device == "cuda":
            model = model.cuda()
        return model

    try:
        import esm
    except ImportError as exc:  # pragma: no cover - depends on the environment
        raise StepError(
            "esmfold_predict: the 'fair-esm' package is required; install it with "
            "'python -m pip install fair-esm'"
        ) from exc
    model = esm.pretrained.esmfold_v1()
    model = model.eval()
    if device == "cuda":
        model = model.cuda()
    if chunk_size:
        try:
            model.set_chunk_size(int(chunk_size))
        except AttributeError:  # pragma: no cover - torchscript variant
            pass
    return model


def _apply_recycles(model, num_recycles: int) -> None:
    inner = getattr(model, "model", None)
    if inner is not None and hasattr(inner, "num_recycles"):
        try:
            inner.num_recycles = int(num_recycles)
        except Exception:  # pragma: no cover - defensive, torchscript attribute
            pass


class EsmfoldPredictStep(Step):
    """Predict one structure with ESMFold and report its confidence."""

    provider = "biopipe-core"

    parameters_file = "esmfold_predict.EsmfoldPredictStep.parameters.json"

    definition = {
        "protocol_version": 3,
        "id": "esmfold_predict",
        "version": "1.0.0",
        "kind": "operator",
        "title": "ESMFold structure prediction",
        "description": (
            "Fold one amino-acid sequence with the official ESMFold implementation shipped in "
            "fair-esm (esm.pretrained.esmfold_v1) and return the predicted PDB together with its "
            "mean pLDDT. The 3B checkpoint is downloaded on first use; set BIOPIPE_ESMFOLD_WEIGHTS "
            "or pre-populate the torch hub cache to run offline."
        ),
        "category": "Machine Learning",
        "icon": "Atom",
        "contracts": {
            "version": 1,
            "inputs": [
                {
                    "version": 1,
                    "numeric": True,
                    "dims": [{"param": "sequence_dim"}, {"param": "position_dim"}],
                    "labels": [],
                    "parallel": [],
                    "ndim": 2,
                    "info": {
                        "representation": {"type": "string", "const": "sequence_codes"},
                        "alphabet_map": {"type": "object", "optional": True},
                    },
                },
            ],
            "output": {
                "mode": "declare",
                "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True},
            },
        },
        "resources": {"memory_modes": ["full"], "estimate": "estimate_memory"},
        "dependencies": ['numpy>=1.24', 'scipy>=1.11'],
        "dependency_imports": ['numpy', 'scipy'],
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
    }

    def run(self, ctx, inputs) -> None:
        params = ctx.step_params
        (sequences,) = inputs
        sequence_dim = str(params.get("sequence_dim") or "sequence")
        position_dim = str(params.get("position_dim") or "position")
        device = str(params.get("device") or "cpu")
        chunk_size = int(params.get("chunk_size") if params.get("chunk_size") is not None else 64)
        num_recycles = int(params.get("num_recycles") if params.get("num_recycles") is not None else 4)
        out_name = str(params.get("output") or "structure")

        decoded = decode_sequences(sequences, sequence_dim, position_dim)
        if len(decoded) != 1:
            raise StepError(f"esmfold_predict: expected exactly one sequence, got {len(decoded)}")
        sequence = decoded[0]
        if not sequence:
            raise StepError("esmfold_predict: the input sequence is empty")
        if device not in ("cpu", "cuda"):
            raise StepError(f"esmfold_predict: device must be 'cpu' or 'cuda', got '{device}'")
        if num_recycles < 1:
            raise StepError("esmfold_predict: num_recycles must be at least 1")

        resource = load_resources()["esmfold"]
        status = check_resource(resource)
        if status["status"] == "partial" and status["root"]:
            print(f"[esmfold_predict] note: {remedy(status)}")

        model = _load_model(device, chunk_size, str(params.get("weights_dir", "") or ""))
        _apply_recycles(model, num_recycles)
        try:
            pdb_text = model.infer_pdb(sequence)
        except Exception as exc:  # pragma: no cover - inference failures vary
            raise StepError(f"esmfold_predict: inference failed: {exc}") from exc
        if not pdb_text or "ATOM" not in pdb_text:
            raise StepError("esmfold_predict: the model produced no atom records")

        workdir = Path(tempfile.mkdtemp(prefix="biopipe_esmfold_"))
        try:
            path = workdir / "prediction.pdb"
            path.write_text(pdb_text, encoding="utf-8")
            form = read_source(path, ["atom", "field"], {"atom": "auto", "field": "builtin"})
            mean_plddt = float("nan")
            if has_column(form, "field", "bfactor"):
                values = np.asarray(form.data[:, column_index(form, "field", "bfactor")], dtype=np.float64)
                finite = np.isfinite(values)
                if finite.any():
                    mean_plddt = float(values[finite].mean())
            form.info.update(
                {
                    "mean_plddt": mean_plddt,
                    "sequence": sequence,
                    "num_recycles": num_recycles,
                    "model": "esmfold_3B_v1",
                }
            )
        finally:
            import shutil

            shutil.rmtree(workdir, ignore_errors=True)

        ctx[out_name] = form
        self._export_data = {
            "mean_plddt": mean_plddt,
            "n_residues": len(sequence),
            "num_recycles": num_recycles,
        }
        print(f"[esmfold_predict] {len(sequence)} residues, mean pLDDT {mean_plddt:.2f}")

    def export(self, ctx) -> dict:
        return getattr(self, "_export_data", {})
