"""UCSC chain-file parsing and coordinate lifting helpers."""
from __future__ import annotations

import gzip
from pathlib import Path

import numpy as np

from src.core import StepError

_COMPLEMENT = str.maketrans(
    "ACGTUNRYKMSWBDHVacgtunrykmswbdhv",
    "TGCAANYRMKSWVHDBtgcaanyrmkswvhdb",
)


def open_text(path):
    text = str(path)
    if text.endswith(".gz"):
        return gzip.open(text, "rt", encoding="utf-8", errors="replace")
    return open(text, "rt", encoding="utf-8", errors="replace")


def chain_path(artifact, operator):
    """Return a chain file path from a FileArtifact, validating the format."""
    files = getattr(artifact, "files", None)
    if not isinstance(files, dict) or not files:
        raise StepError(f"{operator}: chain input must be a FileArtifact")
    path = Path(next(iter(files.values())))
    if not path.is_file():
        raise StepError(f"{operator}: chain file not found: {path}")
    return path


def reverse_complement(sequence):
    return str(sequence).translate(_COMPLEMENT)[::-1]


def load_chain(path):
    """Parse a UCSC chain file into a list of dicts with block arrays."""
    chains = []
    current = None
    with open_text(path) as stream:
        for line in stream:
            line = line.strip()
            if not line:
                continue
            if line.startswith("chain "):
                parts = line.split()
                if len(parts) < 13:
                    raise StepError(f"liftover: malformed chain header: {line[:60]}")
                try:
                    score = float(parts[1])
                    t_name = parts[2]
                    t_size = int(parts[3])
                    t_start = int(parts[5])
                    t_end = int(parts[6])
                    q_name = parts[7]
                    q_size = int(parts[8])
                    q_strand = parts[9]
                    q_start = int(parts[10])
                    q_end = int(parts[11])
                    chain_id = parts[12]
                except (ValueError, IndexError) as exc:
                    raise StepError(f"liftover: malformed chain header: {line[:60]}") from exc
                if q_strand not in {"+", "-"}:
                    raise StepError(f"liftover: unsupported qStrand '{q_strand}'")
                if t_start < 0 or t_end <= t_start or t_end > t_size:
                    raise StepError(f"liftover: target range out of bounds in chain {chain_id}")
                current = {
                    "score": score,
                    "t_name": t_name,
                    "t_size": t_size,
                    "t_start": t_start,
                    "t_end": t_end,
                    "q_name": q_name,
                    "q_size": q_size,
                    "q_strand": q_strand,
                    "q_start": q_start,
                    "q_end": q_end,
                    "id": chain_id,
                    "blocks": [],
                }
                chains.append(current)
                continue
            if current is None:
                raise StepError("liftover: chain block before the first header")
            parts = line.split()
            if len(parts) not in (1, 3):
                raise StepError(f"liftover: malformed chain block: {line[:60]}")
            try:
                size = int(parts[0])
                dt = int(parts[1]) if len(parts) == 3 else 0
                dq = int(parts[2]) if len(parts) == 3 else 0
            except ValueError as exc:
                raise StepError(f"liftover: malformed chain block: {line[:60]}") from exc
            if size <= 0:
                raise StepError(f"liftover: chain block size must be positive (chain {current['id']})")
            current["blocks"].append((size, dt, dq))
            if dt == 0 and dq == 0:
                current = None

    for chain in chains:
        sizes = np.asarray([block[0] for block in chain["blocks"]], dtype=np.int64)
        dts = np.asarray([block[1] for block in chain["blocks"]], dtype=np.int64)
        dqs = np.asarray([block[2] for block in chain["blocks"]], dtype=np.int64)
        chain["sizes"] = sizes
        chain["t_block_starts"] = chain["t_start"] + np.concatenate(([0], np.cumsum(sizes + dts)[:-1]))
        chain["q_block_starts"] = chain["q_start"] + np.concatenate(([0], np.cumsum(sizes + dqs)[:-1]))

    if not chains:
        raise StepError("liftover: no chains found")
    return chains


class ChainIndex:
    """Fast target-coordinate lookup over a parsed chain set."""

    def __init__(self, chains):
        self.chains = chains
        self.by_chrom = {}
        for chain in chains:
            self.by_chrom.setdefault(chain["t_name"], []).append(chain)
        for items in self.by_chrom.values():
            items.sort(key=lambda item: item["t_start"])
        self._starts = {
            name: np.asarray([item["t_start"] for item in items], dtype=np.int64)
            for name, items in self.by_chrom.items()
        }

    def resolve(self, chrom):
        """Resolve a chromosome name with or without the ``chr`` prefix."""
        if chrom in self.by_chrom:
            return chrom
        if chrom.startswith("chr"):
            bare = chrom[3:]
            if bare in self.by_chrom:
                return bare
        else:
            prefixed = "chr" + chrom
            if prefixed in self.by_chrom:
                return prefixed
        return None

    def map_base(self, chrom, position):
        """Map one target base; returns (q_name, q_pos, q_strand, chain) or None."""
        chrom = self.resolve(chrom)
        items = self.by_chrom.get(chrom)
        if not items:
            return None
        position = int(position)
        starts = self._starts[chrom]
        index = int(np.searchsorted(starts, position, side="right")) - 1
        if index < 0:
            return None
        chain = items[index]
        if position >= chain["t_end"]:
            return None
        block = int(np.searchsorted(chain["t_block_starts"], position, side="right")) - 1
        if block < 0:
            return None
        offset = position - int(chain["t_block_starts"][block])
        size = int(chain["sizes"][block])
        if offset >= size:
            return None
        q_position = int(chain["q_block_starts"][block]) + offset
        if chain["q_strand"] == "-":
            q_position = chain["q_size"] - 1 - q_position
        return chain["q_name"], q_position, chain["q_strand"], chain

    def map_interval(self, chrom, start, end):
        """Map a half-open interval; returns (q_name, q_start, q_end, strand) or None."""
        start = int(start)
        end = int(end)
        if end < start:
            raise ValueError(f"interval end {end} is before start {start}")
        if end == start:
            mapped = self.map_base(chrom, start)
            if mapped is None:
                return None
            return mapped[0], mapped[1], mapped[1], mapped[2]
        first = self.map_base(chrom, start)
        last = self.map_base(chrom, end - 1)
        if first is None or last is None:
            return None
        if first[0] != last[0] or first[3] is not last[3]:
            return None
        low = min(first[1], last[1])
        high = max(first[1], last[1]) + 1
        return first[0], low, high, first[2]


def coverage_rows(chains, chrom=None):
    """Per-target-chromosome chain coverage (aligned and non-redundant bases)."""
    grouped = {}
    for chain in chains:
        grouped.setdefault(chain["t_name"], []).append(chain)
    rows = []
    for name in sorted(grouped):
        if chrom and name != chrom:
            continue
        items = grouped[name]
        intervals = []
        for chain in items:
            starts = chain["t_block_starts"]
            for block, size in enumerate(chain["sizes"].tolist()):
                begin = int(starts[block])
                intervals.append((begin, begin + int(size)))
        intervals.sort()
        merged = []
        for begin, finish in intervals:
            if merged and begin <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(merged[-1][1], finish))
            else:
                merged.append((begin, finish))
        covered = sum(finish - begin for begin, finish in merged)
        t_size = items[0]["t_size"]
        rows.append(
            {
                "chrom": name,
                "n_chains": len(items),
                "aligned_bp": int(sum(int(chain["sizes"].sum()) for chain in items)),
                "covered_bp": int(covered),
                "coverage_fraction": (covered / t_size) if t_size else 0.0,
                "t_size": int(t_size),
            }
        )
    if not rows:
        raise StepError(f"liftover: no chains for chromosome '{chrom}'")
    return rows
