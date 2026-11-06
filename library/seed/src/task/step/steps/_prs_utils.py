"""Shared helpers for polygenic-score harmonisation and pruning."""
from __future__ import annotations

import gzip
from pathlib import Path

import numpy as np

from src.core import StepError

_MISSING_IDS = {"", ".", "NA", "N/A"}


def open_text(path):
    text = str(path)
    if text.endswith(".gz"):
        return gzip.open(text, "rt", encoding="utf-8", errors="replace")
    return open(text, "rt", encoding="utf-8", errors="replace")


def _alt_index(gt: str) -> int:
    return gt.replace("|", "/").count("1")


def vcf_variants(path, max_records: int = 0):
    """Return (samples, records) for a VCF, keeping REF/ALT and raw GT text."""
    samples = []
    records = []
    with open_text(path) as handle:
        for line in handle:
            if line.startswith("##"):
                continue
            if line.startswith("#CHROM"):
                columns = line.rstrip("\n").split("\t")
                samples = columns[9:]
                continue
            fields = line.rstrip("\n").split("\t")
            if len(fields) < 10:
                continue
            chrom = fields[0]
            try:
                pos = int(fields[1])
            except ValueError:
                continue
            alts = [item.strip().upper() for item in fields[4].split(",") if item.strip()]
            if not alts:
                continue
            records.append(
                {
                    "chrom": chrom,
                    "pos": pos,
                    "vid": fields[2].strip(),
                    "ref": fields[3].strip().upper(),
                    "alts": alts,
                    "gt": fields[9:],
                }
            )
            if max_records and len(records) >= max_records:
                break
    if not records:
        raise StepError("prs: no variants found in the genotype VCF")
    return samples, records


def variant_label(record) -> str:
    """Match the typed VcfReader label rule for these records."""
    vid = record["vid"]
    alts = record["alts"]
    if vid not in _MISSING_IDS and len(alts) == 1:
        return vid
    return f"{record['chrom']}:{record['pos']}:{alts[0]}"


def read_pgs_weights(path):
    """Read a PGS Catalog scoring file (v2 column names, ``#`` comments)."""
    header = None
    weights = []
    with open_text(path) as handle:
        for line in handle:
            if not line.strip() or line.startswith("#"):
                continue
            fields = line.rstrip("\n").split("\t")
            if header is None:
                lower = [item.strip().lower() for item in fields]
                if "effect_weight" in lower:
                    header = lower
                    continue
                header = []
            if not header:
                if len(fields) < 6:
                    continue
                record = {
                    "rsid": fields[0].strip(),
                    "chrom": fields[1].strip(),
                    "pos": int(fields[2]),
                    "effect": fields[3].strip().upper(),
                    "other": fields[4].strip().upper(),
                    "weight": float(fields[5]),
                }
            else:
                row = dict(zip(header, fields))
                try:
                    record = {
                        "rsid": row.get("rsid", "").strip(),
                        "chrom": row.get("chr_name", "").strip(),
                        "pos": int(row.get("chr_position", "0")),
                        "effect": row.get("effect_allele", "").strip().upper(),
                        "other": row.get("other_allele", "").strip().upper(),
                        "weight": float(row.get("effect_weight", "nan")),
                    }
                except (TypeError, ValueError):
                    continue
            if not record["effect"] or not np.isfinite(record["weight"]):
                continue
            weights.append(record)
    if not weights:
        raise StepError("prs: no usable weights in the score file")
    return weights


def harmonize(records, weights):
    """Match weights to VCF records and orient them to the ALT allele."""
    by_id = {}
    by_pos = {}
    duplicated = 0
    for record in records:
        label = variant_label(record)
        if label in by_pos:
            duplicated += 1
            continue
        by_pos[label] = record
        if record["vid"] not in _MISSING_IDS:
            by_id.setdefault(record["vid"], record)

    counts = {"matched": 0, "flipped": 0, "ambiguous": 0, "absent": 0, "multiallelic": 0}
    entries = []
    for weight in weights:
        record = None
        if weight["rsid"] not in _MISSING_IDS:
            record = by_id.get(weight["rsid"])
        if record is None:
            record = next(
                (
                    item
                    for item in records
                    if item["chrom"] == weight["chrom"] and item["pos"] == weight["pos"]
                ),
                None,
            )
        if record is None:
            counts["absent"] += 1
            continue
        if len(record["alts"]) != 1:
            counts["multiallelic"] += 1
            continue
        alt = record["alts"][0]
        effect = weight["effect"]
        if effect == alt:
            counts["matched"] += 1
            beta = weight["weight"]
        elif effect == record["ref"]:
            counts["flipped"] += 1
            beta = -weight["weight"]
        else:
            counts["ambiguous"] += 1
            continue
        entries.append({"label": variant_label(record), "weight": float(beta), "record": record})
    return entries, counts, duplicated


def dosages(record):
    values = []
    for gt in record["gt"]:
        if not gt or gt == ".":
            values.append(np.nan)
            continue
        alleles = gt.replace("|", "/").split("/")
        if any(item in (".", "") for item in alleles):
            values.append(np.nan)
            continue
        try:
            values.append(float(sum(1 for item in alleles if item == "1")))
        except ValueError:
            values.append(np.nan)
    return np.asarray(values, dtype=float)


def allele_frequency(values):
    finite = values[np.isfinite(values)]
    if finite.size == 0:
        return 0.0
    return float(finite.mean() / 2.0)


def r2_between(a, b):
    mask = np.isfinite(a) & np.isfinite(b)
    if mask.sum() < 3:
        return 0.0
    x = a[mask]
    y = b[mask]
    if x.std() == 0 or y.std() == 0:
        return 0.0
    corr = float(np.corrcoef(x, y)[0, 1])
    return min(1.0, corr * corr)
