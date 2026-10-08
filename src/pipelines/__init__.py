# src/pipelines/__init__.py
"""Pipeline registry.

Each entry maps a pipeline name to a plugin object exposing four
attributes:

* ``manifest``       — module with ``default_manifest()`` and
                       ``validate_manifest()``.
* ``init``           — module with ``init_from_input_dir()``.
* ``pipeline``       — module that contains the pipeline class.
* ``pipeline_class`` — the pipeline class itself. ``scripts/run.py``
                       instantiates it; the script never imports a
                       concrete pipeline directly.

To register a new pipeline, add an adapter class following the
``_GwasPlugin`` pattern below and add it to ``PIPELINES``.
"""

from src.pipelines import gwas
from src.pipelines.gwas import manifest as gwas_manifest
from src.pipelines.gwas import init as gwas_init
from src.pipelines.gwas import pipeline as gwas_pipeline
from src.pipelines.gwas.pipeline import GwasPipeline


class _GwasPlugin:
    """Adapter exposing the plugin interface for the GWAS pipeline."""

    manifest = gwas_manifest
    init = gwas_init
    pipeline = gwas_pipeline
    pipeline_class = GwasPipeline


PIPELINES = {
    "gwas": _GwasPlugin(),
    # Future: "prs": _PrsPlugin(), ...
}

__all__ = ["PIPELINES"]