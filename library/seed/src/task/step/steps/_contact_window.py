"""Bounded Cooler region selection for the existing select and heatmap operators."""
import re


def _bounds(group, region):
    from src.core import StepError
    match = re.fullmatch(r"([^:]+):(\d+)-(\d+)", region or "")
    if not match:
        raise StepError("A contact region must be chrom:start-end (0-based, half-open)")
    chrom, start, end = match[1], int(match[2]), int(match[3])
    names = [value.decode() if isinstance(value, bytes) else str(value) for value in group["chroms/name"][:]]
    if chrom not in names:
        raise StepError(f"Unknown chromosome {chrom!r}")
    index = names.index(chrom)
    if not 0 <= start < end <= int(group["chroms/length"][index]):
        raise StepError("Region exceeds chromosome bounds or is empty")
    offset, stop = map(int, group["indexes/chrom_offset"][index:index + 2])
    def lower_bound(dataset, value, lo, hi, right=False):
        while lo < hi:
            mid = (lo + hi) // 2
            if dataset[mid] < value or (right and dataset[mid] == value):
                lo = mid + 1
            else:
                hi = mid
        return lo
    left = lower_bound(group["bins/end"], start, offset, stop, right=True)
    right = lower_bound(group["bins/start"], end, offset, stop)
    return left, right, chrom


def estimate_window(artifact, params):
    import h5py
    from src.core import StepError
    if artifact.format != "cool" or params.get("source_type") != "contact_matrix":
        raise StepError("File region selection requires source_type=contact_matrix and a Cooler file")
    with h5py.File(artifact.files["data"], "r") as handle:
        group = handle[artifact.info.get("group", "/")]
        a = _bounds(group, params.get("region")); b = _bounds(group, params.get("region2") or params.get("region"))
        cells = (a[1] - a[0]) * (b[1] - b[0])
        metadata = (a[1] - a[0] + b[1] - b[0]) * 512
        return cells * 24 + metadata + 2 * 1024**2, cells * 8 + metadata


def select_window(artifact, params, *, ctx=None):
    import h5py
    import numpy as np
    from src.core import Form, StepError
    from src.task.memory.config import MemoryBudgetError
    artifact.validate()
    workspace, output = estimate_window(artifact, params)
    if ctx and ctx.memory and workspace + output > ctx.memory.config.budget_bytes:
        raise MemoryBudgetError("Contact window exceeds the run budget; choose a smaller region or coarser resolution")
    with h5py.File(artifact.files["data"], "r") as handle:
        group = handle[artifact.info.get("group", "/")]
        left = _bounds(group, params["region"])
        right = _bounds(group, params.get("region2") or params["region"])
        result = np.zeros((left[1] - left[0], right[1] - right[0]), dtype=np.float64)
        symmetric = group.attrs.get("storage-mode", "symmetric-upper") == "symmetric-upper"
        preferred = ctx.memory.config.chunk_bytes if ctx and ctx.memory else 65536
        chunk = max(1, min(preferred, 1024**2) // 48)
        offsets = group["indexes/bin1_offset"]
        def copy_rows(rows, cols, transpose=False):
            for row in range(rows[0], rows[1]):
                if ctx and (ctx.task_dir / "cancel.requested").exists():
                    raise StepError("Run cancelled by user")
                lo, hi = map(int, offsets[row:row + 2])
                for begin in range(lo, hi, chunk):
                    end = min(hi, begin + chunk)
                    columns = group["pixels/bin2_id"][begin:end]
                    values = group["pixels/count"][begin:end]
                    mask = (columns >= cols[0]) & (columns < cols[1])
                    if transpose:
                        mask &= columns != row  # do not double-count diagonal
                        np.add.at(result, (columns[mask] - cols[0], np.full(mask.sum(), row - rows[0])), values[mask])
                    else:
                        np.add.at(result, (np.full(mask.sum(), row - rows[0]), columns[mask] - cols[0]), values[mask])
        copy_rows(left, right)
        if symmetric:
            copy_rows(right, left, True)
        balanced = params.get("balanced", True)
        if balanced:
            name = params.get("weight_name", "weight")
            if name not in group["bins"]:
                raise StepError(f"No balancing weight {name!r}; choose raw counts or balance the map first")
            weight = group["bins"][name]
            if weight.attrs.get("divisive_weights", False):
                raise StepError("Divisive balancing weights are not supported by this selection adapter")
            result *= weight[left[0]:left[1]][:, None]
            result *= weight[right[0]:right[1]][None, :]
        labels, info = {}, {"representation": "contact_window", "missing_code": np.nan,
                            "region": params["region"], "region2": params.get("region2") or params["region"],
                            "balanced": balanced, "resolution": artifact.info.get("resolution"),
                            "assembly": artifact.info.get("assembly", "unknown")}
        parallel = {}
        for axis, bounds in (("bin1", left), ("bin2", right)):
            start = group["bins/start"][bounds[0]:bounds[1]]
            end = group["bins/end"][bounds[0]:bounds[1]]
            labels[axis] = {f"{bounds[2]}:{int(a)}-{int(b)}": i for i, (a, b) in enumerate(zip(start, end))}
            info[axis + "_chrom"] = [bounds[2]] * len(start)
            info[axis + "_start"], info[axis + "_end"] = start, end
            parallel[axis] = [axis + suffix for suffix in ("_chrom", "_start", "_end")]
        return Form(result, ["bin1", "bin2"], labels, info, parallel)
