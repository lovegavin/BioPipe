"""Sliding-window masked redesign scan with the official ESM-IF model."""

from __future__ import annotations

import numpy as np

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.context.base import Context
from src.task.step.base import Step
from ._esm_if_common import chain_residues, load_esm_if, native_sequence, residue_log_probs

_STATISTICS = ("start", "end", "recovery", "mean_log_prob")
_MASK = "<mask>"


def masked_windows(length: int, window: int, step: int) -> list[tuple[int, int]]:
    """Return 0-based ``(start, stop)`` window pairs."""
    if window < 1:
        raise StepError("esm_if_masked_region_scan: window must be at least 1 residue")
    if step < 1:
        raise StepError("esm_if_masked_region_scan: step must be at least 1")
    if window > length:
        raise StepError(
            f"esm_if_masked_region_scan: window {window} is larger than the chain of {length} residues"
        )
    return [(start, start + window) for start in range(0, length - window + 1, step)]


def partial_sequence(sequence: str, start: int, stop: int) -> list[str]:
    return [_MASK if start <= index < stop else residue for index, residue in enumerate(sequence)]


def window_rows(sequence: str, designs: list[str], windows: list[tuple[int, int]], scores: list[np.ndarray]) -> list[list[float]]:
    rows: list[list[float]] = []
    for (start, stop), design, log_probs in zip(windows, designs, scores):
        span = range(start, stop)
        matches = sum(1 for index in span if index < len(design) and design[index] == sequence[index])
        recovery = matches / (stop - start)
        mean_log = float(np.mean(log_probs[start:stop])) if len(log_probs) >= stop else float("nan")
        rows.append([float(start + 1), float(stop), float(recovery), mean_log])
    return rows


class EsmIfMaskedRegionScanStep(Step):
    """Scan a sliding masked window along a chain and score each window."""

    provider = "operon-core"
    parameters_file = "esm_if_masked_region_scan.EsmIfMaskedRegionScanStep.parameters.json"

    @classmethod
    def estimate_memory(cls, inputs, params, profiles):
        return (600 * 1024 * 1024, 0)

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "esm_if_masked_region_scan",
        "version": "1.0.0",
        "kind": "operator",
        "title": "ESM-IF Masked Region Scan",
        "description": "Slide a masked window along a chain and score ESM-IF redesigns of each window.",
        "category": "Machine Learning",
        "icon": "Scissors",
        "contracts": {
            "version": 1,
            "inputs": [
                {
                    "version": 1,
                    "numeric": True,
                    "ndim": 2,
                    "dims": [
                        {"param": "atom_dim", "default": "atom"},
                        {"param": "field_dim", "default": "field"},
                    ],
                    "labels": [],
                    "parallel": [],
                }
            ],
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
        "resources": {
            "memory_modes": ["full"],
            "supports_cuda": False,
            "estimate": "estimate_memory",
        },
        "dependencies": ["numpy>=1.24", "torch>=2.0", "fair-esm>=2.0", "biotite>=0.37"],
        "dependency_imports": ["numpy", "torch", "esm", "biotite"],
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
    }

    def run(self, ctx: Context, inputs: list[Form]) -> None:
        params = ctx.step_params
        form = inputs[0]
        atom_dim = str(params.get("atom_dim") or "atom")
        field_dim = str(params.get("field_dim") or "field")
        chain = str(params.get("chain") or "A")
        model_path = str(params.get("model_path") or "")
        window = int(params.get("window", 6))
        step = int(params.get("step", 1))
        num_samples = int(params.get("num_samples", 1))
        temperature = float(params.get("temperature", 0.1))
        seed = int(params.get("seed", 1))
        out_name = str(params.get("output", "windows"))

        if len(form.dims) != 2 or list(form.dims) != [atom_dim, field_dim]:
            raise StepError(
                f"esm_if_masked_region_scan: a PDB form with dims [{atom_dim}, {field_dim}] is required, "
                f"got {list(form.dims)}"
            )
        if not 1 <= window <= 64:
            raise StepError("esm_if_masked_region_scan: window must be between 1 and 64 residues")
        if not 1 <= step <= 64:
            raise StepError("esm_if_masked_region_scan: step must be between 1 and 64")
        if not 1 <= num_samples <= 8:
            raise StepError("esm_if_masked_region_scan: num_samples must be between 1 and 8")
        if not 0.01 <= temperature <= 2.0:
            raise StepError("esm_if_masked_region_scan: temperature must be in [0.01, 2.0]")
        if seed < 0:
            raise StepError("esm_if_masked_region_scan: seed must not be negative")

        labels, resnames, coords = chain_residues(form, field_dim, chain)
        sequence = native_sequence(resnames)
        if not sequence:
            raise StepError(f"esm_if_masked_region_scan: chain '{chain}' has no residues")
        windows = masked_windows(len(sequence), window, step)
        model, alphabet, torch = load_esm_if(model_path, "esm_if_masked_region_scan")

        designs: list[str] = []
        scores: list[np.ndarray] = []
        with torch.no_grad():
            for index, (start, stop) in enumerate(windows):
                torch.manual_seed(seed + index)
                partial = partial_sequence(sequence, start, stop)
                design = model.sample(coords, partial_seq=partial, temperature=temperature)
                design = str(design).strip().upper()
                if len(design) != len(sequence):
                    raise StepError(
                        f"esm_if_masked_region_scan: the sampled design has length {len(design)}, "
                        f"expected {len(sequence)}"
                    )
                log_probs = np.asarray(residue_log_probs(model, alphabet, coords, design), dtype=np.float64)
                designs.append(design)
                scores.append(log_probs)

        rows = np.asarray(window_rows(sequence, designs, windows, scores), dtype=np.float32)
        names = [f"{start + 1}-{stop}" for start, stop in windows]
        out = Form(
            data=rows,
            dims=["window", "statistic"],
            labels={
                "window": {name: index for index, name in enumerate(names)},
                "statistic": {name: index for index, name in enumerate(_STATISTICS)},
            },
            info={
                "missing_code": np.nan,
                "chain": chain,
                "window": window,
                "step": step,
                "num_samples": num_samples,
                "temperature": temperature,
                "seed": seed,
                "model_path": model_path,
                "native_sequence": sequence,
                "designs": designs,
                "residue_labels": list(labels),
                "windows": names,
            },
        )
        out.validate()
        ctx[out_name] = out
        self._export_data = {
            "chain": chain,
            "num_windows": len(windows),
            "window": window,
            "step": step,
            "native_sequence": sequence,
            "designs": designs,
        }
        best = int(np.nanargmax(rows[:, 2])) if len(rows) else 0
        print(
            f"[esm_if_masked_region_scan] chain {chain}: {len(windows)} windows, "
            f"highest recovery window {names[best] if names else '-'}"
        )

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
