"""Multinomial logistic regression for a nominal response."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step

from ._stats21_common import design_matrix, numeric_column, table_frame


class MultinomialLogitStep(Step):
    provider = 'operon-core'
    """Maximum-likelihood multinomial logit with the first level as reference."""
    parameters_file = 'multinomial_logit.MultinomialLogitStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'multinomial_logit',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'Multinomial logistic regression',
     'category': 'Statistics',
     'contracts': {'version': 1,
                   'inputs': [{'version': 1,
                               'numeric': True,
                               'info': {},
                               'dims': [{'param': 'sample_dim', 'default': 'sample'},
                                        {'param': 'feature_dim', 'default': 'feature'}],
                               'labels': [],
                               'parallel': [],
                               'ndim': 2}],
                   'output': {'mode': 'declare',
                              'schema': {'ndim': 2,
                                         'numeric': True,
                                         'info_open': True,
                                         'axis_info_open': True}}},
     'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'},
     'dependencies': ['statsmodels>=0.14'],
     'dependency_imports': ['statsmodels'],
     'inputs_arity': 1,
     'outputs': [],
     'output_parameter': 'output',
     'description': 'Maximum-likelihood multinomial logit with the first level as reference.'}


    def run(self, ctx: Context, inputs) -> None:
        import statsmodels.api as sm

        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        response_label = ctx.step_params["response_label"]
        predictors = list(ctx.step_params["predictors"])
        categorical = list(ctx.step_params.get("categorical", []))
        missing = [name for name in categorical if name not in predictors]
        if missing:
            raise StepError(
                f"{self.name}: categorical names not in predictors: {missing}"
            )
        frame = table_frame(inputs[0], sample_dim, feature_dim, self.name)
        if response_label not in frame.columns:
            raise StepError(f"{self.name}: response {response_label!r} not found")
        for name in predictors:
            if name not in frame.columns:
                raise StepError(f"{self.name}: predictor {name!r} not found")

        valid = frame[response_label].notna().to_numpy()
        for name in predictors:
            if name in categorical:
                valid &= frame[name].notna().to_numpy()
            else:
                valid &= np.isfinite(numeric_column(frame, name, self.name))
        frame = frame.loc[valid].reset_index(drop=True)
        if len(frame) < 5:
            raise StepError(f"{self.name}: fewer than five complete rows")

        levels = sorted({str(value) for value in frame[response_label].tolist()})
        if len(levels) < 2:
            raise StepError(f"{self.name}: response needs at least two levels")
        counts = frame[response_label].astype(str).value_counts()
        if any(int(counts[level]) < 2 for level in levels):
            raise StepError(f"{self.name}: every response level needs at least two rows")
        mapping = {level: i for i, level in enumerate(levels)}
        y = np.asarray(
            [mapping[str(value)] for value in frame[response_label].tolist()],
            dtype=np.int64,
        )
        design, terms = design_matrix(frame, predictors, categorical, self.name)
        if len(y) <= design.shape[1] + len(levels):
            raise StepError(f"{self.name}: not enough observations for the model")
        maxiter = int(ctx.step_params.get("maxiter", 200))
        try:
            result = sm.MNLogit(y, design).fit(disp=False, maxiter=maxiter)
        except Exception as exc:
            raise StepError(f"{self.name}: fit failed: {exc}") from exc

        params = np.asarray(result.params, dtype=np.float64)
        bse = np.asarray(result.bse, dtype=np.float64)
        pvalues = np.asarray(result.pvalues, dtype=np.float64)
        conf = np.asarray(result.conf_int(), dtype=np.float64)
        outcomes = levels[1:]
        rows = []
        row_labels = []
        for j, outcome in enumerate(outcomes):
            for i, term in enumerate(terms):
                coef = float(params[i, j])
                se = float(bse[i, j])
                z = coef / se if np.isfinite(se) and se > 0 else float("nan")
                low, high = float(conf[j, i, 0]), float(conf[j, i, 1])
                rows.append(
                    [
                        coef,
                        se,
                        z,
                        float(pvalues[i, j]),
                        low,
                        high,
                        float(np.exp(coef)),
                        float(np.exp(low)),
                        float(np.exp(high)),
                    ]
                )
                row_labels.append(f"{term}|{outcome}")

        block = np.asarray(rows, dtype=np.float32)
        ctx[ctx.step_params.get("output", self.name)] = Form(
            data=block,
            dims=["row", "statistic"],
            labels={
                "row": {name: i for i, name in enumerate(row_labels)},
                "statistic": {
                    "coef": 0,
                    "se": 1,
                    "z": 2,
                    "P": 3,
                    "CI_low": 4,
                    "CI_high": 5,
                    "exp_coef": 6,
                    "exp_CI_low": 7,
                    "exp_CI_high": 8,
                },
            },
            info={
                "method": "multinomial logit",
                "reference": levels[0],
                "levels": levels,
                "n": int(len(y)),
                "llf": float(result.llf),
                "aic": float(result.aic),
            },
        )
        self._export = {
            "terms": terms,
            "levels": levels,
            "reference": levels[0],
            "coef": params.tolist(),
            "se": bse.tolist(),
            "p": pvalues.tolist(),
            "llf": float(result.llf),
            "aic": float(result.aic),
            "n": int(len(y)),
        }
        print(f"[{self.name}] n={len(y)}, levels={len(levels)}")

    def export(self, ctx: Context) -> dict:
        return self._export
