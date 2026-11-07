from __future__ import annotations

import gzip
from pathlib import Path

import numpy as np
from scipy import stats

from src.core.errors import StepError


def _open(path):
    path = Path(path)
    if path.suffix == ".gz":
        return gzip.open(path, "rt")
    return open(path)


def read_vcf(path, max_variants=0):
    samples = None
    variants = []
    dosages = []
    with _open(path) as handle:
        for line in handle:
            if line.startswith("##"):
                continue
            if line.startswith("#CHROM"):
                samples = line.rstrip("\n").split("\t")[9:]
                continue
            fields = line.rstrip("\n").split("\t")
            if len(fields) < 10:
                raise StepError("gwas: VCF has no sample columns")
            chrom, pos, _id, ref, alt = fields[:5]
            if len(ref) != 1 or len(alt) != 1 or ref == alt:
                continue
            row = []
            for value in fields[9:]:
                genotype = value.split(":")[0].replace("|", "/")
                alleles = genotype.split("/")
                if len(alleles) != 2 or "." in alleles:
                    row.append(np.nan)
                else:
                    row.append(float(alleles.count("1")))
            variants.append((chrom, int(pos), ref, alt))
            dosages.append(row)
            if max_variants and len(variants) >= max_variants:
                break
    if samples is None:
        raise StepError("gwas: VCF header is missing")
    return samples, variants, np.asarray(dosages, dtype=float)


def phenotype_from_form(form, row_dim, field_dim, value_field, operator):
    if len(form.dims) != 2:
        raise StepError(f"{operator}: phenotype table must be two-dimensional")
    columns = form.labels.get(field_dim, {})
    if value_field not in columns:
        raise StepError(f"{operator}: phenotype column '{value_field}' is missing")
    samples = form.labels.get(row_dim, {})
    if not samples:
        raise StepError(f"{operator}: phenotype rows are not labelled with samples")
    column = columns[value_field]
    values = form.data[:, column]
    table = {}
    for sample, row in samples.items():
        try:
            table[sample] = float(values[row])
        except (TypeError, ValueError):
            raise StepError(f"{operator}: phenotype values must be numeric")
    return table


def association_rows(form, variant_dim, statistic_dim, operator):
    columns = form.labels.get(statistic_dim, {})
    for required in ("p", "beta", "se"):
        if required not in columns:
            raise StepError(f"{operator}: association column '{required}' is missing")
    variants = form.labels.get(variant_dim, {})
    if not variants:
        raise StepError(f"{operator}: association rows are not labelled with variants")
    rows = []
    for name, index in sorted(variants.items(), key=lambda item: item[1]):
        row = {"variant": name}
        for key in ("p", "beta", "se", "stat", "maf", "n"):
            if key in columns:
                row[key] = float(form.data[index][columns[key]])
        rows.append(row)
    return rows


def read_phenotype(path, value_column, operator):
    with _open(path) as handle:
        header = handle.readline().rstrip("\n").split("\t")
        if value_column not in header:
            raise StepError(f"{operator}: phenotype column '{value_column}' is missing")
        sample_column = 0
        value_index = header.index(value_column)
        table = {}
        for line in handle:
            fields = line.rstrip("\n").split("\t")
            if len(fields) <= value_index:
                continue
            try:
                table[fields[sample_column]] = float(fields[value_index])
            except ValueError:
                raise StepError(f"{operator}: phenotype values must be numeric")
    if not table:
        raise StepError(f"{operator}: phenotype table is empty")
    return table


def align(samples, table, operator):
    missing = [sample for sample in samples if sample not in table]
    if missing:
        raise StepError(
            f"{operator}: phenotype is missing {len(missing)} sample(s), first '{missing[0]}'"
        )
    return np.asarray([table[sample] for sample in samples], dtype=float)


def fit_linear(x, y):
    n = x.size
    design = np.column_stack([np.ones(n), x])
    beta, _, _, _ = np.linalg.lstsq(design, y, rcond=None)
    residual = y - design @ beta
    dof = n - 2
    sigma2 = float(residual @ residual) / dof
    covariance = sigma2 * np.linalg.inv(design.T @ design)
    se = float(np.sqrt(covariance[1, 1]))
    t_stat = float(beta[1] / se) if se > 0 else 0.0
    p_value = float(2.0 * stats.t.sf(abs(t_stat), dof))
    return float(beta[1]), se, t_stat, p_value


def fit_logistic(x, y, iterations=50, tolerance=1e-10):
    n = x.size
    design = np.column_stack([np.ones(n), x])
    beta = np.zeros(2)
    for _ in range(iterations):
        eta = design @ beta
        mu = 1.0 / (1.0 + np.exp(-eta))
        weight = np.clip(mu * (1.0 - mu), 1e-12, None)
        gradient = design.T @ (y - mu)
        hessian = design.T @ (design * weight[:, None])
        step = np.linalg.solve(hessian, gradient)
        beta = beta + step
        if float(np.max(np.abs(step))) < tolerance:
            break
    eta = design @ beta
    mu = 1.0 / (1.0 + np.exp(-eta))
    weight = np.clip(mu * (1.0 - mu), 1e-12, None)
    hessian = design.T @ (design * weight[:, None])
    covariance = np.linalg.inv(hessian)
    se = float(np.sqrt(covariance[1, 1]))
    z_stat = float(beta[1] / se) if se > 0 else 0.0
    p_value = float(2.0 * stats.norm.sf(abs(z_stat)))
    return float(beta[1]), se, z_stat, p_value


def association(samples, variants, dosages, phenotype, model="linear", min_maf=0.0):
    if model not in {"linear", "logistic"}:
        raise StepError(f"gwas: unsupported model '{model}'")
    y = np.asarray([phenotype[sample] for sample in samples], dtype=float)
    if model == "logistic" and not set(np.unique(y)).issubset({0.0, 1.0}):
        raise StepError("gwas: logistic model requires a binary phenotype")
    rows = []
    for index, (chrom, pos, ref, alt) in enumerate(variants):
        x = dosages[index]
        keep = ~np.isnan(x)
        if keep.sum() < 3:
            continue
        frequency = float(x[keep].mean() / 2.0)
        maf = min(frequency, 1.0 - frequency)
        if maf < min_maf or maf == 0.0:
            continue
        if model == "linear":
            beta, se, stat, p_value = fit_linear(x[keep], y[keep])
        else:
            beta, se, stat, p_value = fit_logistic(x[keep], y[keep])
        rows.append(
            {
                "chrom": chrom,
                "pos": pos,
                "ref": ref,
                "alt": alt,
                "beta": beta,
                "se": se,
                "stat": stat,
                "p": p_value,
                "maf": maf,
                "n": int(keep.sum()),
            }
        )
    return rows


def inflation(rows):
    p_values = np.asarray([row["p"] for row in rows], dtype=float)
    p_values = p_values[(p_values > 0.0) & (p_values <= 1.0)]
    if p_values.size == 0:
        raise StepError("gwas_inflation: no usable p-values")
    chi2 = stats.chi2.isf(p_values, 1)
    lam = float(np.median(chi2) / 0.4549364231195726)
    return {
        "n_variants": int(p_values.size),
        "lambda": lam,
        "mean_chi2": float(chi2.mean()),
        "median_p": float(np.median(p_values)),
        "min_p": float(p_values.min()),
    }


def clump(rows, threshold, distance, max_hits):
    ordered = sorted(rows, key=lambda row: row["p"])
    selected = []
    for row in ordered:
        if row["p"] > threshold:
            break
        if any(
            hit["chrom"] == row["chrom"]
            and abs(hit["pos"] - row["pos"]) <= distance
            for hit in selected
        ):
            continue
        selected.append(row)
        if max_hits and len(selected) >= max_hits:
            break
    return selected
