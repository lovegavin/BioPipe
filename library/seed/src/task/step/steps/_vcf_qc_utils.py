"""Sample- and site-level QC helpers for VCF files."""
from __future__ import annotations

from src.core.errors import StepError

from ._vcf_utils import genotype_dosage, iter_sites, open_text, read_header

TRANSITIONS = {("A", "G"), ("G", "A"), ("C", "T"), ("T", "C")}


def vcf_path(artifact, operator: str) -> str:
    from src.core import FileArtifact

    if not isinstance(artifact, FileArtifact):
        raise StepError(f"{operator}: input must be a file artifact")
    if artifact.format not in {"vcf", "vcf.gz"}:
        raise StepError(f"{operator}: expected a VCF file, got {artifact.format}")
    artifact.validate()
    path = next(iter(artifact.files.values()))
    return str(path)


def _is_snp(ref: str, alt: str) -> bool:
    return len(ref) == 1 and len(alt) == 1 and ref in "ACGT" and alt in "ACGT"


def sample_summary(path: str, max_sites: int = 0) -> dict[str, dict]:
    with open_text(path) as stream:
        _meta, _fmt, samples = read_header(stream)
        rows = {
            name: {"called": 0, "missing": 0, "het": 0, "hom_ref": 0, "hom_alt": 0, "ts": 0, "tv": 0}
            for name in samples
        }
        n_sites = 0
        for fixed, rest in iter_sites(stream):
            if len(fixed) < 8:
                continue
            ref = fixed[3].upper()
            alt_field = fixed[4]
            alts = [a for a in alt_field.split(",") if a and a != "."]
            if not rest:
                continue
            body = rest.split("\t")
            if len(body) < 1 + len(samples):
                continue
            format_keys = body[0].split(":")
            if "GT" not in format_keys:
                continue
            gt_index = format_keys.index("GT")
            n_sites += 1
            for index, name in enumerate(samples):
                values = body[1 + index].split(":")
                gt = values[gt_index] if gt_index < len(values) else ""
                dosage = genotype_dosage(gt, 1)
                entry = rows[name]
                if dosage is None or len(allele_tokens(gt)) < 2:
                    entry["missing"] += 1
                    continue
                entry["called"] += 1
                if dosage == 1:
                    entry["het"] += 1
                elif dosage == 0:
                    entry["hom_ref"] += 1
                elif dosage >= 2:
                    entry["hom_alt"] += 1
                if len(alts) == 1 and _is_snp(ref, alts[0]):
                    if (ref, alts[0]) in TRANSITIONS:
                        entry["ts"] += 1
                    else:
                        entry["tv"] += 1
            if max_sites and n_sites >= max_sites:
                break
    result = {"n_samples": len(samples), "n_sites": n_sites, "samples": rows}
    return result


def allele_tokens(gt: str) -> list[str]:
    if not gt or gt == ".":
        return []
    return gt.replace("|", "/").split("/")


def site_missingness(path: str, max_sites: int = 0) -> list[dict]:
    rows = []
    with open_text(path) as stream:
        _meta, _fmt, samples = read_header(stream)
        n = len(samples)
        for fixed, rest in iter_sites(stream):
            if not rest:
                continue
            body = rest.split("\t")
            if len(body) < 1 + n:
                continue
            format_keys = body[0].split(":")
            if "GT" not in format_keys:
                continue
            gt_index = format_keys.index("GT")
            called = 0
            for index in range(n):
                values = body[1 + index].split(":")
                gt = values[gt_index] if gt_index < len(values) else ""
                tokens = allele_tokens(gt)
                if len(tokens) >= 2 and all(token not in {"", "."} for token in tokens):
                    called += 1
            rows.append(
                {
                    "site": f"{fixed[0]}:{fixed[1]}",
                    "n_called": called,
                    "n_missing": n - called,
                    "call_rate": called / n if n else 0.0,
                }
            )
            if max_sites and len(rows) >= max_sites:
                break
    return rows


def hwe_exact(obs_hets: int, obs_hom1: int, obs_hom2: int) -> float:
    """Two-sided exact HWE test (Wigginton et al. 2005)."""
    if obs_hets < 0 or obs_hom1 < 0 or obs_hom2 < 0:
        raise StepError("hwe: genotype counts must be non-negative")
    if obs_hets == 0 and (obs_hom1 == 0 or obs_hom2 == 0):
        return 1.0
    obs_homc = min(obs_hom1, obs_hom2)
    obs_homr = max(obs_hom1, obs_hom2)
    rare_copies = 2 * obs_homc + obs_hets
    genotypes = obs_hets + obs_homc + obs_homr
    probs = [0.0] * (rare_copies + 1)
    mid = (rare_copies * (2 * genotypes - rare_copies)) // (2 * genotypes)
    if (mid - rare_copies) % 2 != 0:
        mid += 1
    probs[mid] = 1.0
    total = 1.0
    curr_hets = mid
    curr_homr = (rare_copies - mid) // 2
    curr_homc = genotypes - curr_hets - curr_homr
    while curr_hets >= 2:
        value = probs[curr_hets] * curr_hets * (curr_hets - 1) / (
            4.0 * (curr_homr + 1) * (curr_homc + 1)
        )
        probs[curr_hets - 2] = value
        total += value
        curr_homr += 1
        curr_homc += 1
        curr_hets -= 2
    curr_hets = mid
    curr_homr = (rare_copies - mid) // 2
    curr_homc = genotypes - curr_hets - curr_homr
    while curr_hets <= rare_copies - 2:
        value = probs[curr_hets] * 4.0 * curr_homr * curr_homc / (
            (curr_hets + 2) * (curr_hets + 1)
        )
        probs[curr_hets + 2] = value
        total += value
        curr_homr -= 1
        curr_homc -= 1
        curr_hets += 2
    observed = probs[obs_hets] / total
    p = 0.0
    for value in probs:
        value /= total
        if value <= observed + 1e-12:
            p += value
    return min(1.0, p)


def hwe_rows(path: str, max_sites: int = 0) -> list[dict]:
    rows = []
    with open_text(path) as stream:
        _meta, _fmt, samples = read_header(stream)
        for fixed, rest in iter_sites(stream):
            if not rest or len(fixed) < 5:
                continue
            alts = [a for a in fixed[4].split(",") if a and a != "."]
            if len(alts) != 1:
                continue
            body = rest.split("\t")
            if len(body) < 1 + len(samples):
                continue
            keys = body[0].split(":")
            if "GT" not in keys:
                continue
            gt_index = keys.index("GT")
            hom_ref = het = hom_alt = 0
            for index in range(len(samples)):
                values = body[1 + index].split(":")
                gt = values[gt_index] if gt_index < len(values) else ""
                tokens = allele_tokens(gt)
                if len(tokens) != 2 or any(token in {"", "."} for token in tokens):
                    continue
                dosage = (tokens[0] == "1") + (tokens[1] == "1")
                if dosage == 0:
                    hom_ref += 1
                elif dosage == 1:
                    het += 1
                else:
                    hom_alt += 1
            n_called = hom_ref + het + hom_alt
            if n_called == 0:
                continue
            p = hwe_exact(het, hom_ref, hom_alt)
            alt_freq = (2 * hom_alt + het) / (2 * n_called)
            expected_het = 2 * alt_freq * (1 - alt_freq)
            rows.append(
                {
                    "site": f"{fixed[0]}:{fixed[1]}",
                    "n_called": n_called,
                    "obs_het": het,
                    "exp_het": expected_het * n_called,
                    "alt_freq": alt_freq,
                    "hwe_p": p,
                }
            )
            if max_sites and len(rows) >= max_sites:
                break
    return rows
