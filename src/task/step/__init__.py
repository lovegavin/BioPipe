"""Descriptor-backed lazy Step registry; provider code loads on first lookup."""
import os
from biopipe.lazy import LazyRegistry
from src.task.step.base import Step
STEPS = LazyRegistry()
if os.getenv("BIOPIPE_REGISTRY_MAINTENANCE") != "1":
    from biopipe.packages import bundled_entries, load_entry
    from biopipe.environments import proxy_step

    def _load(descriptor):
        if (descriptor.get("resources") or {}).get("environment"):
            return proxy_step(descriptor)
        return load_entry(descriptor)

    for _, descriptor in bundled_entries("operator"):
        STEPS.register(descriptor["id"], lambda d=descriptor: _load(d), descriptor)
__all__ = ["STEPS", "Step"]
