# src/pipelines/gwas/models/__init__.py
"""Statistical association models."""

from src.pipelines.gwas.models.ols import fit_ols
from src.pipelines.gwas.models.firth import fit_firth
from src.pipelines.gwas.models.logit import fit_logit

__all__ = ["fit_ols", "fit_firth", "fit_logit"]