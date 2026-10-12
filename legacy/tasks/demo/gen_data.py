# tasks/demo/gen_data.py
"""Generate VCF test files for the demo task.

    variants_dip.vcf       diploid       30 variants x 500 samples
    variants_tri.vcf       triploid      15 variants x 200 samples
    variants_tet.vcf       tetraploid    12 variants x 100 samples
    variants_ma.vcf        multi-allelic  5 records x 100 samples
    variants_dip.vcf.gz    same as variants_dip.vcf, gzipped

Every file carries the full VCF header (fileformat, fileDate, source,
reference, assembly, phasing, FORMAT, INFO, FILTER, contig, ALT).

A few genotypes are missing in every file to exercise NaN handling.
Deterministic given SEED.
"""

from __future__ import annotations

import gzip
import random
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT_DIR = HERE / "input"
SEED = 42


def _header_lines(samples: list[str]) -> list[str]:
    lines = [
        "##fileformat=VCFv4.2",
        "##fileDate=20261008",
        "##source=biopipe-demo-generator",
        "##reference=file:///refs/GRCh38.fa",
        "##assembly=GRCh38",
        "##phasing=partial",
        '##FORMAT=<ID=GT,Number=1,Type=String,'
        'Description="Genotype">',
        '##FORMAT=<ID=GQ,Number=1,Type=Integer,'
        'Description="Genotype Quality">',
        '##INFO=<ID=DP,Number=1,Type=Integer,'
        'Description="Total Depth">',
        '##FILTER=<ID=PASS,Description="All filters passed">',
        '##ALT=<ID=DEL,Description="Deletion">',
    ]
    for c in range(1, 23):
        lines.append(f"##contig=<ID=chr{c},length={100_000_000 + c}>")

    header = ["#CHROM", "POS", "ID", "REF", "ALT",
              "QUAL", "FILTER", "INFO", "FORMAT"]
    header.extend(samples)
    lines.append("\t".join(header))
    return lines


def _write_vcf(
    path: Path,
    n_samples: int,
    n_variants: int,
    ploidy: int,
    seed: int,
    gz: bool = False,
) -> None:
    rng = random.Random(seed)
    samples = [f"S{i + 1:04d}" for i in range(n_samples)]

    opener = (
        (lambda p: gzip.open(p, "wt", encoding="utf-8"))
        if gz else
        (lambda p: open(p, "w", encoding="utf-8"))
    )

    with opener(path) as f:
        for line in _header_lines(samples):
            f.write(line + "\n")

        for i in range(n_variants):
            pos = 10000 + i * 5000
            vid = f"rs{i + 1}"
            ref = rng.choice("ACGT")
            alt = rng.choice([b for b in "ACGT" if b != ref])

            gts = []
            for _ in samples:
                if rng.random() < 0.02:
                    gts.append("/".join(["."] * ploidy))
                    continue
                alleles = [
                    "1" if rng.random() < 0.30 else "0"
                    for _ in range(ploidy)
                ]
                gts.append("/".join(alleles))

            fields = ["1", str(pos), vid, ref, alt,
                      ".", ".", ".", "GT"]
            fields.extend(gts)
            f.write("\t".join(fields) + "\n")


def _write_multiallelic(path: Path, n_samples: int, seed: int) -> None:
    """Five records, each with two ALTs. GT-only."""
    rng = random.Random(seed)
    samples = [f"S{i + 1:04d}" for i in range(n_samples)]

    with open(path, "w", encoding="utf-8") as f:
        for line in _header_lines(samples):
            f.write(line + "\n")

        for i in range(5):
            pos = 10000 + i * 1000
            vid = f"ma{i + 1}"
            ref = "A"
            alt = "C,G"

            gts = []
            for _ in samples:
                if rng.random() < 0.02:
                    gts.append("./.")
                    continue
                alleles = []
                for _ in range(2):
                    x = rng.random()
                    alleles.append(
                        0 if x < 0.25 else
                        1 if x < 0.70 else
                        2
                    )
                gts.append(f"{alleles[0]}/{alleles[1]}")

            fields = ["1", str(pos), vid, ref, alt,
                      ".", ".", ".", "GT"]
            fields.extend(gts)
            f.write("\t".join(fields) + "\n")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    _write_vcf(OUT_DIR / "variants_dip.vcf", 500, 30, 2, SEED)
    _write_vcf(OUT_DIR / "variants_tri.vcf", 200, 15, 3, SEED + 1)
    _write_vcf(OUT_DIR / "variants_tet.vcf", 100, 12, 4, SEED + 2)
    _write_multiallelic(OUT_DIR / "variants_ma.vcf", 100, SEED + 10)
    _write_vcf(OUT_DIR / "variants_dip.vcf.gz", 500, 30, 2, SEED, gz=True)

    print(f"Wrote 5 files to {OUT_DIR}")
    print("  variants_dip.vcf       diploid        30 x 500")
    print("  variants_tri.vcf       triploid       15 x 200")
    print("  variants_tet.vcf       tetraploid     12 x 100")
    print("  variants_ma.vcf        multi-allelic   5 x 100  (splits to 10)")
    print("  variants_dip.vcf.gz    diploid        30 x 500  (gzipped)")


if __name__ == "__main__":
    main()