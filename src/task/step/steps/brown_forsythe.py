"""Brown-Forsythe test for equality of variances across groups."""
from __future__ import annotations

from src.task.context import Context

from .levene_test import LeveneTestStep


class BrownForsytheStep(LeveneTestStep):
    """Median-centered Levene test, known as the Brown-Forsythe test."""

    name = "brown_forsythe"
    title = "Brown-Forsythe variance test"
    test_label = "Brown-Forsythe"
    parameters_schema = {
        "type": "object",
        "properties": {
            "feature_dim": {"type": "string", "default": "feature"},
            "sample_dim": {"type": "string", "default": "sample"},
            "group_dim": {"type": "string", "default": "sample"},
            "group_label": {"type": "string"},
            "output": {"type": "string"},
        },
        "required": ["group_label"],
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        self._run_variance(ctx, inputs, "median")
