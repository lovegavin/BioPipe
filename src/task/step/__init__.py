"""Descriptor-backed lazy Step registry; provider code loads on first lookup."""
import os
from biopipe.lazy import LazyRegistry
from src.task.step.base import Step
STEPS = LazyRegistry()
if os.getenv("BIOPIPE_REGISTRY_MAINTENANCE") != "1":
    from biopipe.packages import bundled_entries, load_entry
    for _, descriptor in bundled_entries("operator"):
        STEPS.register(descriptor["id"], lambda d=descriptor: load_entry(d))
__all__ = ["STEPS", "Step"]
