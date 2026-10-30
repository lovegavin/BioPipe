"""Box's M test for homogeneity of covariance matrices."""
from __future__ import annotations

import numpy as np
from scipy import stats

from src.core import StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step

from ._stats20_common import scalar_form
from ._stats21_common import numeric_column, table_frame


class BoxMStep(Step):
    """Box's M test for equal covariance matrices across groups.

    Uses the chi-square approximation from ``biotools::boxM``:
    ``M=(N-k)log|S_pooled|-sum((n_i-1)log|S_i|)``,
    ``C=((2p^2+3p-1)/(6(p+1)(k-1)))*(sum(1/(n_i-1))-1/(N-k))``,
    ``X2=M*(1-C)`` with ``df=p(p+1)(k-1)/2``.
    """

    name = "box_m"
    title = "Box's M test"
    category = "Statistics"
    builtin_package = "biopipe-core"
    dependencies = ["numpy>=1.24", "scipy>=1.11"]
    dependency_imports = ["numpy", "scipy"]
    inputs_arity = 1
    outputs = []
    output_parameter = "output"
    input_contracts = [port(ndim=2, dims=[param("sample_dim", "sample"), param("feature_dim", "feature")])]
    output_contract = {"mode": "declare", "schema": {
        "ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True}}
    parameters_schema = {
        "type": "object",
        "properties": {
            "sample_dim": {"type": "string", "default": "sample"},
            "feature_dim": {"type": "string", "default": "feature"},
            "group_label": {"type": "string", "title": "分组字段"},
            "output": {"type": "string"},
        },
        "required": ["group_label"],
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        group_label = ctx.step_params["group_label"]
        out_name = ctx.step_params.get("output", self.name)
        frame = table_frame(form, sample_dim, feature_dim, "box_m")
        if group_label not in frame.columns:
            raise StepError(f"box_m: group column {group_label!r} not found")
        features = [name for name in frame.columns if name not in ("__sample__", group_label)]
        if not features:
            raise StepError("box_m: no feature columns")
        matrix = np.column_stack([
            np.asarray(numeric_column(frame, name, "box_m"), dtype=np.float64)
            for name in features
        ])
        groups = frame[group_label].astype(str).to_numpy()
        if not np.isfinite(matrix).all():
            raise StepError("box_m: require complete numeric rows")
        names = list(dict.fromkeys(groups.tolist()))
        if len(names) < 2:
            raise StepError("box_m: need at least two groups")
        n_total, p = matrix.shape
        sized = []
        for name in names:
            block = matrix[groups == name]
            if block.shape[0] <= p:
                raise StepError(f"box_m: group {name!r} needs more than {p} samples")
            covariance = np.cov(block, rowvar=False, ddof=1)
            if np.linalg.matrix_rank(covariance) < p:
                raise StepError(f"box_m: covariance for group {name!r} is singular")
            sized.append((block.shape[0], covariance))
        k = len(sized)
        df_pooled = n_total - k
        pooled = sum((n_i - 1) * cov for n_i, cov in sized) / df_pooled
        if np.linalg.matrix_rank(pooled) < p:
            raise StepError("box_m: pooled covariance is singular")
        log_pooled = float(np.linalg.slogdet(pooled)[1])
        log_groups = sum((n_i - 1) * float(np.linalg.slogdet(cov)[1]) for n_i, cov in sized)
        m_stat = df_pooled * log_pooled - log_groups
        correction = ((2.0 * p * p + 3.0 * p - 1.0) / (6.0 * (p + 1.0) * (k - 1.0))) * (
            sum(1.0 / (n_i - 1.0) for n_i, _ in sized) - 1.0 / df_pooled
        )
        chi2 = max(0.0, m_stat * (1.0 - correction))
        df = int(p * (p + 1) / 2 * (k - 1))
        p_value = float(stats.chi2.sf(chi2, df))
        out = scalar_form(
            [m_stat, chi2, float(df), p_value, float(k), float(p), float(n_total)],
            ["M", "chi2", "df", "p", "n_groups", "n_features", "n"],
            "box_m",
        )
        out.info.update({"correction": correction, "method": "Box's M chi-square approximation"})
        ctx[out_name] = out
        self._export_data = {
            "M": m_stat, "chi2": chi2, "df": df, "p": p_value,
            "n_groups": k, "n_features": p, "n": n_total,
            "correction": correction, "groups": names,
        }
        print(f"[box_m] M={m_stat:.6g}, chi2={chi2:.6g}, p={p_value:.6g}")

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
