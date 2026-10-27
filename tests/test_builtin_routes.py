"""Shipped workflows are real reusable graphs, with persistent library controls."""
from copy import deepcopy
import json
from pathlib import Path

from fastapi.testclient import TestClient
import numpy as np
import pandas as pd
import pytest

from src.core import Form
from src.reader import read_source
from src.task import STEPS, Context, run
from src.task.operator_catalog import build_catalog
from src.web.api import create_app
from src.web.graph import compile_graph
from src.web.models import Graph, RouteDefinition, GraphNode, GraphEdge, Position
from src.web.routes import RouteLibrary
from src.web.service import Settings

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = json.loads((ROOT / "src/web/builtin_routes.json").read_text(encoding="utf-8"))["routes"]


def test_builtin_install_library_controls_and_persisted_removal(tmp_path):
    settings = Settings(tmp_path, tmp_path / ".studio", ROOT / "frontend/dist", testing=True, code_root=ROOT, builtin_routes=True)
    app = create_app(settings)
    with TestClient(app) as client:
        client.headers["X-Studio-Token"] = client.get("/api/bootstrap").json()["token"]
        routes = client.get("/api/routes").json()
        assert {r["name"] for r in routes} == {"GWAS", "RNA-seq DE", "Proteomics DE", "生存分析", "16S Microbiome", "Hi-C from FASTQ", "Hi-C from BAM", "Hi-C from PAIRS"}
        key = routes[0]["id"]
        for operator in (key, "pca"):
            result = client.post("/api/library/manage", json={"key": operator, "action": "disable"})
            assert result.status_code == 200 and operator in result.json()["state"]["disabled"]
        restarted = RouteLibrary(app.state.service.routes.directory, app.state.service.catalog, tmp_path)
        restarted.install_builtins()
        assert set(restarted.library_state()["disabled"]) == {key, "pca"}
        for operator in (key, "pca"):
            assert client.post("/api/library/manage", json={"key": operator, "action": "delete"}).status_code == 200
        restarted.install_builtins()
        assert len(restarted.routes()) == len(BUNDLE) - 1  # Startup must not resurrect deleted templates.
        assert restarted.get(key)["graph"] == routes[0]["graph"]
        assert restarted.library_state() == {"disabled": [], "hidden": ["pca"]}
        assert client.post("/api/library/manage", json={"key": "pca", "action": "restore"}).json()["state"]["hidden"] == []
        assert len(client.post("/api/routes/register", json={"workflow_ids": [key]}).json()) == len(BUNDLE)
        assert client.post("/api/library/manage", json={"key": "unknown", "action": "delete"}).status_code == 404
        assert client.post("/api/library/manage", json={"key": "pca", "action": "invalid"}).status_code == 422


def synthetic_sources(graph, directory):
    rng = np.random.default_rng(821)
    n = 120 if graph.name in ("GWAS", "生存分析") else 16
    samples = [f"s{i}" for i in range(n)]
    forms = {}
    for node in graph.nodes:
        if node.kind != "source":
            continue
        if node.id == "geno":
            m = 40
            values = rng.binomial(2, .35, (m, n)).astype(np.float32)
            forms[node.id] = Form(values, ["variant", "sample"],
                {"variant": {f"v{i}": i for i in range(m)}, "sample": {s: i for i, s in enumerate(samples)}},
                {"missing_code": np.nan, "ploidy": 2, "representation": "hard_call", "chrom": ["1"]*m,
                 "pos": list(range(100, 100+m))}, {"variant": ["chrom", "pos"]})
            continue
        if node.id == "pheno":
            frame = pd.DataFrame({"id": samples, "trait_value": rng.normal(size=n)})
        elif node.id == "covar":
            frame = pd.DataFrame({"id": samples, "sex": rng.integers(0, 2, n), "batch": rng.integers(0, 3, n)})
        elif node.id == "otu":
            frame = pd.DataFrame(rng.poisson(30, (40, n)), index=[f"otu{i}" for i in range(40)], columns=samples).reset_index(names="id")
        elif node.id == "meta" and graph.name == "16S Microbiome":
            frame = pd.DataFrame({"id": samples, "site": [f"site{i % 4}" for i in range(n)],
                                  "horizon": [f"h{i % 2}" for i in range(n)], "transect": [f"t{i % 3}" for i in range(n)]})
        elif node.id in ("counts", "proteins"):
            m = 40
            values = rng.negative_binomial(12, .2, (m, n)) if node.id == "counts" else rng.lognormal(3, .6, (m, n))
            names = ["ENSG00000109906"] + [f"feature{i}" for i in range(1, m)]
            frame = pd.DataFrame(values, index=names, columns=samples).reset_index(names="id")
        elif node.id == "meta":
            column, labels = ("dex", ("untrt", "trt")) if graph.name == "RNA-seq DE" else ("Stage", ("Stage II", "Stage III"))
            frame = pd.DataFrame({"id": samples, column: [labels[0]]*(n//2) + [labels[1]]*(n//2)})
        else:
            frame = pd.DataFrame({"id": samples, "OS_Time_nature2012": rng.exponential(400, n)+1,
                "OS_event_nature2012": rng.binomial(1, .8, n),
                "AJCC_Stage_nature2012": rng.choice(["Stage IA", "Stage IIA", "Stage IIIA", "Stage IV"], n),
                "Age_at_Initial_Pathologic_Diagnosis_nature2012": rng.normal(55, 9, n),
                "Gender_nature2012": rng.choice(["female", "male"], n)})
        path = directory / (node.id + ".csv")
        frame.to_csv(path, index=False)
        forms[node.id] = read_source(path, node.source.dims, node.source.labels)
    return forms


@pytest.mark.parametrize("definition", BUNDLE, ids=[r["name"] for r in BUNDLE])
def test_each_shipped_route_expands_and_executes_all_branches(tmp_path, definition):
    if definition['name'].startswith('Hi-C from '):
        pytest.skip('File-backed routes use real Linux fixtures in test_hic_real.py, not the numeric CSV fixture')
    if definition["name"] == "RNA-seq DE":
        pytest.importorskip("pydeseq2")
    if definition["name"] == "生存分析":
        pytest.importorskip("lifelines")
    route = RouteDefinition.model_validate(definition)
    sources = [node.model_copy(deep=True) for node in route.graph.nodes if node.kind == "source"]
    outer = Graph(name=route.name, nodes=sources + [GraphNode(id="route", kind="route", title=route.name,
                  position=Position(x=300, y=100), route=route)],
                  edges=[GraphEdge(id=f"e{i}", source=port.node_id, target="route", targetHandle=f"in-{i}")
                         for i, port in enumerate(route.graph.interface.inputs)],
                  memory={"enabled": True, "budget_mb": 512, "keep": [f"route__out_{i+1}" for i in range(len(route.graph.interface.outputs))]})
    catalog = build_catalog(STEPS)
    manifest, order = compile_graph(outer, catalog, tmp_path)
    assert len(order) == len(route.graph.nodes) - len(sources)
    ctx = Context(tmp_path, manifest)
    try:
        for key, form in synthetic_sources(route.graph, tmp_path).items():
            ctx[key] = form
        run(ctx, manifest["steps"])
        assert len(ctx.artifacts["exports"]) == len(order)
        expected_figures = {"GWAS": 3, "RNA-seq DE": 5, "Proteomics DE": 3, "生存分析": 2, "16S Microbiome": 5}[route.name]
        assert len(list((ctx.memory.run_dir / "figures").glob("*.png"))) == expected_figures
    finally:
        ctx.memory.close("complete" if ctx._run_status == "complete" else "failed")
