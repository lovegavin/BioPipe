# src/pipelines/gwas/steps/assoc.py
"""AssocStep — per-variant association testing."""

from __future__ import annotations

import numpy as np
import pandas as pd
import statsmodels.api as sm

from src.core.forms import ResultTable
from src.orchestration.context import PipelineContext
from src.orchestration.step import Step
from src.pipelines.gwas.models import fit_firth, fit_logit, fit_ols


class AssocStep(Step):
    """Fit OLS (continuous) or Firth / Logit (binary) per variant.

    Produces the ``association`` form: a ResultTable indexed by variant
    ID with columns BETA, SE, P, N, MAF and the variant metadata.
    """

    name = "assoc"
    consumes = ("genotype", "phenotype")
    produces = ("association",)

    def run(self, ctx: PipelineContext) -> None:
        genotype = ctx.get("genotype")
        phenotype = ctx.get("phenotype")
        covariates = ctx.forms.get("covariates")

        y = phenotype.data.iloc[:, 0].to_numpy().astype(float)
        data = genotype.data
        missing_code = genotype.missing_code

        binary = len(np.unique(y)) == 2
        model_name = ctx.config["association"].get("binary_model", "firth")

        if covariates is not None:
            cov = covariates.data.to_numpy().astype(float)
            if np.isnan(cov).any():
                raise ValueError(
                    "Covariates contain missing values. Clean them first."
                )
        else:
            cov = None

        n_snps = genotype.n_snps
        rows = np.full((n_snps, 4), np.nan, dtype=float)  # BETA, SE, P, N

        for i in range(n_snps):
            g = data[i]
            valid = g != missing_code
            n_valid = int(valid.sum())
            rows[i, 3] = n_valid

            if n_valid < 3:
                continue

            X = g[valid][:, None]
            if cov is not None:
                X = np.hstack([X, cov[valid]])
            X = sm.add_constant(X, has_constant="add")
            y_sub = y[valid]

            if binary and len(np.unique(y_sub)) < 2:
                continue

            if not binary:
                res = fit_ols(y_sub, X)
            elif model_name == "firth":
                firth_res = fit_firth(y_sub, X)
                res = None
                if firth_res is not None:
                    beta_arr, se_arr, p_arr = firth_res
                    res = (
                        float(beta_arr[1]),
                        float(se_arr[1]),
                        float(p_arr[1]),
                    )
            else:
                res = fit_logit(y_sub, X)

            if res is not None:
                rows[i, 0], rows[i, 1], rows[i, 2] = res

        # Assemble the result frame. Variant metadata joins on variant ID.
        stats_df = pd.DataFrame(
            rows,
            columns=["BETA", "SE", "P", "N"],
            index=pd.Index(genotype.variant_ids, name="ID"),
        )
        stats_df.insert(0, "MAF", ctx.artifacts["maf"])

        variant_meta = ctx.get("variant_table").data
        result_df = variant_meta.join(stats_df, how="right")

        ctx.put(
            "association",
            ResultTable(
                data=result_df,
                id_column="ID",
                id_kind="variant",
                source_format="derived",
            ),
        )

        n_ok = int(result_df["P"].notna().sum())
        print(
            f"[assoc] {n_ok} / {n_snps} variants tested "
            f"({'binary:' + model_name if binary else 'continuous:ols'})"
        )