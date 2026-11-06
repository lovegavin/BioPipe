"""Shared BAM/BGZF and FASTA helpers used by the alignment operators.

The helpers decode only the fields an operator needs and keep memory bounded:
records are streamed, and pileups use one counter array per reference.
"""
from __future__ import annotations

import gzip
import struct

_MAGIC = b"BAM\x01"
_SEQ_CODES = "=ACMGRSVTWYHKDBN"
_CIGAR_OPS = "MIDNSHP=X"
_REF_OPS = frozenset("MDN=X")
_QUERY_OPS = frozenset("MIS=X")


def _is_gzip(path: str) -> bool:
    with open(path, "rb") as handle:
        return handle.read(2) == b"\x1f\x8b"


def read_header(path: str):
    """Return (header text, [(reference name, length), ...])."""
    opener = gzip.open if _is_gzip(path) else open
    with opener(path, "rb") as handle:
        if handle.read(4) != _MAGIC:
            raise ValueError("not a BAM file (missing BAM\\x01 magic)")
        (l_text,) = struct.unpack("<i", handle.read(4))
        text = handle.read(l_text).decode("utf-8", "replace")
        (n_ref,) = struct.unpack("<i", handle.read(4))
        references = []
        for _ in range(n_ref):
            (l_name,) = struct.unpack("<i", handle.read(4))
            name = handle.read(l_name).rstrip(b"\x00").decode("utf-8", "replace")
            (length,) = struct.unpack("<i", handle.read(4))
            references.append((name, length))
    return text, references


def _decode_sequence(raw: bytes, length: int) -> str:
    out = []
    for index in range(length):
        byte = raw[index >> 1]
        code = byte >> 4 if index % 2 == 0 else byte & 0x0F
        out.append(_SEQ_CODES[code])
    return "".join(out)


def iter_records(path: str, max_records: int = 0, decode_sequence: bool = False):
    """Yield BAM records as dictionaries with the fields operators need."""
    opener = gzip.open if _is_gzip(path) else open
    with opener(path, "rb") as handle:
        if handle.read(4) != _MAGIC:
            raise ValueError("not a BAM file (missing BAM\\x01 magic)")
        (l_text,) = struct.unpack("<i", handle.read(4))
        handle.read(l_text)
        (n_ref,) = struct.unpack("<i", handle.read(4))
        for _ in range(n_ref):
            (l_name,) = struct.unpack("<i", handle.read(4))
            handle.read(l_name)
            handle.read(4)

        seen = 0
        while True:
            head = handle.read(4)
            if len(head) < 4:
                break
            (block_size,) = struct.unpack("<i", head)
            record = handle.read(block_size)
            if len(record) < block_size:
                raise ValueError("truncated BAM record")
            (
                ref_id,
                pos,
                l_read_name,
                mapq,
                _bin,
                n_cigar,
                flag,
                l_seq,
                next_ref_id,
                next_pos,
                tlen,
            ) = struct.unpack_from("<iiBBHHHiiii", record, 0)
            cigar_offset = 32 + l_read_name
            cigar = []
            for index in range(n_cigar):
                (value,) = struct.unpack_from("<I", record, cigar_offset + 4 * index)
                cigar.append((_CIGAR_OPS[value & 0x0F], value >> 4))
            seq_offset = cigar_offset + 4 * n_cigar
            seq_bytes = (l_seq + 1) // 2
            sequence = ""
            if decode_sequence and l_seq:
                sequence = _decode_sequence(record[seq_offset: seq_offset + seq_bytes], l_seq)
            qual_offset = seq_offset + seq_bytes
            quality = record[qual_offset: qual_offset + l_seq]
            yield {
                "ref_id": ref_id,
                "pos": pos,
                "mapq": mapq,
                "flag": flag,
                "seq": sequence,
                "qual": quality,
                "cigar": cigar,
                "next_ref_id": next_ref_id,
                "next_pos": next_pos,
                "tlen": tlen,
            }
            seen += 1
            if max_records and seen >= max_records:
                break


def ref_span(cigar) -> int:
    return sum(length for op, length in cigar if op in _REF_OPS)


def read_fasta(path: str) -> dict:
    """Read a FASTA file (optionally gzipped) into {name: sequence}."""
    opener = gzip.open if _is_gzip(path) else open
    sequences = {}
    name = None
    chunks = []
    with opener(path, "rt", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            if line.startswith(">"):
                if name is not None:
                    sequences[name] = "".join(chunks)
                name = line[1:].split()[0]
                chunks = []
            elif name is not None:
                chunks.append(line.upper())
    if name is not None:
        sequences[name] = "".join(chunks)
    if not sequences and name is None:
        raise ValueError("empty FASTA file")
    return sequences


def pileup_counts(
    bam_path: str,
    references,
    reference_sequences: dict,
    min_mapq: int = 0,
    min_base_quality: int = 20,
    max_records: int = 0,
):
    """Return {reference name: int32 array of shape (4, length)} base counts."""
    import numpy as np

    codes = {"A": 0, "C": 1, "G": 2, "T": 3}
    counts = {}
    for name, length in references:
        if name not in reference_sequences:
            raise ValueError(f"reference sequence {name!r} is missing from the FASTA file")
        counts[name] = np.zeros((4, length), dtype=np.int32)
    primary_skip = 0x100 | 0x800
    for record in iter_records(bam_path, max_records=max_records, decode_sequence=True):
        flag = record["flag"]
        if flag & primary_skip or flag & 0x4:
            continue
        if record["mapq"] < min_mapq:
            continue
        name = references[record["ref_id"]][0]
        array = counts[name]
        ref_pos = record["pos"]
        query_pos = 0
        sequence = record["seq"]
        quality = record["qual"]
        for op, length in record["cigar"]:
            if op in "M=X":
                for offset in range(length):
                    base = sequence[query_pos + offset]
                    code = codes.get(base)
                    if code is not None and quality[query_pos + offset] >= min_base_quality:
                        position = ref_pos + offset
                        if 0 <= position < array.shape[1]:
                            array[code, position] += 1
                ref_pos += length
                query_pos += length
            elif op in "IS":
                query_pos += length
            elif op in "DN":
                ref_pos += length
    return counts
