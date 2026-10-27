"""Streaming sequence input and small file descriptors (no discovery-time I/O)."""
import bz2
import gzip
import lzma
from itertools import zip_longest
from pathlib import Path


def open_text(path):
    path = Path(path)
    opener = {".gz": gzip.open, ".bz2": bz2.open, ".xz": lzma.open}.get(path.suffix.lower(), open)
    return opener(path, "rt", encoding="ascii", newline=None)


def fastq_records(path, *, record_bytes=1024 * 1024, phred_offset=33):
    """Yield complete records, supporting wrapped FASTQ and gzip/bzip2/xz.

    A single record must fit the caller's buffer. This is a resource admission
    limit, not a limit on the total input file or number of reads.
    """
    from src.core import ReaderError
    if phred_offset not in (33, 64) or record_bytes < 1:
        raise ReaderError("FASTQ requires phred_offset 33/64 and a positive record buffer")
    with open_text(path) as stream:
        def line():
            text = stream.readline(record_bytes + 2)
            if len(text.rstrip("\r\n")) > record_bytes:
                raise ReaderError("FASTQ record exceeds the configured streaming buffer")
            return text.rstrip("\r\n") if text else None
        while True:
            header = line()
            if header is None:
                return
            if not header.startswith("@") or not header[1:].strip():
                raise ReaderError("FASTQ record must begin with a nonempty @ identifier")
            parts, length = bytearray(), 0
            while True:
                value = line()
                if value is None:
                    raise ReaderError("Truncated FASTQ sequence")
                if value.startswith("+"):
                    break
                if not value:
                    raise ReaderError("Empty FASTQ sequence line")
                length += len(value)
                if length > record_bytes:
                    raise ReaderError("FASTQ record exceeds the configured streaming buffer")
                parts.extend(value.upper().encode('ascii'))
            sequence = parts.decode('ascii')
            if not sequence or any(ch not in "ACGTUNRYKMSWBDHV" for ch in sequence):
                raise ReaderError("FASTQ contains an empty or invalid nucleotide sequence")
            parts, length = bytearray(), 0
            while length < len(sequence):
                value = line()
                if value is None:
                    raise ReaderError("Truncated FASTQ quality string")
                if not value:
                    raise ReaderError("Empty FASTQ quality line")
                if any(not phred_offset <= ord(ch) <= 126 for ch in value):
                    raise ReaderError("FASTQ quality is outside the declared Phred encoding")
                parts.extend(value.encode('ascii'))
                length += len(value)
            if length != len(sequence):
                raise ReaderError("FASTQ sequence and quality lengths differ")
            yield header[1:].split()[0], sequence, parts.decode('ascii')


def fastq_summary(files, *, phred_offset=33, record_bytes=1024 * 1024, cancelled=None):
    """Exact bounded-memory per-mate QC, retaining R1/R2 pairing semantics."""
    from src.core import ReaderError
    roles = [key for key in ("r1", "r2") if key in files]
    if not roles:
        raise ReaderError("FASTQ artifact has no r1 file")
    result = {role: {"reads": 0, "bases": 0, "gc_bases": 0, "n_bases": 0,
                     "q20_bases": 0, "q30_bases": 0, "quality_sum": 0,
                     "min_length": None, "max_length": 0} for role in roles}
    streams = [fastq_records(files[role], phred_offset=phred_offset, record_bytes=record_bytes) for role in roles]
    def pair_id(identifier):
        return identifier[:-2] if identifier.endswith(("/1", "/2")) else identifier
    try:
        for index, records in enumerate(zip_longest(*streams)):
            if cancelled and index % 1024 == 0:
                if cancelled():
                    raise ReaderError("Run cancelled by user")
            if any(record is None for record in records):
                raise ReaderError("Paired FASTQ files have different read counts")
            if len(records) == 2 and pair_id(records[0][0]) != pair_id(records[1][0]):
                raise ReaderError(f"Paired FASTQ identifiers disagree at read {index + 1}")
            for role, (_, sequence, quality) in zip(roles, records):
                item = result[role]
                item["reads"] += 1
                item["bases"] += len(sequence)
                item["gc_bases"] += sequence.count("G") + sequence.count("C")
                item["n_bases"] += sequence.count("N")
                item["min_length"] = min(item["min_length"] or len(sequence), len(sequence))
                item["max_length"] = max(item["max_length"], len(sequence))
                for ch in quality:
                    score = ord(ch) - phred_offset
                    item["quality_sum"] += score
                    item["q20_bases"] += score >= 20
                    item["q30_bases"] += score >= 30
    finally:
        for stream in streams:
            stream.close()
    if not result[roles[0]]["reads"]:
        raise ReaderError("FASTQ contains no reads")
    for item in result.values():
        item.update(mean_length=item["bases"] / item["reads"],
                    gc=item["gc_bases"] / item["bases"], n_ratio=item["n_bases"] / item["bases"],
                    mean_quality=item["quality_sum"] / item["bases"],
                    q20=item["q20_bases"] / item["bases"], q30=item["q30_bases"] / item["bases"])
    return result


def read_file_source(path, format, **args):
    from src.core.files import FileArtifact
    from src.core import ReaderError
    path = Path(path).resolve()
    if format == "alignment":
        format = path.suffix.lower().lstrip(".")
    files, info = {"data": str(path)}, {}
    if format == "fastq":
        files = {"r1": str(path)}
        if args.get("mate_path"):
            files["r2"] = str((path.parent / args["mate_path"]).resolve())
        info["phred_offset"] = args.get("phred_offset", 33)
    elif format == "cool":
        import h5py
        with h5py.File(path, "r") as handle:
            if "resolutions" in handle:
                resolutions = sorted(int(key) for key in handle["resolutions"])
                resolution = args.get("resolution")
                if resolution not in resolutions:
                    raise ReaderError(f"Choose a resolution from {resolutions} for this .mcool")
                group = "/resolutions/" + str(resolution)
            else:
                group = "/"
            data = handle[group]
            if not all(key in data for key in ("chroms", "bins", "pixels", "indexes")):
                raise ReaderError("File does not contain a Cooler contact matrix")
            storage = data.attrs.get("storage-mode", "symmetric-upper")
            if storage not in ("symmetric-upper", "square"):
                raise ReaderError("Unsupported Cooler storage-mode")
            info = {"group": group, "resolution": int(data.attrs.get("bin-size", 0) or 0),
                    "assembly": str(data.attrs.get("genome-assembly", data.attrs.get("assembly", "unknown"))),
                    "storage_mode": storage, "balanced": "weight" in data["bins"],
                    "nbins": len(data["bins/start"]), "nnz": len(data["pixels/count"])}
            if args.get("resolution") and info["resolution"] != args["resolution"]:
                raise ReaderError("Requested resolution differs from Cooler bin size")
    artifact = FileArtifact(format, files, info)
    artifact.validate()
    return artifact
