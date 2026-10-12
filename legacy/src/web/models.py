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
    kind: Literal["source", "operator"]
    operator: str | None = None
    title: str = Field(default="", max_length=120)
    position: Position
    params: dict[str, Any] = Field(default_factory=dict)
    source: Source | None = None
    input_count: int = Field(default=1, ge=0, le=20)


class GraphEdge(StrictModel):
    id: str = Field(max_length=200)
    source: str = Field(max_length=80)
    target: str = Field(max_length=80)
    sourceHandle: str = Field(default="out", max_length=100)
    targetHandle: str = Field(default="in-0", pattern=r"^in-\d+$")


class Graph(StrictModel):
    schema_version: Literal[1] = 1
    name: str = Field(default="我的工作流", min_length=1, max_length=120)
    base_dir: str = Field(default=".", max_length=2048)
    nodes: list[GraphNode] = Field(max_length=1000)
    edges: list[GraphEdge] = Field(max_length=5000)
    memory: dict[str, Any] = Field(default_factory=lambda: {"enabled": True, "auto_spill": True})


class ManifestImport(StrictModel):
    text: str = Field(max_length=2 * 1024**2)
    base_dir: str = Field(default=".", max_length=2048)
