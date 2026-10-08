# src/pipelines/__init__.py
"""Pipeline registry.

Each entry maps a pipeline name to an object exposing ``manifest``,
``init`` and ``pipeline`` attributes. ``scripts/run.py`` and
``scripts/init_task.py`` consume this registry and never import
pipelines directly.
"""

from src.pipelines import gwas
from src.pipelines.gwas import manifest as gwas_manifest
from src.pipelines.gwas import init as gwas_init
from src.pipelines.gwas import pipeline as gwas_pipeline


class _GwasPlugin:
    """Adapter exposing the three plugin interface points."""

    manifest = gwas_manifest
    init = gwas_init
    pipeline = gwas_pipeline


PIPELINES = {
    "gwas": _GwasPlugin(),
    # Future: "prs": _PrsPlugin(), ...
}

__all__ = ["PIPELINES"]