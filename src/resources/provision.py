"""Provisioning helpers for Operon large resources.

Design goals: downloads must survive slow or unstable links (resume, retries,
read timeouts), must never leave a half-written file in place (atomic rename),
must be verifiable (size and SHA-256), and must be able to reuse a local
staging directory when the server has a slow uplink (``--from-dir``).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

CHUNK = 4 * 1024 * 1024
DEFAULT_RETRIES = 3


class ProvisionError(RuntimeError):
    """Raised when provisioning cannot proceed (lock contention)."""


def sha256_file(path: Path) -> str:
    """Return the SHA-256 hex digest of a file."""

    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while True:
            block = handle.read(CHUNK)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def verify_file(path: Path, *, sha256: str = "", size: int = 0) -> tuple[bool, str]:
    """Check that a file exists and matches the expected size and digest."""

    if not path.is_file():
        return False, "missing"
    actual_size = path.stat().st_size
    if size and actual_size != size:
        return False, f"size {actual_size} != {size}"
    if sha256 and sha256_file(path) != sha256:
        return False, "sha256 mismatch"
    return True, "ok"


def rewrite_url(url: str, *, mirrors: list[str] = (), rewrites: list[tuple[str, str]] = ()) -> str:
    """Apply mirror prefixes and explicit ``old=new`` rewrites to a URL."""

    for old, new in rewrites:
        if old and url.startswith(old):
            return new + url[len(old):]
    for mirror in mirrors:
        for prefix in ("https://huggingface.co/", "https://www.huggingface.co/"):
            if url.startswith(prefix) and mirror:
                return mirror.rstrip("/") + "/" + url[len(prefix):]
    return url


def download(
    url: str,
    dest: Path,
    *,
    sha256: str = "",
    size: int = 0,
    timeout: int = 60,
    retries: int = DEFAULT_RETRIES,
) -> Path:
    """Download with resume, retries and an atomic rename."""

    dest.parent.mkdir(parents=True, exist_ok=True)
    partial = dest.with_name(dest.name + ".part")
    last_error: Exception | None = None
    for attempt in range(1, max(retries, 1) + 1):
        try:
            offset = partial.stat().st_size if partial.is_file() else 0
            headers = {"Range": f"bytes={offset}-"} if offset else {}
            request = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(request, timeout=timeout) as response:
                status = response.getcode()
                if status == 206:
                    matched = re.fullmatch(r'bytes (\d+)-(\d+)/(\d+|\*)', response.headers.get('Content-Range', ''))
                    if not matched or int(matched[1]) != offset:
                        raise ProvisionError(f'invalid resume range for {dest.name}')
                    expected = int(matched[2]) - offset + 1
                    mode = 'ab' if offset else 'wb'
                else:
                    # Servers may ignore Range and return the complete file.
                    mode = 'wb'
                    expected = int(response.headers.get('Content-Length', -1))
                received = 0
                with open(partial, mode) as handle:
                    while True:
                        block = response.read(CHUNK)
                        if not block:
                            break
                        handle.write(block)
                        received += len(block)
                if expected >= 0 and received != expected:
                    raise OSError(f'incomplete response for {dest.name}: {received} != {expected}')
                if status == 206 and matched[3] != '*' and partial.stat().st_size != int(matched[3]):
                    raise OSError(f'incomplete range response for {dest.name}')
            valid, reason = verify_file(partial, sha256=sha256, size=size)
            if not valid:
                partial.unlink(missing_ok=True)
                label = 'checksum mismatch' if reason == 'sha256 mismatch' else 'verification failed'
                raise ProvisionError(f"{label} for {dest.name}: {reason}")
            os.replace(partial, dest)
            return dest
        except ProvisionError:
            raise
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            if attempt < retries:
                time.sleep(min(2 ** attempt, 30))
                continue
    raise ProvisionError(f"download failed for {url}: {last_error}")


@dataclass
class ProvisionResult:
    resource: str
    root: Path
    downloaded: list[str] = field(default_factory=list)
    copied: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)

    def as_dict(self, *, plan: bool = False) -> dict:
        pending = bool(self.missing or self.failed)
        return {
            "resource": self.resource,
            "root": str(self.root),
            "downloaded": self.downloaded,
            "copied": self.copied,
            "skipped": self.skipped,
            "missing": self.missing,
            "failed": self.failed,
            "status": "incomplete" if pending else ("planned" if plan else "ok"),
        }


def _copy_from_source(source: Path, target: Path, sha256: str, size: int = 0) -> bool:
    """Atomic copy from a local staging directory."""

    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_name(target.name + ".part")
    shutil.copyfile(source, partial)
    if not verify_file(partial, sha256=sha256, size=size)[0]:
        partial.unlink(missing_ok=True)
        return False
    os.replace(partial, target)
    return True


def provision_one(
    root: Path,
    entry: dict,
    *,
    files: list[str] | None = None,
    offline: bool = False,
    timeout: int = 60,
    retries: int = DEFAULT_RETRIES,
    source_dir: Path | None = None,
    mirrors: list[str] = (),
    rewrites: list[tuple[str, str]] = (),
    plan: bool = False,
) -> ProvisionResult:
    """Provision every declared file of one manifest entry into ``root``."""

    result = ProvisionResult(resource=str(entry.get("id", "?")), root=root)
    downloads = entry.get("downloads") or {}
    checksums = entry.get("sha256") or {}
    sizes = entry.get("sizes") or {}
    for name in entry.get("files", []):
        if files and name not in files:
            continue
        target = root / name
        stamp = checksums.get(name, "")
        size = int(sizes.get(name, 0))
        ok, reason = verify_file(target, sha256=stamp, size=size)
        if ok:
            result.skipped.append(name)
            continue
        if plan:
            result.missing.append(f"{name} (would fetch)")
            continue
        source = (source_dir / name) if source_dir else None
        if source is not None and source.is_file():
            if _copy_from_source(source, target, stamp, size):
                result.copied.append(name)
                continue
            result.failed.append(f"{name}: checksum mismatch or size mismatch in {source}")
            continue
        url = downloads.get(name, "")
        if offline or not url:
            result.missing.append(f"{name} ({reason})" if not url else name)
            continue
        try:
            download(rewrite_url(url, mirrors=mirrors, rewrites=rewrites), target, sha256=stamp, size=size, timeout=timeout, retries=retries)
            result.downloaded.append(name)
        except ProvisionError as exc:
            result.failed.append(f"{name}: {exc}")
    return result


def provision(
    manifest: dict,
    root: Path,
    *,
    only: list[str] | None = None,
    files: list[str] | None = None,
    offline: bool = False,
    timeout: int = 60,
    retries: int = DEFAULT_RETRIES,
    source_dir: str | Path | None = None,
    mirrors: list[str] = (),
    rewrites: list[tuple[str, str]] = (),
    plan: bool = False,
    jobs: int = 1,
    lock_timeout: float = 30.0,
) -> dict:
    """Provision selected resources under a lock file, optionally in parallel."""

    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    source = Path(source_dir) if source_dir else None
    lock = root / ".operon-provision.lock"
    deadline = time.monotonic() + lock_timeout
    while True:
        try:
            handle = open(lock, "x")
            break
        except FileExistsError:
            if time.monotonic() > deadline:
                raise ProvisionError(f"another provisioning run holds {lock}")
            time.sleep(0.5)
    try:
        handle.write(str(os.getpid()))
        handle.close()
        entries = [entry for entry in manifest.get("resources", []) if not only or entry.get("id") in only]
        tasks = [
            (entry, name)
            for entry in entries
            for name in entry.get("files", [])
            if not files or name in files
        ]
        results: dict[str, ProvisionResult] = {}

        def work(task: tuple[dict, str]) -> None:
            entry, name = task
            key = str(entry.get("id", "?"))
            result = results.setdefault(key, ProvisionResult(resource=key, root=root))
            single = dict(entry)
            single["files"] = [name]
            partial = provision_one(
                root,
                single,
                files=[name],
                offline=offline,
                timeout=timeout,
                retries=retries,
                source_dir=source,
                mirrors=mirrors,
                rewrites=rewrites,
                plan=plan,
            )
            result.downloaded.extend(partial.downloaded)
            result.copied.extend(partial.copied)
            result.skipped.extend(partial.skipped)
            result.missing.extend(partial.missing)
            result.failed.extend(partial.failed)

        if jobs > 1 and len(tasks) > 1:
            with ThreadPoolExecutor(max_workers=jobs) as pool:
                for task in tasks:
                    pool.submit(work, task)
        else:
            for task in tasks:
                work(task)
        ordered = [results[key].as_dict(plan=plan) for key in results]
        return {
            "root": str(root),
            "offline": offline,
            "plan": plan,
            "results": ordered,
            "status": "ok" if all(item["status"] in ("ok", "planned") for item in ordered) else "incomplete",
        }
    finally:
        lock.unlink(missing_ok=True)


def load_manifest(path: str | Path | None = None) -> dict:
    """Load the resource manifest from the package."""

    if path is None:
        path = Path(__file__).resolve().parents[2] / "operon" / "resources.json"
    return json.loads(Path(path).read_text())
