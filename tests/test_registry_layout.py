"""Registry route discovery in installed layouts."""

from pathlib import Path

from operon import registry


def test_default_route_roots_pairs_env_with_its_code_dir(monkeypatch, tmp_path):
    prefix = tmp_path / "managed-v1" / "env-abc"
    prefix.mkdir(parents=True)
    paired = tmp_path / "managed-v1" / "code-abc" / "routes"
    paired.mkdir(parents=True)
    other = tmp_path / "managed-v1" / "code-old" / "routes"
    other.mkdir(parents=True)
    monkeypatch.setattr("sys.prefix", str(prefix))
    monkeypatch.delenv("OPERON_ROUTES", raising=False)
    assert registry.default_route_roots(tmp_path / "site-packages") == [paired.resolve()]


def test_default_route_roots_falls_back_to_managed_code_dir(monkeypatch, tmp_path):
    prefix = tmp_path / "managed-v1" / "env-abc"
    prefix.mkdir(parents=True)
    code = tmp_path / "managed-v1" / "code-abc" / "routes"
    code.mkdir(parents=True)
    monkeypatch.setattr("sys.prefix", str(prefix))
    monkeypatch.delenv("OPERON_ROUTES", raising=False)
    roots = registry.default_route_roots(tmp_path / "site-packages")
    assert roots == [code.resolve()]


def test_default_route_roots_prefers_env_override(monkeypatch, tmp_path):
    override = tmp_path / "custom-routes"
    override.mkdir()
    monkeypatch.setenv("OPERON_ROUTES", str(override))
    roots = registry.default_route_roots(tmp_path / "nowhere")
    assert roots and roots[0] == override.resolve()


def test_route_sources_uses_fallback_when_root_has_no_routes(monkeypatch, tmp_path):
    prefix = tmp_path / "managed-v1" / "env-abc"
    prefix.mkdir(parents=True)
    routes = tmp_path / "managed-v1" / "code-abc" / "routes" / "demo"
    routes.mkdir(parents=True)
    (routes / "task.yaml").write_text("name: demo\nsteps: []\n")
    monkeypatch.setattr("sys.prefix", str(prefix))
    monkeypatch.delenv("OPERON_ROUTES", raising=False)
    found = registry.route_sources(tmp_path / "site-packages")
    assert [relative for _, relative in found] == ["demo"]
