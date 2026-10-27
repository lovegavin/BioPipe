"""Protocol-level SOP checks for report/plot operators.

Plot operators have no numeric contract. Their SOP is: report mode,
no Form registration, strict parameter schema, titled fields, and a
working artifact path through the route/demo suite.
"""
from __future__ import annotations

from src.task import STEPS
from src.task.operator_catalog import build_catalog

PLOTS = {
    "barplot", "boxplot", "dotplot", "enrichment_plot", "forest_plot",
    "heatmap", "histogram", "kaplan_meier", "line", "ma_plot",
    "manhattan", "scatter", "violin", "volcano",
}


def test_all_plot_operators_are_report_only_and_strict():
    catalog = build_catalog(STEPS)
    operators = {item["name"]: item for item in catalog["operators"]}
    for name in sorted(PLOTS):
        operator = operators[name]
        assert operator["contracts"]["output"]["mode"] in ("report", "none"), name
        assert operator["output_parameter"] is None, name
        schema = operator["parameters_schema"]
        assert schema["additionalProperties"] is False, name
        for key, field in schema.get("properties", {}).items():
            assert field.get("title"), f"{name}.{key} has no title"


def test_plot_operators_are_not_form_steps():
    for name in PLOTS:
        assert STEPS[name].output_parameter is None
        assert not STEPS[name].outputs
