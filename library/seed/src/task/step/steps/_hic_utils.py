"""Helpers for pair-level Hi-C quality control and contact binning."""
from __future__ import annotations

import gzip
from pathlib import Path

import numpy as np

from src.core import StepError


def open_text(path):
    path = Path(path)
    if path.name.endswith(".gz"):
        return gzip.open(path, "rt")
    return path.open("r", encoding="utf-8")


def read_chrom_sizes(path):
    sizes = {}
    with open_text(path) as handle:
        for line in handle:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            fields = line.split()
            if len(fields) < 2:
                raise StepError(f"chrom sizes: malformed line {line!r}")
            name, length = fields[0], fields[1]
            try:
                length = int(length)
            except ValueError as exc:
                raise StepError(f"chrom sizes: invalid length in {line!r}") from exc
            if length <= 0:
                raise StepError(f"chrom sizes: non-positive length for {name}")
            sizes[name] = length
    if not sizes:
        raise StepError("chrom sizes: no entries found")
    return sizes


def iter_pairs(path, max_pairs=0):
    seen = 0
    with open_text(path) as handle:
        for line in handle:
            if line.startswith("#"):
                continue
            fields = line.split()
            if len(fields) < 6:
                continue
            chrom1, pos1, _strand1, chrom2, pos2, _strand2 = fields[:6]
            try:
                pos1, pos2 = int(pos1), int(pos2)
            except ValueError:
                continue
            seen += 1
            yield chrom1, pos1, chrom2, pos2
            if max_pairs and seen >= max_pairs:
                return


def pair_statistics(path, max_pairs=0):
    total = cis = trans = 0
    distances = []
    per_chrom = {}
    for chrom1, pos1, chrom2, pos2 in iter_pairs(path, max_pairs):
        total += 1
        if chrom1 == chrom2:
            cis += 1
            per_chrom[chrom1] = per_chrom.get(chrom1, 0) + 1
            distances.append(abs(pos2 - pos1))
        else:
            trans += 1
    if total == 0:
        raise StepError("hic_pair_stats: no pairs found")
    return {
        "total": total,
        "cis": cis,
        "trans": trans,
        "cis_fraction": cis / total,
        "chromosomes": len(per_chrom),
        "mean_cis_distance": float(np.mean(distances)) if distances else 0.0,
        "per_chrom": per_chrom,
    }


def bin_contacts(path, sizes, resolution, chromosome="", include_trans=False, max_pairs=0):
    if resolution <= 0:
        raise StepError("hic_contact_matrix: resolution must be positive")
    counter = {}
    used = 0
    for chrom1, pos1, chrom2, pos2 in iter_pairs(path, max_pairs):
        if chrom1 not in sizes or chrom2 not in sizes:
            continue
        if chrom1 != chrom2 and not include_trans:
            continue
        if chromosome and chrom1 != chromosome and (not include_trans or chrom2 != chromosome):
            continue
        b1 = pos1 // resolution
        b2 = pos2 // resolution
        if chrom1 == chrom2:
            if b1 > b2:
                b1, b2 = b2, b1
            if b1 == b2 and pos1 == pos2:
                continue
        key = (chrom1, b1, chrom2, b2)
        counter[key] = counter.get(key, 0) + 1
        used += 1
    rows = []
    for (c1, b1, c2, b2), count in counter.items():
        label = c1 if c1 == c2 else f"{c1}|{c2}"
        rows.append((label, b1 * resolution, b2 * resolution, count))
    rows.sort(key=lambda row: (row[0], row[1], row[2]))
    return rows, used


def decay_table(rows, n_bins=20, max_distance=0):
    distances = []
    counts = []
    for _label, start1, start2, count in rows:
        distance = abs(start2 - start1)
        if distance > 0:
            distances.append(distance)
            counts.append(int(count))
    if not distances:
        raise StepError("hic_distance_decay: no contacts at non-zero distance")
    distances = np.asarray(distances, dtype=np.float64)
    counts = np.asarray(counts, dtype=np.float64)
    upper = float(max_distance) if max_distance else float(distances.max())
    upper = max(upper, float(distances.min()) + 1.0)
    edges = np.geomspace(max(1.0, float(distances.min())), upper, n_bins + 1)
    table = []
    grand = float(counts.sum())
    for index in range(n_bins):
        lo, hi = float(edges[index]), float(edges[index + 1])
        mask = (distances >= lo) & (distances < hi) if index < n_bins - 1 else (distances >= lo) & (distances <= hi)
        n_contacts = int(mask.sum())
        n_pairs = int(counts[mask].sum())
        mean_count = n_pairs / n_contacts if n_contacts else 0.0
        table.append((f"{lo:.0f}-{hi:.0f}", lo, hi, n_contacts, n_pairs, mean_count, n_pairs / grand))
    return table, int(grand)
