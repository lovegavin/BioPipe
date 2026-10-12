"""Small function-oriented operator API layered over the compatible Step API."""
from abc import abstractmethod
from src.task.step.base import Step
from src.core import Form, StepError


class Operator(Step):
    """Implement compute(inputs, params, context) and return one Form or a report.

    Set output_parameter=None and output_contract={"mode": "report"} for a
    report-only operator. Use Step directly for legacy multi-output behavior.
    """
    inputs_arity = 1
    output_parameter = "output"
    parameters_schema = {"type": "object", "properties": {}, "additionalProperties": False}

    @abstractmethod
    def compute(self, inputs, params, context):
        """Return a new Form, or a JSON-compatible report for report operators."""

    def run(self, ctx, inputs):
        params = {key: value for key, value in ctx.step_params.items() if key not in ("output", "_input_names")}
        result = self.compute(inputs, params, ctx)
        if self.output_parameter:
            if not isinstance(result, Form):
                raise StepError(f"{self.name}: compute() must return a Form")
            ctx[str(ctx.step_params.get(self.output_parameter, self.name))] = result
            self._report = {"shape": list(result.data.shape), "dims": result.dims}
        else:
            self._report = result or {}

    def export(self, ctx):
        return self._report
