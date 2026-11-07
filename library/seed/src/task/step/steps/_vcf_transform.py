"""Helpers for VCF normalisation, merging and concatenation."""
from __future__ import annotations

from src.core import StepError


def load_reference(path):
    chroms = {}
    name = None
    chunks = []
    with open(path, 'rt', encoding='utf-8', errors='replace') as handle:
        for line in handle:
            if line.startswith('>'):
                if name is not None:
                    chroms[name] = ''.join(chunks).upper()
                name = line[1:].split()[0] if line[1:].strip() else ''
                chunks = []
            else:
                chunks.append(line.strip())
    if name is not None:
        chroms[name] = ''.join(chunks).upper()
    if not chroms:
        raise StepError('vcf reference FASTA contains no sequences')
    return chroms


def _base(seq, pos):
    if 1 <= pos <= len(seq):
        return seq[pos - 1]
    return ''


def trim_alleles(pos, ref, alt):
    """Trim shared suffix/prefix while keeping at least one base."""
    while len(ref) > 1 and len(alt) > 1 and ref[-1] == alt[-1]:
        ref, alt = ref[:-1], alt[:-1]
    while len(ref) > 1 and len(alt) > 1 and ref[0] == alt[0]:
        ref, alt = ref[1:], alt[1:]
        pos += 1
    return pos, ref, alt


def left_align(pos, ref, alt, seq):
    """Shift an indel left with the vt/bcftools trim-extend loop."""
    guard = 0
    while True:
        if ref and alt and ref[-1] == alt[-1]:
            ref, alt = ref[:-1], alt[:-1]
            guard += 1
            if guard > 100000:
                raise StepError('left alignment did not converge')
            continue
        if not ref or not alt:
            if pos <= 1:
                break
            base = _base(seq, pos - 1)
            if not base:
                break
            ref = base + ref
            alt = base + alt
            pos -= 1
            continue
        break
    return trim_alleles(pos, ref, alt)


def normalize(pos, ref, alts, seq):
    out = []
    for alt in alts:
        p, r, a = int(pos), ref.upper(), alt.upper()
        if len(r) != len(a):
            p, r, a = left_align(p, r, a, seq)
        else:
            p, r, a = trim_alleles(p, r, a)
        out.append((p, r, a))
    return out


def split_alts(alt_text):
    return [a for a in alt_text.split(',') if a]


def fasta_path(artifact, operator):
    from src.core import FileArtifact
    if not isinstance(artifact, FileArtifact):
        raise StepError(f'{operator} requires a reference FASTA file')
    artifact.validate()
    if artifact.format not in ('fasta', 'fa', 'fna'):
        raise StepError(f"{operator} requires a FASTA file, got {artifact.format!r}")
    return next(iter(artifact.files.values()))


def parse_info_fields(text):
    return [field for field in text.split(';') if field and field != '.']
