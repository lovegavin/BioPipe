import pytest


@pytest.fixture(autouse=True)
def isolated_runtime_hint(tmp_path, monkeypatch):
    """Worker tests isolate the user's Python choice and resource ledger."""
    monkeypatch.setenv("OPERON_RUNTIME_CONFIG", str(tmp_path / "runtime.json"))
    monkeypatch.setenv("OPERON_ADMISSION_DIR", str(tmp_path / "admission"))
