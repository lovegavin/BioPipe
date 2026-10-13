"""Desktop bootstrap hints must be portable, isolated and safe to ignore."""
import json
from pathlib import Path
import sys

from biopipe.runtime import remember_runtime, runtime_config_path


def test_runtime_hint_is_home_relative_and_not_a_canvas_profile(tmp_path, monkeypatch):
    home = tmp_path / "用户 home"
    monkeypatch.chdir(tmp_path)
    assert runtime_config_path(home=home, environ={}) == home / ".biopipe/runtime.json"
    assert runtime_config_path(home=home, environ={"BIOPIPE_RUNTIME_CONFIG": "custom/runtime.json"}) == home / "custom/runtime.json"
    assert runtime_config_path(home=home, environ={"BIOPIPE_STUDIO_HOME": "other profile"}) == home / ".biopipe/runtime.json"
    assert not home.exists()


def test_running_python_is_remembered_atomically(tmp_path, monkeypatch):
    record = tmp_path / "user home/runtime.json"
    monkeypatch.setenv("BIOPIPE_RUNTIME_CONFIG", str(record))
    assert remember_runtime()
    data = json.loads(record.read_text(encoding="utf-8"))
    assert data == {"schema_version": 1, "python": str(Path(sys.executable).absolute())}
    assert list(record.parent.glob("*.tmp")) == []


def test_incomplete_runtime_does_not_replace_a_working_hint(tmp_path, monkeypatch):
    record = tmp_path / "runtime.json"
    record.write_text("original", encoding="utf-8")
    monkeypatch.setattr("biopipe.runtime.importlib.util.find_spec", lambda name: None)
    assert not remember_runtime(path=record)
    assert record.read_text(encoding="utf-8") == "original"


def test_unwritable_runtime_hint_does_not_prevent_startup(tmp_path):
    blocked = tmp_path / "file"
    blocked.write_text("preserve", encoding="utf-8")
    assert not remember_runtime(path=blocked / "runtime.json")
    assert blocked.read_text(encoding="utf-8") == "preserve"
