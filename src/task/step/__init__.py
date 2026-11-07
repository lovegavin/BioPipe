"""Descriptor-backed lazy Step registry; provider code loads on first lookup."""
import os
from operon.lazy import LazyRegistry
from src.task.step.base import Step
STEPS = LazyRegistry()
if os.getenv("OPERON_REGISTRY_MAINTENANCE") != "1":
    from operon.packages import bundled_entries, load_entry
    from operon.environments import proxy_step

    def _load(descriptor):
        environment = (descriptor.get("resources") or {}).get("environment")
        if environment:
            from operon.environments import resolve
            if resolve(environment) is not None:
                return proxy_step(descriptor)
        return load_entry(descriptor)

    for _, descriptor in bundled_entries("operator"):
        STEPS.register(descriptor["id"], lambda d=descriptor: _load(d), descriptor)
__all__ = ["STEPS", "Step"]
