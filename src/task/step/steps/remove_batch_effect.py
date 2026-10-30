"""Remove batch effects with a linear model (limma-style).

The operator fits one linear model per feature with an intercept, batch
dummy variables and optional covariates. Batch coefficients are then
subtracted from the expression matrix; the intercept and covariate
effects are retained. This matches ``limma::removeBatchEffect`` for
additive batch effects without batch-covariate interactions.
"""
from __future__ import annotations

import numpy as np

from src.core import StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step

from ._ext_common import (
    axis_labels,
    group_values,
    labels_in_order,
    make_form,
    reorder,
    require_dims,
)


class RemoveBatchEffectStep(Step):
    name = "remove_batch_effect"
    title = "Remove batch effect"
    category = "Analysis"
    builtin_package = "biopipe-core"
    inputs_arity = 2
    outputs = []
    input_contracts = [
        port(ndim=2, dims=[param("feature_dim", "feature"), param("sample_dim", "sample")]),
        {**port(ndim=2, dims=[param("sample_dim", "sample")]),
         "labels_any": [param("batch_label")]},
    ]
    output_contract = {"mode": "declare", "schema": {
        "ndim": 2, "numeric": True, "info_open": False, "axis_info_open": False,
        "info": {"missing_code": {"type": ["number", "null"]}}}}
    output_parameter = "output"
    parameters_schema = {
        "type": "object",
        "properties": {
            "feature_dim": {"type": "string", "default": "feature"},
            "sample_dim": {"type": "string", "default": "sample"},
            "batch_label": {"type": "string"},
            "covariates": {"type": "array", "items": {"type": "string"}, "default": []},
            "output": {"type": "string"},
        },
        "required": ["batch_label"],
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        expr, meta = inputs
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        batch_label = ctx.step_params["batch_label"]
        covariates = list(ctx.step_params.get("covariates", []))
        out_name = ctx.step_params.get("output", self.name)
        require_dims(expr, feature_dim, sample_dim, label="expression")
        require_dims(meta, sample_dim, label="metadata")
        data = reorder(expr, feature_dim, sample_dim)
        features = labels_in_order(expr, feature_dim)
        samples = labels_in_order(expr, sample_dim)
        if not np.isfinite(data).all():
            raise StepError("remove_batch_effect: expression matrix contains non-finite values")
        if data.shape[1] < 2:
            raise StepError("remove_batch_effect: need at least two samples")

        meta_samples, values = group_values(meta, sample_dim, batch_label)
        by_sample = {s: _group_key(v) for s, v in zip(meta_samples, values)}
        missing = [s for s in samples if s not in by_sample]
        if missing:
            raise StepError(f"remove_batch_effect: {len(missing)} expression samples have no batch label")

        batch_levels: list[str] = []
        for s in samples:
            if by_sample[s] not in batch_levels:
                batch_levels.append(by_sample[s])
        if len(batch_levels) < 2:
            raise StepError("remove_batch_effect: at least two batches are required")
        codes = np.asarray([batch_levels.index(by_sample[s]) for s in samples], dtype=np.int64)

        columns = [np.ones(len(samples), dtype=np.float64)]
        batch_cols: list[int] = []
        # Sum-to-zero (effect) coding, matching limma's contr.sum batch
        # matrix. With an intercept this centers all batches on the grand
        # mean rather than on the first batch.
        for b in range(len(batch_levels) - 1):
            column = np.zeros(len(samples), dtype=np.float64)
            column[codes == b] = 1.0
            column[codes == len(batch_levels) - 1] = -1.0
            batch_cols.append(len(columns))
            columns.append(column)

        cover_info: dict[str, str] = {}
        for name in covariates:
            if name == batch_label:
                raise StepError("remove_batch_effect: covariates must not repeat batch_label")
            cov_samples, cov_values = group_values(meta, sample_dim, name)
            cov_by_sample = {s: v for s, v in zip(cov_samples, cov_values)}
            missing_cov = [s for s in samples if s not in cov_by_sample]
            if missing_cov:
                raise StepError(
                    f"remove_batch_effect: {len(missing_cov)} samples have no covariate {name!r}"
                )
            raw = [cov_by_sample[s] for s in samples]
            numeric = True
            try:
                numeric_values = np.asarray([float(v) for v in raw], dtype=np.float64)
            except (TypeError, ValueError):
                numeric = False
            if numeric:
                if not np.isfinite(numeric_values).all():
                    raise StepError(f"remove_batch_effect: covariate {name!r} has non-finite values")
                columns.append(numeric_values)
                cover_info[name] = "numeric"
            else:
                levels: list[str] = []
                for v in raw:
                    if _group_key(v) not in levels:
                        levels.append(_group_key(v))
                if len(levels) < 2:
                    raise StepError(f"remove_batch_effect: covariate {name!r} has fewer than two levels")
                for level in levels[1:]:
                    columns.append(np.asarray([_group_key(v) == level for v in raw], dtype=np.float64))
                cover_info[name] = f"categorical:{len(levels)}"

        design = np.column_stack(columns)
        rank = int(np.linalg.matrix_rank(design))
        if rank < design.shape[1]:
            raise StepError(
                "remove_batch_effect: design is rank deficient; batch is confounded with covariates"
            )
        beta, _, _, _ = np.linalg.lstsq(design, data.T, rcond=None)
        batch_effect = design[:, batch_cols] @ beta[batch_cols, :]
        corrected = data - batch_effect.T

        labels = {
            feature_dim: axis_labels(features, feature_dim),
            sample_dim: axis_labels(samples, sample_dim),
        }
        ctx[out_name] = make_form(corrected, [feature_dim, sample_dim], labels)
        sizes = {name: int((codes == i).sum()) for i, name in enumerate(batch_levels)}
        self._export_data = {
            "method": "linear_model",
            "batch_label": batch_label,
            "batches": batch_levels,
            "batch_sizes": sizes,
            "covariates": cover_info,
            "n_features": len(features),
            "n_samples": len(samples),
        }
        ctx.metadata.setdefault(self.name, {})[out_name] = {
            "method": "linear_model",
            "n_batches": len(batch_levels),
            "n_features": len(features),
            "n_samples": len(samples),
        }
        print(
            f"[remove_batch_effect] {len(features)} features, {len(samples)} samples, "
            f"{len(batch_levels)} batches, covariates={list(cover_info)}"
        )

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})


def _group_key(value) -> str:
    try:
        number = float(value)
        if number.is_integer():
            return str(int(number))
        return str(number)
    except (TypeError, ValueError):
        return str(value)
