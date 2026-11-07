"""Helpers for pairwise genome alignment statistics and synteny blocks."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from src.core import StepError

from ._annotation_utils import fasta_sequences

DEFAULT_PRESET = "asm5"
DEFAULT_MIN_BLOCK = 1000


def resolve_binary(binary: str, operator: str) -> str:
    path = shutil.which(binary)
    if not path:
        raise StepError(f"{operator}: required executable {binary!r} is not available")
    return path


def write_fasta(form, sequence_dim: str, position_dim: str, path: Path, operator: str) -> list[tuple[str, int]]:
    names, sequences = fasta_sequences(form, sequence_dim, position_dim, operator)
    entries = []
    lines = []
    for index, (name, sequence) in enumerate(zip(names, sequences)):
        label = name or f"sequence_{index + 1}"
        entries.append((label, len(sequence)))
        lines.append(f">{label}\n")
        for start in range(0, len(sequence), 60):
            lines.append(sequence[start:start + 60] + "\n")
    path.write_text("".join(lines), encoding="utf-8")
    return entries


def _tag(record: dict, name: str):
    for key, value in record["tags"].items():
        if key == name:
            return value
    return None


def run_minimap2(
    query: Path,
    reference: Path,
    preset: str = DEFAULT_PRESET,
    threads: int = 1,
    timeout: int = 1800,
    binary: str = "minimap2",
) -> list[dict]:
    executable = resolve_binary(binary, "genome_alignment")
    command = [executable, "-x", preset, "--no-long-join", "-c", "--cs", "-t", str(max(int(threads), 1)), str(reference), str(query)]
    try:
        completed = subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired as error:
        raise StepError(f"minimap2 did not finish within {timeout} seconds") from error
    if completed.returncode != 0:
        detail = (completed.stderr or "").strip().splitlines()
        raise StepError(f"minimap2 failed: {detail[-1] if detail else completed.returncode}")
    records = []
    for line in completed.stdout.splitlines():
        if not line or line.startswith("#"):
            continue
        fields = line.split("\t")
        if len(fields) < 12:
            continue
        tags = {}
        for item in fields[12:]:
            if ":" in item:
                key, _, value = item.partition(":")
                if key == "de":
                    value = value.removeprefix("f:")
                tags[key] = value
        try:
            record = {
                "query": fields[0], "query_length": int(fields[1]),
                "query_start": int(fields[2]), "query_end": int(fields[3]),
                "strand": fields[4],
                "reference": fields[5], "reference_length": int(fields[6]),
                "reference_start": int(fields[7]), "reference_end": int(fields[8]),
                "matches": int(fields[9]), "block_length": int(fields[10]),
                "mapq": int(fields[11]), "tags": tags,
            }
        except ValueError:
            continue
        divergence = _tag(record, "de")
        try:
            identity = 1.0 - float(divergence) if divergence is not None else record["matches"] / max(record["block_length"], 1)
        except (TypeError, ValueError):
            identity = record["matches"] / max(record["block_length"], 1)
        record["identity"] = min(max(identity, 0.0), 1.0)
        records.append(record)
    if not records:
        raise StepError("genome_alignment: minimap2 produced no alignments between the two assemblies")
    return records


def _merge(spans: list[tuple[int, int]]) -> int:
    total = 0
    current_start = current_end = None
    for start, end in sorted(spans):
        if start > end:
            start, end = end, start
        if current_start is None:
            current_start, current_end = start, end
        elif start <= current_end:
            current_end = max(current_end, end)
        else:
            total += current_end - current_start
            current_start, current_end = start, end
    if current_start is not None:
        total += current_end - current_start
    return total


def coverage_bp(records: list[dict], side: str) -> int:
    spans = {}
    for record in records:
        key = record[f"{side}_name"]
        spans.setdefault(key, []).append((record[f"{side}_start"], record[f"{side}_end"]))
    return sum(_merge(items) for items in spans.values())


def alignment_statistics(records: list[dict], query_length: int, reference_length: int, min_block: int, min_identity: float) -> dict:
    kept = [r for r in records if r["block_length"] >= min_block and r["identity"] >= min_identity]
    if not kept:
        raise StepError("genome_alignment: no alignments passed the minimum block and identity filters")
    aligned_bp = sum(r["block_length"] for r in kept)
    weighted = sum(r["identity"] * r["block_length"] for r in kept)
    query_spans = {}
    reference_spans = {}
    for record in kept:
        query_spans.setdefault(record["query"], []).append((record["query_start"], record["query_end"]))
        reference_spans.setdefault(record["reference"], []).append((record["reference_start"], record["reference_end"]))
    query_bp = sum(_merge(items) for items in query_spans.values())
    reference_bp = sum(_merge(items) for items in reference_spans.values())
    lengths = sorted((r["block_length"] for r in kept), reverse=True)
    half = aligned_bp / 2.0
    cumulative = 0
    n50 = 0
    for length in lengths:
        cumulative += length
        if cumulative >= half:
            n50 = length
            break
    return {
        "n_alignments": len(kept),
        "aligned_bp": aligned_bp,
        "query_bp_covered": query_bp,
        "reference_bp_covered": reference_bp,
        "query_coverage": query_bp / query_length if query_length else 0.0,
        "reference_coverage": reference_bp / reference_length if reference_length else 0.0,
        "mean_identity": weighted / aligned_bp if aligned_bp else 0.0,
        "max_alignment_bp": max(lengths) if lengths else 0,
        "n50_alignment_bp": n50,
        "total_query_bp": query_length,
        "total_reference_bp": reference_length,
    }


def chain_blocks(records: list[dict], min_block: int = DEFAULT_MIN_BLOCK, gap: int = 2000, max_ref_gap: int = 50000) -> list[dict]:
    kept = [r for r in records if r["block_length"] >= min_block]
    kept.sort(key=lambda r: (r["reference"], r["reference_start"], r["reference_end"], r["query"], r["query_start"]))
    if not kept:
        raise StepError("genome_synteny: no alignments passed the minimum block length")
    blocks = []
    current = None
    for record in kept:
        if current is None:
            current = _start_block(record)
            continue
        if _extends(current, record, gap, max_ref_gap):
            _append(current, record)
        else:
            blocks.append(_finish(current))
            current = _start_block(record)
    if current is not None:
        blocks.append(_finish(current))
    blocks = [block for block in blocks if block["aligned_bp"] >= min_block]
    if not blocks:
        raise StepError("genome_synteny: chained blocks are shorter than the minimum block length")
    return blocks


def _oriented(record: dict) -> tuple[int, int]:
    if record["strand"] == "-":
        return record["query_length"] - record["query_end"], record["query_length"] - record["query_start"]
    return record["query_start"], record["query_end"]


def _start_block(record: dict) -> dict:
    start, end = _oriented(record)
    return {
        "reference": record["reference"], "query": record["query"],
        "reference_start": record["reference_start"], "reference_end": record["reference_end"],
        "query_start": start, "query_end": end,
        "strand": record["strand"], "n_alignments": 1,
        "aligned_bp": record["block_length"], "weighted_identity": record["identity"] * record["block_length"],
    }


def _extends(current: dict, record: dict, gap: int, max_ref_gap: int) -> bool:
    if record["reference"] != current["reference"] or record["query"] != current["query"]:
        return False
    if record["strand"] != current["strand"]:
        return False
    if record["reference_start"] > current["reference_end"] + max_ref_gap:
        return False
    start, end = _oriented(record)
    return current["query_end"] - gap <= start <= current["query_end"] + gap and end >= current["query_end"]


def _append(current: dict, record: dict) -> None:
    start, end = _oriented(record)
    current["reference_end"] = max(current["reference_end"], record["reference_end"])
    current["query_end"] = max(current["query_end"], end)
    current["query_start"] = min(current["query_start"], start)
    current["n_alignments"] += 1
    current["aligned_bp"] += record["block_length"]
    current["weighted_identity"] += record["identity"] * record["block_length"]


def _finish(current: dict) -> dict:
    current = dict(current)
    current["identity"] = current.pop("weighted_identity") / max(current["aligned_bp"], 1)
    current["length_bp"] = current["reference_end"] - current["reference_start"]
    return current


def rearrangement_summary(blocks: list[dict]) -> dict:
    if not blocks:
        raise StepError("genome_rearrangement: no synteny blocks were found")
    ordered = sorted(blocks, key=lambda b: (b["reference"], b["reference_start"]))
    forward = [b for b in ordered if b["strand"] == "+"]
    reverse = [b for b in ordered if b["strand"] == "-"]
    breakpoints = 0
    translocations = 0
    inversions = 0
    in_reverse = False
    previous = None
    for block in ordered:
        reversed_block = block["strand"] == "-"
        if reversed_block and not in_reverse:
            inversions += 1
        in_reverse = reversed_block
        if previous is not None:
            chromosome_change = (block["reference"] != previous["reference"]
                                 or block["query"] != previous["query"])
            if chromosome_change:
                translocations += 1
                breakpoints += 1
            elif block["strand"] != previous["strand"]:
                breakpoints += 1
            elif (block["reference_start"] - previous["reference_end"] > 50000
                  or block["query_start"] < previous["query_end"] - 2000):
                breakpoints += 1
        previous = block
    total_bp = sum(b["aligned_bp"] for b in ordered)
    forward_bp = sum(b["aligned_bp"] for b in forward)
    largest = max(ordered, key=lambda b: b["aligned_bp"])
    return {
        "n_blocks": len(ordered),
        "n_forward_blocks": len(forward),
        "n_reverse_blocks": len(reverse),
        "n_breakpoints": breakpoints,
        "n_inversions": inversions,
        "n_translocations": translocations,
        "syntenic_fraction": forward_bp / total_bp if total_bp else 0.0,
        "largest_block_bp": largest["aligned_bp"],
        "largest_block_fraction": largest["aligned_bp"] / total_bp if total_bp else 0.0,
        "total_block_bp": total_bp,
    }
