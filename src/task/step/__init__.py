# src/task/step/__init__.py
"""Step router.

Loads the bundled package index into a name -> class map. Source scanning
is retained solely for the package-index maintenance command.
"""

from __future__ import annotations

import importlib
import os
import pkgutil

from src.core import StepError
from src.task.step import steps as _steps_pkg
from src.task.step.base import Step


def _discover() -> dict[str, type[Step]]:
    registry: dict[str, type[Step]] = {}
    for _, mod_name, is_pkg in pkgutil.iter_modules(_steps_pkg.__path__):
        if is_pkg:
            continue
        mod = importlib.import_module(f"src.task.step.steps.{mod_name}")
        for attr in vars(mod).values():
            if (
                isinstance(attr, type)
                and issubclass(attr, Step)
                and attr is not Step
                and attr.name != "unnamed"
            ):
                if attr.name in registry and registry[attr.name] is not attr:
                    raise StepError(
                        f"Duplicate step name '{attr.name}' "
                        f"in module '{mod_name}'"
                    )
                registry[attr.name] = attr
    return registry


def _from_packages():
    from biopipe.packages import bundled_entries, load_entry
    return {descriptor["id"]: load_entry(descriptor)
            for _, descriptor in bundled_entries("operator")}


STEPS: dict[str, type[Step]] = {} if os.getenv("BIOPIPE_REGISTRY_MAINTENANCE") == "1" else _from_packages()


__all__ = ["STEPS", "Step"]
