from __future__ import annotations

from dataclasses import dataclass, field
import math
import os

from src.core import ContextError, ManifestError

AUTO_BUDGET_FRACTION = 0.90


class MemoryBudgetError(ContextError):
    """The declared execution contract cannot currently fit the budget."""


class DiskBudgetError(ContextError):
    """A spill cannot be committed within the run's disk quota."""


@dataclass
class MemoryConfig:
    enabled: bool = False
    budget_bytes: int = 0
    process_limit_bytes: int | None = None
    disk_limit_bytes: int | None = None
    target_fraction: float = 0.70
    spill_fraction: float = 0.85
    auto_spill: bool = True
    poll_seconds: float = 0.1
    chunk_bytes: int = 4 * 1024**2
    io_buffer_bytes: int = 64 * 1024
    cache_dir: str | None = None
    keep: list[str] = field(default_factory=list)
    profiles: dict = field(default_factory=dict)
    available_at_start_bytes: int | None = None

    @classmethod
    def parse(cls, manifest: dict, *, detect_available: bool = True) -> "MemoryConfig":
        runtime = manifest.get("runtime", {})
        if not isinstance(runtime, dict):
            raise ManifestError("runtime must be a mapping")
        raw = runtime.get("memory", {})
        if not isinstance(raw, dict):
            raise ManifestError("runtime.memory must be a mapping")
        allowed = {"enabled", "budget_mb", "process_limit_mb", "disk_limit_mb",
                   "target_fraction", "spill_fraction", "auto_spill", "poll_ms",
                   "chunk_mb", "io_buffer_kb", "cache_dir", "keep", "profiles"}
        unknown = set(raw) - allowed
        if unknown:
            raise ManifestError(f"Unknown runtime.memory options: {sorted(unknown)}")
        enabled = raw.get("enabled", bool(raw))
        for key, val in (("enabled", enabled), ("auto_spill", raw.get("auto_spill", True))):
            if not isinstance(val, bool):
                raise ManifestError(f"runtime.memory.{key} must be boolean")
        if not enabled:
            return cls()

        def positive(key, default, scale=1):
            value = raw.get(key, default)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
                raise ManifestError(f"runtime.memory.{key} must be a finite positive number")
            return max(1, int(value * scale))

        # Validation has no allocation budget until execution takes its snapshot.
        automatic = 0
        available_at_start = None
        if detect_available and "budget_mb" not in raw:
            try:
                from .system import available_memory
                available_at_start = available_memory()
            except (ImportError, OSError, RuntimeError) as error:
                raise ManifestError("Cannot scan available memory for an automatic budget; "
                                    "ensure psutil is available or set runtime.memory.budget_mb explicitly") from error
            automatic = int(available_at_start * AUTO_BUDGET_FRACTION)
            if automatic <= 0:
                raise ManifestError("No available memory for an automatic budget; retry when memory is available")
        budget = positive("budget_mb", 0, 1024**2) if "budget_mb" in raw else automatic
        if 'budget_mb' in raw and os.environ.get('BIOPIPE_AVAILABLE_AT_START_BYTES'):
            # Studio/SSH worker handoff: preserve the host's original audit
            # snapshot without a second scan or a second 90% allocation.
            available_at_start = int(os.environ['BIOPIPE_AVAILABLE_AT_START_BYTES'])
        target, spill = raw.get("target_fraction", .70), raw.get("spill_fraction", .85)
        if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in (target, spill)) or not 0 < target < spill <= 1:
            raise ManifestError("Require 0 < target_fraction < spill_fraction <= 1")
        keep = raw.get("keep", [])
        if not isinstance(keep, list) or any(not isinstance(n, str) for n in keep):
            raise ManifestError("runtime.memory.keep must be a list of form names")
        profiles = raw.get("profiles", {})
        if not isinstance(profiles, dict):
            raise ManifestError("runtime.memory.profiles must be a mapping")
        for name, profile in profiles.items():
            if not isinstance(profile, dict) or set(profile) - {"workspace_mb", "output_mb"}:
                raise ManifestError(f"Invalid memory profile for {name!r}")
            for key, value in profile.items():
                if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
                    raise ManifestError(f"Profile {name}.{key} must be finite and nonnegative")
        cache_dir = raw.get("cache_dir")
        if cache_dir is not None and (not isinstance(cache_dir, str) or not cache_dir):
            raise ManifestError("cache_dir must be a nonempty path string")
        return cls(True, budget,
                   positive("process_limit_mb", 1, 1024**2) if "process_limit_mb" in raw else None,
                   positive("disk_limit_mb", 1, 1024**2) if "disk_limit_mb" in raw else None,
                   float(target), float(spill), raw.get("auto_spill", True),
                   positive("poll_ms", 100) / 1000,
                   positive("chunk_mb", 4, 1024**2), positive("io_buffer_kb", 64, 1024),
                   cache_dir, keep, profiles, available_at_start)
