"""Shared helpers for the population-genetics extension operators.

Genotype input is a 2D Form ordered as [variant, sample]. Each cell is the
alt allele count of a hard call: an integer in [0, ploidy]; missing calls are
NaN (or the Form's declared ``missing_code``). ``chrom`` and ``pos`` are read
from the variant axis labels or from ``axis_info``.

Window handling follows scikit-allel 1.3.13 so results can be compared value
by value with ``allel.tajima_d``, ``allel.windowed_tajima_d``,
``allel.watterson_theta`` and ``allel.windowed_diversity``.
"""
from __future__ import annotations

import numpy as np

from src.core import StepError

from ._ext_common import axis_labels, make_form, reorder


def _positive_int(value, label: str, name: str) -> int:
    if isinstance(value, bool) or value is None:
        raise StepError(f"{label}: info['{name}'] must be a positive integer")
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise StepError(f"{label}: info['{name}'] must be a positive integer") from None
    if float(value) != number:
        raise StepError(f"{label}: info['{name}'] must be a positive integer")
    if number < 1:
        raise StepError(f"{label}: info['{name}'] must be a positive integer")
    return number


def prepare_genotypes(form, variant_dim: str, sample_dim: str, label: str):
    """Validate a hard-call genotype Form and return ([variant, sample], ploidy)."""
    data = reorder(form, variant_dim, sample_dim)
    representation = form.info.get("representation")
    if representation is not None and str(representation) != "hard_call":
        raise StepError(
            f"{label}: requires hard-call genotypes, got representation={representation!r}; "
            "filter or convert the input first"
        )
    ploidy = _positive_int(form.info.get("ploidy"), label, "ploidy")
    missing = form.info.get("missing_code", np.nan)
    if missing is None:
        missing = np.nan
    try:
        missing_value = float(missing)
    except (TypeError, ValueError):
        raise StepError(f"{label}: info['missing_code'] must be numeric") from None
    values = np.array(data, dtype=np.float64, copy=True)
    invalid = ~np.isfinite(values) if np.isnan(missing_value) else values == missing_value
    present = values[~invalid]
    if present.size:
        if not np.all(present == np.floor(present)):
            raise StepError(f"{label}: alt allele counts must be integers")
        if present.min() < 0 or present.max() > ploidy:
            raise StepError(f"{label}: alt allele counts must be in [0, {ploidy}]")
    values[invalid] = np.nan
    return values, ploidy


def allele_counts(data: np.ndarray, ploidy: int):
    """Return per-variant alt counts and the number of called chromosomes."""
    called = np.isfinite(data)
    alt = np.where(called, data, 0.0).sum(axis=1)
    an = called.sum(axis=1).astype(np.float64) * float(ploidy)
    alt = np.where(an > 0, alt, np.nan)
    return alt, an


def mean_pairwise_difference(alt: np.ndarray, an: np.ndarray) -> np.ndarray:
    """Mean pairwise difference per variant; NaN when there are no pairs."""
    alt = np.asarray(alt, dtype=np.float64)
    an = np.asarray(an, dtype=np.float64)
    pairs = an * (an - 1.0) / 2.0
    same = alt * (alt - 1.0) / 2.0 + (an - alt) * (an - alt - 1.0) / 2.0
    out = np.full(alt.shape, np.nan, dtype=np.float64)
    ok = pairs > 0
    out[ok] = (pairs[ok] - same[ok]) / pairs[ok]
    return out


def tajima_constants(n: int) -> dict:
    """Constants of Tajima's D for ``n`` called chromosomes (n >= 2)."""
    if n < 2:
        raise StepError("tajimas_d requires at least two called chromosomes")
    i = np.arange(1, n, dtype=np.float64)
    a1 = float(np.sum(1.0 / i))
    a2 = float(np.sum(1.0 / (i * i)))
    b1 = (n + 1.0) / (3.0 * (n - 1.0))
    b2 = 2.0 * (n * n + n + 3.0) / (9.0 * n * (n - 1.0))
    c1 = b1 - 1.0 / a1
    c2 = b2 - (n + 2.0) / (a1 * n) + a2 / (a1 * a1)
    return {
        "n": int(n),
        "a1": a1,
        "a2": a2,
        "e1": c1 / a1,
        "e2": c2 / (a1 * a1 + a2),
    }


def positions_chroms(form, variant_dim: str, label: str):
    """Return (pos, chrom) arrays parallel to ``variant_dim``, or None."""
    n = form.data.shape[form.dims.index(variant_dim)]
    pos = form.get_parallel("pos", variant_dim)
    chrom = form.get_parallel("chrom", variant_dim)
    if pos is not None:
        try:
            pos = np.asarray(pos, dtype=np.float64).reshape(-1)
        except (TypeError, ValueError):
            raise StepError(f"{label}: info['pos'] must be numeric") from None
        if pos.size != n:
            raise StepError(f"{label}: info['pos'] has {pos.size} entries for {n} variants")
        if not np.all(np.isfinite(pos)):
            raise StepError(f"{label}: info['pos'] must be finite")
        if np.any(np.diff(pos) < 0):
            raise StepError(f"{label}: info['pos'] must be sorted in ascending order")
    if chrom is not None:
        chrom = np.asarray(chrom).reshape(-1)
        if chrom.size != n:
            raise StepError(f"{label}: info['chrom'] has {chrom.size} entries for {n} variants")
    return pos, chrom


def window_label(chrom, start, end) -> str:
    if chrom is not None:
        return f"{chrom}:{int(start)}-{int(end)}"
    if not np.isfinite(start):
        return "all"
    return f"{int(start)}-{int(end)}"


def windows_for(pos, chrom, n_variants: int, window_size, step_size, label: str) -> list[dict]:
    """Return window records with keys chrom/start/end/index.

    With ``window_size`` None there is one record per chromosome (or one
    record for the whole input when no chromosome is annotated). Otherwise
    windows start at the first position and advance by ``step_size`` until
    the last position, mimicking ``allel.stats.window.position_windows``.
    """
    if chrom is None:
        groups = [(None, np.arange(n_variants, dtype=np.int64))]
    else:
        order: dict[str, list[int]] = {}
        for index, name in enumerate(chrom):
            order.setdefault(str(name), []).append(index)
        groups = [(name, np.asarray(index, dtype=np.int64)) for name, index in order.items()]
    if window_size is None:
        records = []
        for name, index in groups:
            if pos is None:
                start = end = np.nan
            else:
                start, end = float(pos[index][0]), float(pos[index][-1])
            records.append({"chrom": name, "start": start, "end": end, "index": index})
        return records
    if pos is None:
        raise StepError(f"{label}: info['pos'] is required for windowed analysis")
    size = int(window_size)
    step = int(step_size) if step_size is not None else size
    if size < 1 or step < 1:
        raise StepError(f"{label}: window_size and step_size must be positive")
    records = []
    for name, index in groups:
        p = pos[index]
        if p.size == 0:
            continue
        start, stop = int(p[0]), int(p[-1])
        last = False
        for w_start in range(start, stop, step):
            w_stop = w_start + size
            if w_stop >= stop:
                w_stop = stop
                last = True
            else:
                w_stop -= 1
            i0 = int(np.searchsorted(p, w_start))
            i1 = int(np.searchsorted(p, w_stop, side="right"))
            records.append({
                "chrom": name,
                "start": float(w_start),
                "end": float(w_stop),
                "index": index[i0:i1],
            })
            if last:
                break
    return records


def statistic_form(rows, columns: list[str], labels: list[str], info=None):
    """Build the [window, statistic] output Form."""
    if rows:
        data = np.asarray(rows, dtype=np.float32)
    else:
        data = np.zeros((0, len(columns)), dtype=np.float32)
    mapping = {
        "window": axis_labels(labels, "window"),
        "statistic": {name: i for i, name in enumerate(columns)},
    }
    return make_form(data, ["window", "statistic"], mapping, info or {})
