"""Interface atom-pair distance histogram."""

from __future__ import annotations

import numpy as np

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.step.base import Step
from src.task.step.steps._protein_common import decode_column, heavy_atom_mask
from src.task.step.steps._structure_common import atom_coords, field_columns, pick_chain_sides


class InterfaceDistanceHistogramStep(Step):
    """Histogram binder-target heavy-atom pair distances."""

    provider = "operon-core"

    parameters_file = "interface_distance_histogram.InterfaceDistanceHistogramStep.parameters.json"


    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "interface_distance_histogram",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Interface distance histogram",
        "description": (
            "Bin the distances between binder and target heavy atoms across the interface. "
            "Pair counts are reported per distance bin together with quantile statistics."
        ),
        "category": "Machine Learning",
        "icon": "ChartBar",
        "contracts": {
            "version": 1,
            "inputs": [
                {
                    "version": 1,
                    "numeric": True,
                    "dims": [
                        {"param": "atom_dim", "default": "atom"},
                        {"param": "field_dim", "default": "field"},
                    ],
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
                },
            },
        },
        "resources": {
            "memory_modes": ["full"],
            "estimate": "estimate_memory",
        },
        "dependencies": ["numpy>=1.24"],
        "dependency_imports": [],
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
    }

    def run(self, ctx, inputs) -> None:
        form = inputs[0]
        params = ctx.step_params
        atom_dim = str(params.get("atom_dim", "atom"))
        field_dim = str(params.get("field_dim", "field"))
        bin_width = float(params.get("bin_width", 0.5))
        cutoff = float(params.get("cutoff", 8.0))
        output = str(params.get("output", "histogram"))

        if list(form.dims) != [atom_dim, field_dim]:
            raise StepError(
                f"interface_distance_histogram: a PDB form with dims [{atom_dim}, {field_dim}] is "
                f"required, got {list(form.dims)}"
            )
        if cutoff <= 0.0:
            raise StepError("interface_distance_histogram: cutoff must be positive")
        if bin_width <= 0.0:
            raise StepError("interface_distance_histogram: bin_width must be positive")
        if bin_width > cutoff:
            raise StepError("interface_distance_histogram: bin_width must not exceed cutoff")

        field_columns(form, field_dim, ("x", "y", "z", "chain"))
        coords = atom_coords(form, field_dim)
        chain = np.asarray([str(value) for value in decode_column(form, field_dim, "chain")])
        mask = heavy_atom_mask(form, field_dim)
        binder_text = str(params.get("binder_chains", "A"))
        target_text = str(params.get("target_chains", ""))
        binder_chains, target_chains = pick_chain_sides(
            {str(v).strip() for v in chain}, binder_text, target_text, "interface_distance_histogram"
        )
        binder_mask = mask & np.isin(chain, list(binder_chains))
        target_mask = mask & np.isin(chain, list(target_chains))
        if int(binder_mask.sum()) == 0:
            raise StepError(
                "interface_distance_histogram: the binder chains have no heavy atoms in the structure form"
            )
        if int(target_mask.sum()) == 0:
            raise StepError(
                "interface_distance_histogram: the target chains have no heavy atoms in the structure form"
            )

        deltas = coords[binder_mask][:, None, :] - coords[target_mask][None, :, :]
        distances = np.sqrt(np.sum(deltas * deltas, axis=-1))
        selected = distances[(distances > 0.0) & (distances <= cutoff)]
        if selected.size == 0:
            raise StepError(
                "interface_distance_histogram: no binder-target atom pair is within the cutoff"
            )

        n_bins = int(np.ceil(cutoff / bin_width))
        edges = np.linspace(0.0, n_bins * bin_width, n_bins + 1)
        counts, _ = np.histogram(selected, bins=edges)
        total = int(counts.sum())
        fractions = counts.astype(np.float64) / float(total)
        centers = 0.5 * (edges[:-1] + edges[1:])

        rows = []
        for index in range(n_bins):
            rows.append(
                [
                    round(float(edges[index]), 6),
                    round(float(edges[index + 1]), 6),
                    round(float(centers[index]), 6),
                    float(counts[index]),
                    round(float(fractions[index]), 8),
                ]
            )
        labels = {
            "distance_bin": {
                f"{edges[index]:.2f}-{edges[index + 1]:.2f}": index for index in range(n_bins)
            },
            "statistic": {
                "lower": 0,
                "upper": 1,
                "center": 2,
                "count": 3,
                "fraction": 4,
            },
        }
        quantiles = np.percentile(selected, [1.0, 5.0, 25.0, 50.0, 75.0, 95.0, 99.0])
        info = {
            "missing_code": np.nan,
            "binder_chains": sorted(binder_chains),
            "target_chains": sorted(target_chains),
            "cutoff": cutoff,
            "bin_width": bin_width,
            "n_atom_pairs": total,
            "n_binder_atoms": int(binder_mask.sum()),
            "n_target_atoms": int(target_mask.sum()),
            "min_distance": round(float(selected.min()), 4),
            "max_distance": round(float(selected.max()), 4),
            "mean_distance": round(float(selected.mean()), 4),
            "median_distance": round(float(np.median(selected)), 4),
            "quantiles": {
                f"q{int(q)}": round(float(value), 4)
                for q, value in zip([1, 5, 25, 50, 75, 95, 99], quantiles)
            },
            "unit": "A",
        }
        out = Form(
            data=np.asarray(rows, dtype=np.float32),
            dims=["distance_bin", "statistic"],
            labels=labels,
            info=info,
        )
        out.validate()
        ctx[output] = out
        self._export_data = {
            "n_atom_pairs": total,
            "cutoff": cutoff,
            "bin_width": bin_width,
            "binder_chains": sorted(binder_chains),
            "target_chains": sorted(target_chains),
            "min_distance": info["min_distance"],
            "median_distance": info["median_distance"],
            "peak_bin": f"{centers[int(np.argmax(counts))]:.2f}",
        }
        print(
            f"[interface_distance_histogram] pairs={total} bins={n_bins} "
            f"median={info['median_distance']} A"
        )

    def export(self, ctx) -> dict:
        return getattr(self, "_export_data", {})


__all__ = ["InterfaceDistanceHistogramStep"]
