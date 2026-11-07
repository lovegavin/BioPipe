"""Somers' D ordinal association for a contingency table."""
from __future__ import annotations

from src.task.context import Context
from src.task.step.base import Step

from ._ordinal38_common import contingency, somers_d
from ._stats20_common import scalar_form


class SomersDStep(Step):
    provider = 'operon-core'
    """Somers' D with the row or column variable as dependent."""
    parameters_file = 'somers_d.SomersDStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'somers_d',
     'version': '1.0.0',
     'kind': 'operator',
     'title': "Somers' D",
     'category': 'Statistics',
     'contracts': {'version': 1,
                   'inputs': [{'version': 1,
                               'numeric': True,
                               'info': {},
                               'dims': [{'param': 'row_dim', 'default': 'row'},
                                        {'param': 'column_dim', 'default': 'column'}],
                               'labels': [],
                               'parallel': [],
                               'ndim': 2}],
                   'output': {'mode': 'declare',
                              'schema': {'ndim': 2,
                                         'numeric': True,
                                         'info_open': True,
                                         'axis_info_open': True}}},
     'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'},
     'dependencies': [],
     'dependency_imports': [],
     'inputs_arity': 1,
     'outputs': [],
     'output_parameter': 'output',
     'description': "Somers' D with the row or column variable as dependent."}


    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        row_dim = ctx.step_params.get("row_dim", "row")
        column_dim = ctx.step_params.get("column_dim", "column")
        direction = ctx.step_params.get("direction", "row")
        out_name = ctx.step_params.get("output", self.name)
        counts, rows, columns = contingency(form, row_dim, column_dim, "somers_d")
        value, concordant, discordant, denominator = somers_d(counts, direction)
        total = float(counts.sum())
        out = scalar_form(
            [value, concordant, discordant, denominator, total, float(len(rows)), float(len(columns))],
            ["D", "concordant", "discordant", "comparable_pairs", "n", "n_rows", "n_columns"],
            "somers_d",
        )
        out.info.update({"direction": direction, "row_labels": rows, "column_labels": columns})
        ctx[out_name] = out
        self._export_data = {
            "D": value,
            "concordant": float(concordant),
            "discordant": float(discordant),
            "comparable_pairs": float(denominator),
            "n": int(total),
            "direction": direction,
        }
        print(f"[somers_d] D={value:.6f}, direction={direction}, n={total:.0f}")

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
