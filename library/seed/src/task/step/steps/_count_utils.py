"""Helpers for counting BAM alignments against annotation features."""
from __future__ import annotations

from bisect import bisect_left, bisect_right

from ._bam_utils import iter_records, ref_span

_PRIMARY_SKIP = 0x4 | 0x100 | 0x200 | 0x800


def read_gff_features(path: str, feature_type: str, id_attribute: str):
    """Return [(seqid, feature_id, start, end, strand)] with 0-based half-open ends."""
    features = []
    opener = open
    if path.endswith(".gz"):
        import gzip

        opener = gzip.open
    with opener(path, "rt", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if not line or line.startswith("#"):
                continue
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 9 or parts[2] != feature_type:
                continue
            attributes = parts[8]
            value = None
            for item in attributes.split(";"):
                item = item.strip()
                if not item:
                    continue
                if "=" in item:
                    key, _, raw = item.partition("=")
                else:
                    key, _, raw = item.partition(" ")
                if key.strip() == id_attribute:
                    value = raw.strip().strip('"')
                    break
            if not value:
                continue
            start = int(parts[3]) - 1
            end = int(parts[4])
            if end <= start:
                continue
            features.append((parts[0], value, start, end, parts[6] if parts[6] in "+-" else "."))
    if not features:
        raise ValueError(f"no {feature_type!r} features with attribute {id_attribute!r}")
    return features


class FeatureIndex:
    """Bin features by reference and genomic window for fast overlap lookups."""

    def __init__(self, features, bin_size: int = 10_000):
        self.bin_size = bin_size
        self.by_ref = {}
        for seqid, feature_id, start, end, strand in features:
            bins = self.by_ref.setdefault(seqid, {})
            first = start // bin_size
            last = (end - 1) // bin_size
            for index in range(first, last + 1):
                bins.setdefault(index, []).append((start, end, feature_id, strand))

    def overlaps(self, seqid: str, start: int, end: int):
        bins = self.by_ref.get(seqid)
        if not bins:
            return []
        first = start // self.bin_size
        last = (end - 1) // self.bin_size
        found = []
        seen = set()
        for index in range(first, last + 1):
            for feature in bins.get(index, ()):
                if feature[2] in seen:
                    continue
                if feature[0] < end and start < feature[1]:
                    seen.add(feature[2])
                    found.append(feature)
        return found


def count_alignments(bam_path: str, features, min_mapq: int = 0, count_pairs: bool = False,
                     max_records: int = 0):
    """Count primary alignments (or read-1 fragments) overlapping each feature."""
    from ._bam_utils import read_header

    _, references = read_header(bam_path)
    names = [name for name, _ in references]
    index = FeatureIndex(features)
    counts = {feature_id: 0 for _, feature_id, _, _, _ in features}
    considered = 0
    for record in iter_records(bam_path, max_records=max_records):
        flag = record["flag"]
        if flag & _PRIMARY_SKIP:
            continue
        if record["mapq"] < min_mapq:
            continue
        if count_pairs and not flag & 0x40:
            continue
        ref_id = record["ref_id"]
        if ref_id < 0 or ref_id >= len(names):
            continue
        span = ref_span(record["cigar"])
        if span <= 0:
            continue
        start = record["pos"]
        end = start + span
        hits = index.overlaps(names[ref_id], start, end)
        if not hits:
            continue
        considered += 1
        for hit in hits:
            counts[hit[2]] += 1
    return counts, considered
