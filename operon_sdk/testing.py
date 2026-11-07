"""Contract-aware helpers for plugin authors' small, deterministic fixtures."""
from pathlib import Path
from tempfile import TemporaryDirectory


def run_operator(cls, inputs, params=None):
    """Run a plugin through real engine contracts, returning its Form/report.

    This helper uses small in-memory fixtures. It does not replace resource,
    performance or scientific correctness testing on representative data.
    """
    from src.task import Context, STEPS, run
    from .declarations import bind_class, for_class
    cls = bind_class(cls, for_class(cls))
    with TemporaryDirectory(prefix="operon-sdk-") as temporary:
        names = [f"input_{i}" for i in range(len(inputs))]
        spec = {"name": cls.name, "inputs": names, "params": dict(params or {})}
        if cls.output_parameter:
            spec['params'].setdefault(cls.output_parameter, cls.name)
        ctx = Context(Path(temporary), {"sources": {}, "steps": [spec]})
        # Preserve lazy factories and descriptor metadata as well as loaded
        # classes. Assigning a class and restoring only the value loses both.
        sentinel = object()
        stores = [getattr(STEPS, attr, None) for attr in ('factories', 'loaded', 'declarations')]
        lazy = all(store is not None for store in stores)
        previous = [store.get(cls.name, sentinel) for store in stores] if lazy else STEPS.get(cls.name, sentinel)
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
            STEPS.pop(cls.name, None)
            if lazy:
                for store, value in zip(stores, previous):
                    if value is not sentinel:
                        store[cls.name] = value
            elif previous is not sentinel:
                STEPS[cls.name] = previous
            ctx.finalize()
