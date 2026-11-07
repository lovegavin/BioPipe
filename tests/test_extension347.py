"""Tests for resource provisioning (download, checksum, offline, locking)."""

import hashlib
import json

import pytest

from src.resources.provision import (
    ProvisionError,
    provision,
    sha256_file,
    verify_file,
)


def _manifest(tmp_path, *, sha=None, size=None):
    source = tmp_path / "source.bin"
    source.write_bytes(b"operon-provision-test")
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    entry = {
        "id": "demo",
        "files": ["data/a.bin", "data/b.bin"],
        "downloads": {"data/a.bin": source.as_uri()},
        "sha256": {"data/a.bin": sha or digest},
        "sizes": {"data/a.bin": size or source.stat().st_size},
    }
    return {"resources": [entry]}, source


def test_verify_file(tmp_path):
    path = tmp_path / "x.bin"
    assert verify_file(path) == (False, "missing")
    path.write_bytes(b"abc")
    ok, reason = verify_file(path, sha256=hashlib.sha256(b"abc").hexdigest(), size=3)
    assert ok and reason == "ok"
    ok, reason = verify_file(path, size=9)
    assert not ok and "size" in reason


def test_provision_downloads_and_is_idempotent(tmp_path):
    manifest, source = _manifest(tmp_path)
    root = tmp_path / "root"
    first = provision(manifest, root)
    assert first["status"] == "incomplete"  # data/b.bin has no download URL
    assert first["results"][0]["downloaded"] == ["data/a.bin"]
    assert first["results"][0]["missing"] == ["data/b.bin (missing)"]  # no URL declared
    target = root / "data/a.bin"
    assert target.read_bytes() == source.read_bytes()
    second = provision(manifest, root)
    assert second["results"][0]["skipped"] == ["data/a.bin"]


def test_checksum_mismatch_is_reported(tmp_path):
    manifest, _ = _manifest(tmp_path, sha="0" * 64)
    summary = provision(manifest, tmp_path / "root")
    assert summary["status"] == "incomplete"
    assert any("checksum mismatch" in item for item in summary["results"][0]["failed"])
    assert not (tmp_path / "root/data/a.bin").exists()


def test_offline_mode_reports_without_download(tmp_path):
    manifest, _ = _manifest(tmp_path)
    summary = provision(manifest, tmp_path / "root", offline=True)
    assert summary["results"][0]["missing"]
    assert summary["results"][0]["downloaded"] == []


def test_only_and_files_filters(tmp_path):
    manifest, _ = _manifest(tmp_path)
    assert provision(manifest, tmp_path / "r1", only=["other"])["results"] == []
    summary = provision(manifest, tmp_path / "r2", files=["data/a.bin"])
    assert summary["results"][0]["skipped"] == []


def test_lock_timeout(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    (root / ".operon-provision.lock").write_text("12345")
    manifest, _ = _manifest(tmp_path)
    with pytest.raises(ProvisionError, match="holds"):
        provision(manifest, root, lock_timeout=0.1)


def test_sha256_file(tmp_path):
    path = tmp_path / "y.bin"
    path.write_bytes(b"abc")
    assert sha256_file(path) == hashlib.sha256(b"abc").hexdigest()


def test_from_dir_copy(tmp_path):
    manifest, source = _manifest(tmp_path)
    staging = tmp_path / "staging" / "data"
    staging.mkdir(parents=True)
    (staging / "a.bin").write_bytes(source.read_bytes())
    summary = provision(manifest, tmp_path / "root", source_dir=tmp_path / "staging")
    assert summary["results"][0]["copied"] == ["data/a.bin"]
    assert (tmp_path / "root/data/a.bin").read_bytes() == source.read_bytes()


def test_plan_does_not_fetch(tmp_path):
    manifest, _ = _manifest(tmp_path)
    summary = provision(manifest, tmp_path / "root", plan=True)
    assert summary["results"][0]["downloaded"] == []
    assert summary["results"][0]["missing"]
    assert not (tmp_path / "root/data/a.bin").exists()


def test_mirror_and_rewrite(tmp_path):
    from src.resources.provision import rewrite_url

    hf = "https://huggingface.co/org/repo/resolve/main/x.bin"
    assert rewrite_url(hf, mirrors=["https://hf-mirror.com"]).startswith("https://hf-mirror.com/org/")
    assert rewrite_url(hf, rewrites=[("https://huggingface.co", "https://cdn.example")]).startswith("https://cdn.example/org/")
    assert rewrite_url("https://other/x", mirrors=["https://m"]) == "https://other/x"


def test_parallel_downloads(tmp_path):
    manifest, _ = _manifest(tmp_path)
    summary = provision(manifest, tmp_path / "root", jobs=2)
    assert summary["results"][0]["downloaded"] == ["data/a.bin"]
