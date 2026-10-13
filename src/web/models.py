from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Position(StrictModel):
    x: float = Field(ge=-1000000, le=1000000)
    y: float = Field(ge=-1000000, le=1000000)


class Source(StrictModel):
    path: str = Field(default="", max_length=2048)
    dims: list[str] = Field(default_factory=lambda: ["sample", "feature"], min_length=1, max_length=8)
    labels: dict[str, Any] = Field(default_factory=lambda: {"sample": "auto", "feature": "builtin"})
    args: dict[str, Any] = Field(default_factory=dict)


class GraphNode(StrictModel):
    id: str = Field(pattern=r"^[A-Za-z_][A-Za-z0-9_.-]{0,79}$")
    kind: Literal["source", "operator", "route"]
    operator: str | None = None
    title: str = Field(default="", max_length=120)
    position: Position
    params: dict[str, Any] = Field(default_factory=dict)
    context_params: dict[str, Any] = Field(default_factory=dict)
    source: Source | None = None
    input_count: int = Field(default=1, ge=0, le=20)
    route: RouteDefinition | None = None


class GraphEdge(StrictModel):
    id: str = Field(max_length=200)
    source: str = Field(max_length=80)
    target: str = Field(max_length=80)
    sourceHandle: str = Field(default="out", max_length=100)
    targetHandle: str = Field(default="in-0", pattern=r"^in-\d+$")


class RouteInput(StrictModel):
    node_id: str = Field(max_length=80)
    label: str = Field(min_length=1, max_length=120)
    contract: dict[str, Any] = Field(default_factory=dict)


class RouteOutput(StrictModel):
    node_id: str = Field(max_length=80)
    handle: str = Field(default="out", pattern=r"^out(?:-\d+)?$")
    label: str = Field(min_length=1, max_length=120)
    contract: dict[str, Any] = Field(default_factory=dict)


class RouteInterface(StrictModel):
    version: Literal[1] = 1
    inputs: list[RouteInput] = Field(default_factory=list, max_length=20)
    outputs: list[RouteOutput] = Field(default_factory=list, max_length=20)


class Graph(StrictModel):
    schema_version: Literal[1, 2] = 1
    name: str = Field(default="我的工作流", min_length=1, max_length=120)
    base_dir: str = Field(default=".", max_length=2048)
    nodes: list[GraphNode] = Field(max_length=1000)
    edges: list[GraphEdge] = Field(max_length=5000)
    memory: dict[str, Any] = Field(default_factory=lambda: {"enabled": True, "auto_spill": True})
    params: dict[str, Any] = Field(default_factory=dict)
    runtime: dict[str, Any] = Field(default_factory=dict)
    manifest_extra: dict[str, Any] = Field(default_factory=dict)
    interface: RouteInterface | None = None
    plugin_lock: dict[str, dict[str, str]] = Field(default_factory=dict)


class RouteDefinition(StrictModel):
    id: str = Field(pattern=r"^route_[a-f0-9]{12}$")
    version: int = Field(ge=1)
    name: str = Field(min_length=1, max_length=120)
    graph: Graph


class SavedWorkflow(StrictModel):
    id: str = Field(pattern=r"^route_[a-f0-9]{12}$")
    version: int = Field(ge=1)
    updated_at: str
    graph: Graph


class SaveWorkflow(StrictModel):
    id: str | None = Field(default=None, pattern=r"^route_[a-f0-9]{12}$")
    expected_version: int | None = Field(default=None, ge=1)
    graph: Graph


class RegisterRoutes(StrictModel):
    workflow_ids: list[str] = Field(min_length=1, max_length=50)


class LibraryState(StrictModel):
    disabled: list[str] = Field(default_factory=list, max_length=2000)
    hidden: list[str] = Field(default_factory=list, max_length=2000)


class LibraryAction(StrictModel):
    key: str = Field(min_length=1, max_length=80)
    action: Literal["disable", "enable", "delete", "restore"]


class Viewport(StrictModel):
    x: float = Field(ge=-1000000, le=1000000)
    y: float = Field(ge=-1000000, le=1000000)
    zoom: float = Field(ge=.1, le=4)


class WorkspaceDocument(StrictModel):
    id: str = Field(min_length=1, max_length=80)
    graph: Graph
    viewport: Viewport | None = None
    workflow_id: str | None = None
    workflow_version: int | None = None


class PanelWidths(StrictModel):
    library: int | None = Field(default=None, ge=200, le=360)
    inspector: int | None = Field(default=None, ge=256, le=420)


class Workspace(StrictModel):
    schema_version: Literal[1] = 1
    active_id: str = Field(max_length=80)
    documents: list[WorkspaceDocument] = Field(min_length=1, max_length=20)
    closed_documents: list[WorkspaceDocument] = Field(default_factory=list, max_length=20)
    panel_widths: PanelWidths = Field(default_factory=PanelWidths)


GraphNode.model_rebuild()
Graph.model_rebuild()
RouteDefinition.model_rebuild()


class ManifestImport(StrictModel):
    text: str
    base_dir: str = Field(default=".", max_length=2048)
