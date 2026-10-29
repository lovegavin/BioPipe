"""Elastic-net penalised linear regression."""
from __future__ import annotations

from ._ml_common import _RegressionBase


class ElasticNetRegressorStep(_RegressionBase):
    name = "elastic_net_regressor"
    title = "Elastic net regressor"
    extra_properties = {
        "alpha": {"type": "number", "exclusiveMinimum": 0, "default": 1.0},
        "l1_ratio": {"type": "number", "minimum": 0, "maximum": 1, "default": 0.5},
        "max_iter": {"type": "integer", "minimum": 1, "default": 1000},
    }

    def _build_model(self, params, random_state):
        from sklearn.linear_model import ElasticNet
        return ElasticNet(
            alpha=float(params.get("alpha", 1.0)),
            l1_ratio=float(params.get("l1_ratio", 0.5)),
            max_iter=int(params.get("max_iter", 1000)),
            random_state=random_state,
        )
