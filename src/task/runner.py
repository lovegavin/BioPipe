# src/task/runner.py
"""Runner — resolves inputs, executes steps in order."""

from __future__ import annotations

import json
import time

from src.core import ContextError, StepError
from src.task.context import Context
from src.task.step import STEPS
from src.core.contracts import (compatible, describe_form, describe_metadata, infer_output,
                                resolve, validate_form, validate_output, validate_values)


def run(ctx: Context, steps: list[dict]) -> None:
    exports = ctx.artifacts["exports"] = []
    ctx._run_status = "running"
    try:
        if ctx.memory:
            ctx.memory.configure(steps, STEPS)
        for i, spec in enumerate(steps, start=1):
            name = spec["name"]
            cls = STEPS.get(name)
            if cls is None:
                raise StepError(f"Unknown step '{name}'. Available: {sorted(STEPS)}")
            step = cls()
            names = spec.get("inputs", [])
            _check_arity(name, step.inputs_arity, names)
            ctx.step_params = dict(spec.get("params", {}))
            if cls.parameters_schema is not None:
                from biopipe_sdk.protocol import validate_parameters
                output = ctx.step_params.pop(cls.output_parameter, None) if cls.output_parameter else None
                ctx.step_params = validate_parameters(cls.parameters_schema, ctx.step_params)
                if output is not None:
                    ctx.step_params[cls.output_parameter] = output
            ctx.step_params["_input_names"] = list(names)
            forms, stream = [], None
            schemas, expected = [], None
            successful = False
            try:
                if ctx.memory:
                    forms, stream = ctx.memory.prepare(i - 1, spec, cls)
                else:
                    forms = [_resolve(ctx, n, name) for n in names]
                requirements = [resolve(rule, ctx.step_params) for rule in (cls.input_contracts or [])]
                schemas = []
                if stream is not None:
                    schema = describe_metadata(stream["metadata"], stream["shape"])
                    required = requirements[0] if requirements else None
                    result = compatible(schema, required)
                    if required is not None and result["status"] != "compatible":
                        raise StepError(f"{name} input 1 contract: " + "; ".join(result["reasons"]))
                    original_chunks = stream["chunks"]
                    def checked_chunks(chunks=original_chunks, requirement=required, metadata=stream["metadata"]):
                        try:
                            for chunk in chunks:
                                validate_values(chunk, metadata["info"], requirement, f"{name} input 1")
                                yield chunk
                        finally:
                            chunks.close()
                    stream["chunks"] = checked_chunks()
                    schemas.append(schema)
                else:
                    for port, form in enumerate(forms):
                        required = requirements[min(port, len(requirements) - 1)] if requirements else None
                        validate_form(form, required, f"{name} input {port + 1} ({names[port]})")
                        schemas.append(describe_form(form))
                expected = infer_output(cls.output_contract, schemas, ctx.step_params)
                declared_outputs = list(step.outputs)
                if cls.output_parameter:
                    declared_outputs.append(str(ctx.step_params.get(cls.output_parameter, name)))
                ctx.written_outputs.clear()
                def check_output(key, form):
                    if cls.output_contract and cls.output_contract.get("mode") in {"report", "none"}:
                        raise StepError(f"{name} contract: report operator cannot register a Form")
                    if declared_outputs and key not in declared_outputs:
                        raise StepError(f"{name} contract: undeclared output {key}")
                    if cls.output_contract:
                        validate_output(form, expected, f"{name} output {key}")
                ctx.output_validator = check_output
                start = time.perf_counter()
                if stream is not None:
                    step.run_stream(ctx, stream)
                else:
                    step.run(ctx, forms)
                elapsed = time.perf_counter() - start
                for output in declared_outputs:
                    if output not in ctx.written_outputs:
                        raise StepError(f"Step '{name}' declared output '{output}' but did not register it")
                content = step.export(ctx)
                prefix = f"runs/{ctx.memory.run_id}/" if ctx.memory else ""
                relative = f"{prefix}steps/{i:02d}_{name}.json"
                path = ctx.out_dir / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                with open(path, "w", encoding="utf-8") as file:
                    json.dump(content, file, indent=2, ensure_ascii=False)
                exports.append({"index": i, "name": name, "elapsed": round(elapsed, 4),
                                "inputs": list(names), "params": spec.get("params", {}),
                                "export_path": relative})
                ctx.metadata.setdefault("steps", []).append({"name": name, "elapsed": elapsed})
                if ctx.memory:
                    ctx.memory.event("contract_checked", name=name, inputs=len(names), outputs=declared_outputs, contract_version=1)
                successful = True
                print(f"[{i}/{len(steps)}] {name} done in {elapsed:.3f}s")
            finally:
                ctx.output_validator = None
                schemas.clear()
                expected = None
                if stream is not None:
                    stream["chunks"].close()
                forms.clear()
                stream = None
                del step
                if "content" in locals():
                    del content
                if ctx.memory:
                    if successful:
                        ctx.memory.finish(spec, elapsed)
                    else:
                        ctx.memory.abort_step()
        ctx._run_status = "complete"
    except BaseException as exc:
        ctx._run_status, ctx._run_error = "failed", exc
        raise


def _check_arity(name: str, arity, form_names: list[str]) -> None:
    if arity == "*":
        if not form_names:
            raise StepError(
                f"Step '{name}' accepts any number of inputs but got none"
            )
        return
    if len(form_names) != arity:
        raise StepError(
            f"Step '{name}' expects {arity} inputs, got {len(form_names)}"
        )


def _resolve(ctx: Context, name: str, step_name: str):
    if not ctx.has(name):
        raise ContextError(
            f"Step '{step_name}' requires form '{name}', which is not "
            f"in context. Available: {sorted(ctx.forms)}"
        )
    return ctx[name]
