"""Hi-C adapters. Scientific algorithms belong to BWA/open2c, not BioPipe."""
from pathlib import Path
import json

from biopipe.tool_runner import ToolRunner


def input_path(ctx, value):
    path = Path(value)
    path = path if path.is_absolute() else ctx.task_dir / path
    if not path.is_file():
        raise ValueError(f"Input file does not exist: {path}")
    return path.resolve()


def identity(path):
    path = Path(path).resolve()
    stat = path.stat()
    return {"path": str(path), "size": stat.st_size, "mtime_ns": stat.st_mtime_ns}


def _result(runner, files, format, info, summary):
    provenance = runner.directory / "provenance.json"
    provenance.write_text(json.dumps({"parameters": runner.params, "tools": runner.versions,
                                     "info": info, "summary": summary}, indent=2), encoding="utf-8")
    return {"files": {**{k: str(v) for k, v in files.items()}, "provenance": str(provenance)},
            "format": format, "info": info, "summary": summary}


def align_reads(ctx, files, params):
    from src.reader.readers._sequencing import fastq_summary
    if not files.get("r2"):
        raise ValueError("Hi-C alignment requires paired FASTQ files (mate_path)")
    r = ToolRunner(ctx, params)
    r.require("bwa", "samtools")
    reference = input_path(ctx, params["reference_fasta"])
    stamp = identity(reference)
    # BWA indexes are private to the run; never write beside a user's reference.
    ref = r.directory / "reference.fa"
    r.checkpoint(reference.stat().st_size)
    with reference.open("rb") as src, ref.open("wb") as dst:
        while block := src.read(1024**2):
            r.checkpoint(len(block))
            dst.write(block)
    if identity(reference) != stamp:
        raise ValueError("Reference changed while preparing the run")
    qc = fastq_summary(files, record_bytes=int(params.get("record_buffer_mb", 1) * 1024**2),
                       phred_offset=params.get("phred_offset", 33),
                       cancelled=r.checkpoint)
    r.command("bwa", "index", r.path(ref))
    sam, bam = r.directory / "alignment.sam", r.directory / "alignment.bam"
    r.command("bwa", "mem", "-5SP", "-t", r.threads, r.path(ref), r.path(files["r1"]), r.path(files["r2"]), stdout=sam)
    r.command("samtools", "view", "-@", r.threads, "-b", "-o", r.path(bam), r.path(sam))
    sam.unlink()
    return _result(r, {"data": bam}, "bam", {"assembly": params.get("assembly", "unknown"),
        "reference": identity(reference), "alignment_mode": "bwa-mem-5SP", "sort_order": "query-grouped"}, {"qc": qc})


def chrom_sizes(path):
    result = {}
    with Path(path).open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip() or line.startswith("#"): continue
            chrom, size = line.split()[:2]
            if chrom in result or int(size) <= 0:
                raise ValueError("Chromosome sizes must contain unique names and positive lengths")
            result[chrom] = int(size)
    if not result: raise ValueError("Empty chromosome sizes file")
    return result


def canonical_pairs(source, target, sizes, *, min_mapq=0, pair_types=("UU",), cancelled=lambda: False):
    """Stream validated 1-based contacts into the standard eight-column schema."""
    from src.reader.readers._sequencing import open_text
    names = ["readID", "chrom1", "pos1", "chrom2", "pos2", "strand1", "strand2", "pair_type"]
    counts = {"input": 0, "retained": 0, "filtered": 0}
    columns = None
    rank = {name: i for i, name in enumerate(sizes)}
    with open_text(source) as src, Path(target).open("w", encoding="utf-8", newline="\n") as dst:
        dst.write("## pairs format v1.0.0\n#shape: upper triangle\n")
        for chrom, length in sizes.items(): dst.write(f"#chromsize: {chrom} {length}\n")
        dst.write("#columns: " + " ".join(names) + "\n")
        for line in src:
            if line.startswith("#columns:"):
                columns = line.split(":", 1)[1].split()
                if len(columns) != len(set(columns)) or not set(names).issubset(columns):
                    raise ValueError("pairs #columns must declare the standard eight fields without duplicates")
                if min_mapq and not {"mapq1", "mapq2"}.issubset(columns):
                    raise ValueError("pairs has no mapq1/mapq2: use min_mapq=0 only for already-filtered input")
                continue
            if line.startswith("#") or not line.strip(): continue
            if columns is None: raise ValueError("pairs is missing its #columns header")
            if counts["input"] % 4096 == 0 and cancelled(): raise RuntimeError("Run cancelled by user")
            values = line.rstrip("\r\n").split("\t")
            if len(values) != len(columns): raise ValueError("pairs row does not match #columns")
            row = dict(zip(columns, values))
            counts["input"] += 1
            if row["pair_type"] not in pair_types or (min_mapq and min(int(row["mapq1"]), int(row["mapq2"])) < min_mapq):
                counts["filtered"] += 1
                continue
            for side in ("1", "2"):
                if row["chrom" + side] not in sizes or not 1 <= int(row["pos" + side]) <= sizes[row["chrom" + side]]:
                    raise ValueError("Contact coordinate is outside the supplied chromosome sizes (pairs is 1-based)")
                if row["strand" + side] not in ("+", "-"): raise ValueError("Invalid contact strand")
            if (rank[row["chrom1"]], int(row["pos1"])) > (rank[row["chrom2"]], int(row["pos2"])):
                for field in ("chrom", "pos", "strand"):
                    row[field + "1"], row[field + "2"] = row[field + "2"], row[field + "1"]
                row["pair_type"] = row["pair_type"][::-1]
            dst.write("\t".join(row[n] for n in names) + "\n")
            counts["retained"] += 1
    if columns is None: raise ValueError("pairs is missing its #columns header")
    if not counts["retained"]: raise ValueError("No contacts remain after pair-type/MAPQ filtering")
    return counts


def build_contacts(ctx, files, format, params):
    r = ToolRunner(ctx, params)
    r.require("pairtools", "cooler")
    chroms = input_path(ctx, params["chromsizes"])
    sizes = chrom_sizes(chroms)
    source = input_path(ctx, files["data"])
    parsed = source
    min_mapq = int(params.get("min_mapq", 30))
    if format in ("bam", "sam"):
        r.require("samtools")
        collated, sam = r.directory / "name-sorted.bam", r.directory / "name-sorted.sam"
        r.command("samtools", "sort", "-n", "-@", r.threads, "-m", f"{max(1, r.memory_bytes // (r.threads + 1) // 1024**2)}M",
                  "-T", r.path(r.scratch / "sort"), "-o", r.path(collated), r.path(source))
        r.command("samtools", "view", "-h", "-o", r.path(sam), r.path(collated))
        parsed = r.directory / "parsed.pairs"
        r.command("pairtools", "parse", "--chroms-path", r.path(chroms), "--min-mapq", min_mapq,
                  "--walks-policy", params.get("walks_policy", "5unique"), "--drop-sam", "--add-columns", "mapq",
                  "--output", r.path(parsed), r.path(sam))
        sam.unlink(); collated.unlink()
    elif format != "pairs":
        raise ValueError("build_contacts accepts BAM, SAM, or pairs")
    canonical = r.directory / "canonical.pairs"
    stats = canonical_pairs(parsed, canonical, sizes, min_mapq=min_mapq, pair_types=params.get("pair_types", ["UU"]),
                            cancelled=r.checkpoint)
    sorted_pairs, deduped = r.directory / "sorted.pairs", r.directory / "contacts.pairs"
    r.command("pairtools", "sort", "--nproc", r.threads, "--memory", f"{max(1,r.memory_bytes//1024**2)}M",
              "--tmpdir", r.path(r.scratch), "--output", r.path(sorted_pairs), r.path(canonical))
    canonical.unlink()
    qc = r.directory / "dedup.stats"
    r.command("pairtools", "dedup", "--max-mismatch", params.get("max_mismatch", 3),
              "--chunksize", max(100, r.memory_bytes // 4096), "--output-stats", r.path(qc),
              "--output", r.path(deduped), r.path(sorted_pairs))
    sorted_pairs.unlink()
    cool = r.directory / "contacts.cool"
    binsize = int(params.get("binsize", 10000))
    r.command("cooler", "cload", "pairs", "-c1", 2, "-p1", 3, "-c2", 4, "-p2", 5,
              "--chunksize", max(1, r.memory_bytes // 512), "--temp-dir", r.path(r.scratch),
              r.path(chroms) + ":" + str(binsize), r.path(deduped), r.path(cool))
    if params.get("balance", True):
        r.command("cooler", "balance", "--nproc", r.threads, "--chunksize", max(1, r.memory_bytes // (r.threads * 128)),
                  "--ignore-diags", params.get("ignore_diags", 2), "--convergence-policy", "error", r.path(cool))
    outputs = {"data": cool, "pairs": deduped, "qc": qc}
    resolutions = sorted(set(params.get("resolutions", [])))
    if resolutions:
        if any(n < binsize or n % binsize for n in resolutions):
            raise ValueError("Multiresolution bins must be positive multiples of binsize")
        multi = r.directory / "contacts.mcool"
        r.command("cooler", "zoomify", "--nproc", r.threads, "--chunksize", max(1,r.memory_bytes//128),
                  "--resolutions", ",".join(map(str, sorted({binsize, *resolutions}))), "--out", r.path(multi), r.path(cool))
        # Keep the raw and balanced base resolution as the primary artifact.
        outputs["multiresolution"] = multi
    return _result(r, outputs, "cool", {"group": "/", "resolution": binsize, "assembly": params.get("assembly", "unknown"),
                   "balanced": params.get("balance", True), "chromsizes": identity(chroms)}, stats)


def analyze_contacts(ctx, files, params, auxiliaries):
    r = ToolRunner(ctx, params)
    r.require("cooltools")
    matrix = input_path(ctx, files["data"])
    from src.reader.readers._sequencing import read_file_source
    artifact = read_file_source(matrix, "cool", resolution=params.get("resolution"))
    group = params.get("group") or artifact.info.get("group", "/")
    uri = r.path(matrix) + "::" + group
    resolution = artifact.info["resolution"]
    if not resolution: raise ValueError("Hi-C analysis requires a fixed bin size")
    weight = params.get("weight_name", "weight")
    view = input_path(ctx, params["view"]) if params.get("view") else None
    provenance = {"matrix": identity(matrix), "group": group, "resolution": resolution,
                  "weight_name": weight, "view": identity(view) if view else None,
                  "ignore_diags": params.get("ignore_diags", 2)}
    common = ["--clr-weight-name", weight, "--ignore-diags", params.get("ignore_diags", 2)]
    view_args = ["--view", r.path(view)] if view else []
    chunk = max(1, r.memory_bytes // (r.threads * 128))
    method = params.get("method", "expected")
    out = r.directory / (method + ".tsv")
    expected = None
    if method in ("loops", "pileup"):
        for aux in auxiliaries:
            if aux.get("info", {}).get("representation") != "hic_expected": continue
            if aux["info"].get("hic_provenance") != provenance:
                raise ValueError("Expected table must match matrix, resolution, balancing, view, and ignored diagonals")
            expected = input_path(ctx, aux["files"]["table"])
        if expected is None:
            expected = r.directory / "expected.tsv"
            r.command("cooltools", "expected-cis", uri, *common, *view_args, "--nproc", r.threads,
                      "--chunksize", chunk, "--output", r.path(expected))
    if method == "expected":
        r.command("cooltools", "expected-cis", uri, *common, *view_args, "--nproc", r.threads,
                  "--chunksize", chunk, "--output", r.path(out))
    elif method == "compartments":
        _check_dense_region_budget(artifact, view, r.memory_bytes)
        prefix = r.directory / "compartments"
        phase = ["--phasing-track", r.path(input_path(ctx, params["phasing_track"]))] if params.get("phasing_track") else []
        r.command("cooltools", "eigs-cis", uri, *common, *view_args, *phase,
                  "--n-eigs", params.get("n_eigs", 3), "--out-prefix", r.path(prefix))
        out = Path(str(prefix) + ".cis.vecs.tsv")
    elif method == "insulation":
        windows = params.get("windows", [100000, 250000, 500000])
        if not windows or any(w <= 0 or w % resolution for w in windows):
            raise ValueError("Insulation windows must be positive multiples of the matrix resolution")
        r.command("cooltools", "insulation", uri, *windows, *common, *view_args,
                  "--nproc", r.threads, "--chunksize", chunk, "--output", r.path(out))
    elif method == "loops":
        tile_bins = max(16, int((r.memory_bytes / (64 * r.threads)) ** .5))
        r.command("cooltools", "dots", uri, r.path(expected), "--clr-weight-name", weight, *view_args,
                  "--nproc", r.threads, "--tile-size", tile_bins * resolution,
                  "--max-loci-separation", params.get("max_loci_separation", 2000000), "--output", r.path(out))
    elif method == "pileup":
        out = _pileup(r, uri, expected, common, view_args, resolution)
    else:
        raise ValueError("Unknown Hi-C analysis method: " + method)
    info = {"representation": "hic_" + method, "hic_provenance": provenance,
            "orientation": ("phased" if params.get("phasing_track") else "unoriented") if method == "compartments" else None}
    return _result(r, {"matrix" if method == "pileup" else "table": out}, "npz" if method == "pileup" else "tsv", info, {"method": method})


def _check_dense_region_budget(artifact, view, budget):
    import h5py
    with h5py.File(artifact.files["data"], "r") as handle:
        group = handle[artifact.info.get("group", "/")]
        sizes = group["chroms/length"][:]
    if view:
        sizes = []
        with view.open(encoding="utf-8") as handle:
            for line in handle:
                if not line.strip() or line.startswith("#"): continue
                fields = line.split(); sizes.append(int(fields[2]) - int(fields[1]))
    n = max((int(size) // artifact.info["resolution"] + 1 for size in sizes), default=0)
    if n * n * 64 > budget:
        raise ValueError("Compartment eigendecomposition exceeds memory_mb; use coarser bins, a smaller view, or a larger admitted workspace")


def _pileup(r, uri, expected, common, view_args, resolution):
    """Bound snippet stacks by batching features; aggregate with per-pixel counts."""
    import numpy as np
    features = input_path(r.ctx, r.params.get("features", ""))
    flank = int(r.params.get("flank", 100000))
    width = 2 * (flank // resolution) + 1
    batch_size = max(1, r.memory_bytes // max(1, width * width * 64))
    if width * width * 64 > r.memory_bytes:
        raise ValueError("Pileup window exceeds memory_mb; reduce flank or use coarser bins")
    total = np.zeros((width, width)); count = np.zeros((width, width), dtype=np.int64)
    from itertools import islice
    with features.open(encoding="utf-8") as handle:
        records = (line for line in handle if line.strip() and not line.startswith("#"))
        while batch := list(islice(records, batch_size)):
            piece, target = r.scratch / "features.bed", r.scratch / "snips.npz"
            piece.write_text("".join(batch), encoding="utf-8")
            r.command("cooltools", "pileup", uri, r.path(piece), *common, *view_args,
                      "--expected", r.path(expected), "--flank", flank, "--features-format", r.params.get("features_format", "BEDPE"),
                      "--nproc", 1, "--store-snips", "--out", r.path(target))
            with np.load(target, allow_pickle=False) as data:
                stack = data["stack"]
                if stack.shape != (len(batch), width, width):
                    raise ValueError("Unexpected cooltools snippet dimensions")
                valid = np.isfinite(stack)
                total += np.sum(stack, axis=0, where=valid, initial=0)
                count += valid.sum(axis=0)
            target.unlink()
    if not count.any(): raise ValueError("No valid pileup pixels; check features, view and balancing")
    out = r.directory / "pileup.npz"
    result = np.divide(total, count, out=np.full_like(total, np.nan), where=count > 0)
    np.savez(out, pileup=result, valid_counts=count)
    return out
