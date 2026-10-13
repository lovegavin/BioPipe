import pytest


@pytest.fixture(autouse=True)
def isolated_runtime_hint(tmp_path, monkeypatch):
    """Real backend subprocesses must not read or replace the user's Python choice."""
    monkeypatch.setenv("BIOPIPE_RUNTIME_CONFIG", str(tmp_path / "runtime.json"))
