"""Contract-aware helpers for plugin authors' small, deterministic fixtures."""
from pathlib import Path
from tempfile import TemporaryDirectory


def run_operator(cls, inputs, params=None):
    """Run a plugin through real engine contracts, returning its Form/report.

    This helper uses small in-memory fixtures. It does not replace resource,
    performance or scientific correctness testing on representative data.
    """
    from src.task import Context, STEPS, run
    with TemporaryDirectory(prefix="biopipe-sdk-") as temporary:
        names = [f"input_{i}" for i in range(len(inputs))]
        spec = {"name": cls.name, "inputs": names, "params": dict(params or {})}
        ctx = Context(Path(temporary), {"sources": {}, "steps": [spec]})
        previous = STEPS.get(cls.name)
        STEPS[cls.name] = cls
        try:
            for name, form in zip(names, inputs):
                ctx[name] = form
            run(ctx, [spec])
            if cls.output_parameter:
                return ctx[spec["params"].get(cls.output_parameter, cls.name)]
            import json
            return json.loads((ctx.out_dir / ctx.artifacts["exports"][0]["export_path"]).read_text(encoding="utf-8"))
        finally:
            if previous is None:
                STEPS.pop(cls.name, None)
            else:
                STEPS[cls.name] = previous
            ctx.finalize()
