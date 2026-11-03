"""Artifact tables and remote ensure."""

from __future__ import annotations

import pickle
from pathlib import Path
from types import MethodType, SimpleNamespace

import numpy as np
import pytest

from src.web import remote_service as module
from src.web.service import JobService


def _fake_service(tmp_path):
    cache = tmp_path / "cache" / "abc"
    cache.mkdir(parents=True)
    np.save(cache / "data.npy", np.arange(50, dtype=np.float32).reshape(10, 5))
    with (cache / "metadata.pkl").open("wb") as handle:
        pickle.dump({"labels": {"residue": {f"r{i}": i for i in range(10)},
                                "statistic": {f"c{i}": i for i in range(5)}}}, handle)
    service = SimpleNamespace()
    service.artifact = lambda key, artifact_id: (cache / "data.npy", {"name": "iface", "kind": "form"})
    service._artifact_labels = JobService._artifact_labels
    service.preview = MethodType(JobService.preview, service)
    return service


def test_preview_returns_labels_and_window(tmp_path):
    service = _fake_service(tmp_path)
    value = service.preview("job", "abc", offset=2, limit=3)
    assert value["columns"] == ["c0", "c1", "c2", "c3", "c4"]
    assert value["row_labels"] == ["r2", "r3", "r4"]
    assert value["rows"] == [[10.0, 11.0, 12.0, 13.0, 14.0], [15.0, 16.0, 17.0, 18.0, 19.0], [20.0, 21.0, 22.0, 23.0, 24.0]]
    assert value["total"] == 10 and value["offset"] == 2


def test_ensure_reconnects_key_auth_and_refuses_password():
    manager = SimpleNamespace()
    manager.profile = lambda key: {"auth": "key"}
    manager.status = lambda: {"profiles": {}}
    manager.connect = lambda key, credentials: {"latency": 12}
    manager.ensure = MethodType(module.RemoteManager.ensure, manager)
    assert manager.ensure("p1") == {"connected": True, "profile_id": "p1", "latency": 12}

    manager.status = lambda: {"profiles": {"p1": {"connected": True}}}
    assert manager.ensure("p1")["connected"] is True

    manager.profile = lambda key: {"auth": "password"}
    manager.status = lambda: {"profiles": {}}
    with pytest.raises(ValueError, match="密码认证"):
        manager.ensure("p1")
