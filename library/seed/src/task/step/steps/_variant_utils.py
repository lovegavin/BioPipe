"""Dependency-free helpers for variant consequence annotation.

The module parses GFF3 gene models and a FASTA reference directly, so the
operators stay usable in the base environment (no pysam/cyvcf2).  Coordinates
are 1-based inclusive, matching both GFF3 and VCF.
"""
from __future__ import annotations

import gzip
from bisect import bisect_right

SEVERITY = (
    "stop_gained",
    "stop_lost",
    "start_lost",
    "splice_acceptor",
    "splice_donor",
    "frameshift",
    "inframe_deletion",
    "inframe_insertion",
    "missense",
    "synonymous",
    "5_prime_UTR",
    "3_prime_UTR",
    "non_coding",
    "intron",
    "intergenic",
)
SEVERITY_RANK = {name: index for index, name in enumerate(SEVERITY)}
CODING_CLASSES = {
    "stop_gained", "stop_lost", "start_lost", "missense", "synonymous",
    "frameshift", "inframe_deletion", "inframe_insertion",
}
SPLICE_CLASSES = {"splice_acceptor", "splice_donor"}

_BASES = "TCAG"
_AMINO = "FFLLSSSSYY**CC*WLLLLPPPPHHQQRRRRIIIMTTTTNNKKSSRRVVVVAAAADDEEGGGG"


def _build_code():
    table = {}
    index = 0
    for first in _BASES:
        for second in _BASES:
            for third in _BASES:
                table[first + second + third] = _AMINO[index]
                index += 1
    return table


CODON_TABLE = _build_code()
_COMPLEMENT = str.maketrans("ACGTNacgtn", "TGCANtgcan")


def reverse_complement(sequence: str) -> str:
    return sequence.translate(_COMPLEMENT)[::-1]


def translate(codon: str) -> str:
    return CODON_TABLE.get(codon.upper(), "X")


def parse_attributes(text: str) -> dict:
    result = {}
    for part in text.strip().split(";"):
        part = part.strip()
        if not part or "=" not in part:
            continue
        key, value = part.split("=", 1)
        result[key.strip()] = value.strip()
    return result


def _clean_id(value: str) -> str:
    for prefix in ("gene:", "transcript:", "mRNA:"):
        if value.startswith(prefix):
            return value[len(prefix):]
    return value


class Transcript:
    __slots__ = ("id", "gene_id", "gene_name", "biotype", "strand", "chrom", "start", "end", "exons", "cds", "cds_phases")

    def __init__(self, tid, gene_id, gene_name, biotype, strand, chrom, start, end):
        self.id = tid
        self.gene_id = gene_id
        self.gene_name = gene_name
        self.biotype = biotype
        self.strand = strand if strand in ("+", "-") else "+"
        self.chrom = chrom
        self.start = start
        self.end = end
        self.exons = []
        self.cds = []
        self.cds_phases = {}

    @property
    def is_coding(self) -> bool:
        return bool(self.cds) and self.biotype == "protein_coding"

    def sorted_cds(self):
        return sorted(self.cds) if self.strand == "+" else sorted(self.cds, reverse=True)

    @property
    def cds_offset(self) -> int:
        """Bases to skip at the 5' end of the spliced CDS (GFF3 phase)."""
        ordered = self.sorted_cds()
        if not ordered:
            return 0
        return self.cds_phases.get(ordered[0], 0) % 3

    def sorted_exons(self):
        return sorted(self.exons) if self.strand == "+" else sorted(self.exons, reverse=True)


def load_gff3(path) -> tuple:
    """Return (genes, transcripts, bins) parsed from a GFF3 file."""
    genes = {}
    transcripts = {}
    opener = gzip.open if str(path).endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if not line or line.startswith("#"):
                continue
            fields = line.rstrip("\n").split("\t")
            if len(fields) != 9:
                continue
            chrom, _, kind, start, end, _, strand, _, attr = fields
            attributes = parse_attributes(attr)
            if kind == "gene":
                gid = _clean_id(attributes.get("ID", ""))
                if not gid:
                    continue
                genes[gid] = {
                    "name": attributes.get("gene_name", attributes.get("Name", gid)),
                    "biotype": attributes.get("gene_type", attributes.get("biotype", "")),
                }
            elif kind in ("transcript", "mRNA"):
                tid = _clean_id(attributes.get("ID", ""))
                if not tid:
                    continue
                parent = _clean_id(attributes.get("Parent", "").split(",")[0])
                transcripts[tid] = Transcript(
                    tid,
                    parent,
                    attributes.get("gene_name", parent),
                    attributes.get("transcript_type", attributes.get("biotype", "")),
                    strand,
                    chrom,
                    int(start),
                    int(end),
                )
            elif kind == "exon":
                for parent in attributes.get("Parent", "").split(","):
                    parent = _clean_id(parent.strip())
                    if parent in transcripts:
                        transcripts[parent].exons.append((int(start), int(end)))
            elif kind == "CDS":
                for parent in attributes.get("Parent", "").split(","):
                    parent = _clean_id(parent.strip())
                    if parent in transcripts:
                        transcripts[parent].cds.append((int(start), int(end)))
                        phase_field = fields[7]
                        transcripts[parent].cds_phases[(int(start), int(end))] = (
                            int(phase_field) if phase_field in ("0", "1", "2") else 0
                        )
    for tid, tx in transcripts.items():
        gene = genes.get(tx.gene_id)
        if gene:
            tx.gene_name = gene["name"]
            if not tx.biotype:
                tx.biotype = gene["biotype"]
    bins = {}
    for tx in transcripts.values():
        first = tx.start // 1_000_000
        last = tx.end // 1_000_000
        for bucket in range(first, last + 1):
            bins.setdefault((tx.chrom, bucket), []).append(tx)
    return genes, transcripts, bins


def nearby_transcripts(bins, chrom, pos):
    return bins.get((chrom, pos // 1_000_000), [])


def load_fasta(path) -> dict:
    opener = gzip.open if str(path).endswith(".gz") else open
    sequences = {}
    name = None
    chunks = []
    with opener(path, "rt", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            line = line.rstrip("\n")
            if line.startswith(">"):
                if name is not None:
                    sequences[name] = "".join(chunks).upper()
                name = line[1:].split()[0]
                chunks = []
            elif line:
                chunks.append(line)
    if name is not None:
        sequences[name] = "".join(chunks).upper()
    return sequences


def cds_index(tx: Transcript, pos: int):
    """0-based position of ``pos`` inside the spliced CDS, or None."""
    index = 0
    offset = tx.cds_offset
    for start, end in tx.sorted_cds():
        if start <= pos <= end:
            raw = index + (pos - start if tx.strand == "+" else end - pos)
            shifted = raw - offset
            return shifted if shifted >= 0 else None
        index += end - start + 1
    return None


def codon_positions(tx: Transcript, codon_index: int):
    """Genomic positions of one codon, ordered 5'->3' on the transcript."""
    need_start = codon_index * 3 + tx.cds_offset
    need_end = need_start + 3
    positions = []
    index = 0
    for start, end in tx.sorted_cds():
        length = end - start + 1
        if index + length <= need_start:
            index += length
            continue
        if index >= need_end:
            break
        low = max(0, need_start - index)
        high = min(length, need_end - index)
        if tx.strand == "+":
            positions.extend(range(start + low, start + high))
        else:
            positions.extend(range(end - low, end - high, -1))
        index += length
    return positions[:3]


def coding_snv(tx: Transcript, pos: int, alt: str, genome: dict):
    sequence = genome[tx.chrom]
    index = cds_index(tx, pos)
    if index is None:
        return None
    codon_index = index // 3
    offset = index % 3
    positions = codon_positions(tx, codon_index)
    if len(positions) != 3:
        return None
    bases = [sequence[p - 1] for p in positions]
    if tx.strand == "-":
        # Codon positions are already in transcript order; complement the bases.
        bases = [base.translate(_COMPLEMENT) for base in bases]
    ref_codon = "".join(bases)
    ref_aa = translate(ref_codon)
    alt_base = alt.upper()
    if tx.strand == "-":
        alt_base = alt_base.translate(_COMPLEMENT)
    alt_codon = ref_codon[:offset] + alt_base + ref_codon[offset + 1:]
    alt_aa = translate(alt_codon)
    number = codon_index + 1
    if ref_aa == alt_aa:
        consequence = "synonymous"
        change = f"{number}{ref_aa}"
    elif alt_aa == "*":
        consequence = "stop_gained"
        change = f"{number}{ref_aa}>{number}*"
    elif ref_aa == "*":
        consequence = "stop_lost"
        change = f"{number}*>{number}{alt_aa}"
    elif codon_index == 0 and ref_aa == "M" and alt_aa != "M":
        consequence = "start_lost"
        change = f"{number}M>{number}{alt_aa}"
    else:
        consequence = "missense"
        change = f"{number}{ref_aa}>{number}{alt_aa}"
    return consequence, change, ref_codon + ">" + alt_codon


def _splice_class(tx: Transcript, pos: int):
    exons = tx.sorted_exons()
    for index in range(len(exons) - 1):
        left_end = exons[index][0] if tx.strand == "-" else exons[index][1]
        right_start = exons[index + 1][1] if tx.strand == "-" else exons[index + 1][0]
        if tx.strand == "+":
            if left_end < pos < right_start:
                if pos in (left_end + 1, left_end + 2):
                    return "splice_donor"
                if pos in (right_start - 1, right_start - 2):
                    return "splice_acceptor"
                return "intron"
        else:
            if right_start < pos < left_end:
                if pos in (left_end - 1, left_end - 2):
                    return "splice_donor"
                if pos in (right_start + 1, right_start + 2):
                    return "splice_acceptor"
                return "intron"
    return "intron"


def classify_transcript(tx: Transcript, pos: int, ref: str, alt: str, genome: dict, genes: dict):
    """Return (consequence, gene, transcript, amino_acid, dna_change) or None."""
    if not (tx.start <= pos <= tx.end):
        return None
    gene = genes.get(tx.gene_id, {})
    gene_name = gene.get("name", tx.gene_name or tx.gene_id)
    in_exon = any(start <= pos <= end for start, end in tx.exons)
    if in_exon and any(start <= pos <= end for start, end in tx.cds):
        if len(ref) == 1 and len(alt) == 1:
            coding = coding_snv(tx, pos, alt, genome)
            if coding is None:
                return None
            consequence, change, dna_change = coding
            return consequence, gene_name, tx.id, change, dna_change
        delta = len(alt) - len(ref)
        if delta % 3:
            consequence = "frameshift"
        elif delta > 0:
            consequence = "inframe_insertion"
        else:
            consequence = "inframe_deletion"
        return consequence, gene_name, tx.id, None, f"{pos}{ref}>{alt}"
    if in_exon:
        if tx.cds:
            cds_start = min(start for start, _ in tx.cds)
            cds_end = max(end for _, end in tx.cds)
            if tx.strand == "+":
                consequence = "5_prime_UTR" if pos < cds_start else "3_prime_UTR"
            else:
                consequence = "5_prime_UTR" if pos > cds_end else "3_prime_UTR"
        else:
            consequence = "non_coding"
        return consequence, gene_name, tx.id, None, None
    return _splice_class(tx, pos), gene_name, tx.id, None, None


def annotate_variant(chrom, pos, ref, alt, bins, genes, genome):
    """Pick the most severe consequence across overlapping transcripts."""
    best = None
    for tx in nearby_transcripts(bins, chrom, pos):
        result = classify_transcript(tx, pos, ref, alt, genome, genes)
        if result is None:
            continue
        rank = SEVERITY_RANK.get(result[0], 99)
        if best is None or rank < best[0]:
            best = (rank,) + result
    if best is None:
        return "intergenic", "", "", "", ""
    return best[1:]
