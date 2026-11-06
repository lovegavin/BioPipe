"""Peak-calling helpers shared by the ATAC peak operators."""
from __future__ import annotations

import gzip
import struct

import numpy as np
from scipy.ndimage import uniform_filter1d
from scipy.stats import poisson

from src.core import StepError

_MAGIC = b'BAM\x01'
_RECORD = '<iiBBHHHiiii'


def _check_gzip(path):
    with open(path, 'rb') as probe:
        if probe.read(2) != b'\x1f\x8b':
            raise StepError(f'{path}: input is not a gzip/BGZF file')


def _read_header(handle):
    if handle.read(4) != _MAGIC:
        raise StepError('input is not a BAM file')
    l_text = struct.unpack('<i', handle.read(4))[0]
    handle.read(l_text)
    n_ref = struct.unpack('<i', handle.read(4))[0]
    names, lengths = [], []
    for _ in range(n_ref):
        l_name = struct.unpack('<i', handle.read(4))[0]
        names.append(handle.read(l_name - 1).decode('ascii'))
        handle.read(1)
        lengths.append(struct.unpack('<i', handle.read(4))[0])
    return names, lengths


def read_references(path):
    _check_gzip(path)
    with gzip.open(path, 'rb') as handle:
        return _read_header(handle)


def iter_fragments(path, min_mapq=30, max_fragments=0):
    """Yield ``(chrom, start, end)`` for paired fragments (read 1 only)."""
    _check_gzip(path)
    with gzip.open(path, 'rb') as handle:
        names, _lengths = _read_header(handle)
        n = 0
        while True:
            head = handle.read(4)
            if len(head) < 4:
                break
            block = struct.unpack('<i', head)[0]
            data = handle.read(block)
            if len(data) < block:
                break
            (ref_id, pos, _l_name, mapq, _bin, _n_cigar, flag,
             _l_seq, _next_ref, _next_pos, tlen) = struct.unpack_from(_RECORD, data, 0)
            if flag & 0x4 or flag & 0x100 or flag & 0x800:
                continue
            if not flag & 0x1 or not flag & 0x40:
                continue
            if tlen <= 0 or ref_id < 0 or mapq < min_mapq:
                continue
            yield names[ref_id], pos, pos + tlen
            n += 1
            if max_fragments and n >= max_fragments:
                break


def pileup(starts, ends, length):
    """Per-base fragment coverage for one chromosome."""
    length = int(length)
    starts = np.clip(np.asarray(starts, dtype=np.int64), 0, length)
    ends = np.clip(np.asarray(ends, dtype=np.int64), 0, length)
    delta = (np.bincount(starts, minlength=length + 1)[:length + 1].astype(np.int64)
             - np.bincount(ends, minlength=length + 1)[:length + 1].astype(np.int64))
    return np.cumsum(delta[:-1]).astype(np.int32)


def _runs(mask, length):
    padded = np.concatenate(([False], mask, [False]))
    change = np.diff(padded.astype(np.int8))
    starts = np.nonzero(change == 1)[0]
    ends = np.nonzero(change == -1)[0]
    return starts, ends


def _merge_runs(starts, ends, max_gap):
    merged = []
    current_start = current_end = None
    for start, end in zip(starts, ends):
        if current_start is None:
            current_start, current_end = int(start), int(end)
            continue
        if start - current_end <= max_gap:
            current_end = int(end)
        else:
            merged.append((current_start, current_end))
            current_start, current_end = int(start), int(end)
    if current_start is not None:
        merged.append((current_start, current_end))
    return merged


def call_peaks(fragments, chrom_lengths, *, qvalue=0.05, max_gap=50,
               min_length=100, local_windows=(1000, 10000),
               candidate_sigma=3.0, extension_bp=260,
               total_fragments_bp=0.0, genome_bp=1):
    """Call peaks from fragments grouped by chromosome.

    Candidates are regions where the per-base fragment coverage exceeds the
    local Poisson mean by ``candidate_sigma`` standard deviations.  Poisson
    p-values at the candidate summits are corrected with Benjamini-Hochberg,
    and significant candidate regions are grown by ``extension_bp`` so that
    the reported intervals cover the whole fragment footprint.
    """
    if genome_bp <= 0:
        raise StepError('genome length must be positive')
    genome_lambda = float(total_fragments_bp) / float(genome_bp)
    peaks = []
    for chrom in sorted(fragments):
        starts, ends = fragments[chrom]
        length = int(chrom_lengths.get(chrom, 0))
        if length <= 0 or len(starts) == 0:
            continue
        counts = pileup(starts, ends, length)
        signal = counts.astype(np.float32)
        lam = None
        for window in local_windows:
            size = int(window) | 1
            filtered = uniform_filter1d(signal, size=size, mode='constant')
            lam = filtered if lam is None else np.maximum(lam, filtered, out=lam)
        lam = np.maximum(lam, max(genome_lambda, 1e-12), out=lam)
        del signal

        idx = np.nonzero(counts)[0]
        if idx.size == 0:
            continue
        pvals = poisson.sf(counts[idx] - 1, lam[idx])

        # Candidate regions: coverage above local mean by candidate_sigma.
        threshold = lam + float(candidate_sigma) * np.sqrt(np.maximum(lam, 1.0))
        cand_starts, cand_ends = _runs(counts > threshold, length)
        candidates = _merge_runs(cand_starts, cand_ends, 100)
        if not candidates:
            continue
        cand_p = np.empty(len(candidates), dtype=np.float64)
        cand_summit = np.empty(len(candidates), dtype=np.int64)
        for i, (start, end) in enumerate(candidates):
            segment = counts[start:end]
            offset = int(np.argmax(segment))
            cand_summit[i] = start + offset
            cand_p[i] = poisson.sf(segment[offset] - 1, lam[start + offset])

        order = np.argsort(cand_p)
        ranked = cand_p[order]
        m = ranked.size
        qvals = ranked * m / np.arange(1, m + 1)
        qvals = np.minimum.accumulate(qvals[::-1])[::-1]
        qvals = np.clip(qvals, 0.0, 1.0)
        significant = qvals <= float(qvalue)
        if not significant.any():
            continue
        p_cut = float(ranked[significant].max())
        mask = np.zeros(length, dtype=bool)
        mask[idx[pvals <= p_cut]] = True

        # q-value map for scoring the final intervals.
        qmap = np.ones(length, dtype=np.float64)
        qmap[idx[order]] = qvals

        run_starts, run_ends = _runs(mask, length)
        merged = _merge_runs(run_starts, run_ends, int(max_gap))
        extended = [(max(0, start - int(extension_bp)),
                     min(length, end + int(extension_bp))) for start, end in merged]
        for start, end in _merge_runs([item[0] for item in extended],
                                      [item[1] for item in extended], 0):
            if end - start < int(min_length):
                continue
            segment = counts[start:end]
            offset = int(np.argmax(segment))
            summit = start + offset
            count = int(segment[offset])
            score = float(-np.log10(max(qmap[start:end].min(), 1e-300)))
            fold = float(count / max(lam[summit], 1e-12))
            peaks.append({'chrom': chrom, 'start': int(start), 'end': int(end),
                          'length': int(end - start), 'summit': int(summit),
                          'count': count, 'score': score, 'fold_enrichment': fold})
    peaks.sort(key=lambda item: (item['chrom'], item['start']))
    return peaks
