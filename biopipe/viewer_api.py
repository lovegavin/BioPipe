"""Shared retained-result handoff API. Launching programs requires run scope."""
from fastapi import Request
from pydantic import BaseModel, ConfigDict, Field


class ViewerPath(BaseModel):
    model_config = ConfigDict(extra='forbid')
    executable: str | None = Field(default=None, max_length=32768)


class ViewerOpen(BaseModel):
    model_config = ConfigDict(extra='forbid')
    viewer: str | None = Field(default=None, min_length=1, max_length=64)
    role: str = Field(min_length=1, max_length=512)


class ViewerPrepare(BaseModel):
    model_config = ConfigDict(extra='forbid')
    role: str = Field(min_length=1, max_length=512)


class ViewerDefault(BaseModel):
    model_config = ConfigDict(extra='forbid')
    extension: str = Field(min_length=2, max_length=64)
    viewer: str | None = Field(default=None, min_length=1, max_length=64)


def mount_viewers(app, application, bridge):
    service = application.viewers

    @app.get('/api/v1/viewers')
    def viewers(request: Request, refresh: bool = False):
        bridge.actor(request, 'context')
        return service.listing(refresh=refresh)

    @app.post('/api/v1/viewers/default')
    def set_default(payload: ViewerDefault, request: Request):
        bridge.actor(request, 'run')
        return service.set_default(payload.extension, payload.viewer)

    @app.post('/api/v1/viewers/{viewer}/configure')
    def configure(viewer: str, payload: ViewerPath, request: Request):
        bridge.actor(request, 'run')
        return service.configure(viewer, payload.executable)

    @app.get('/api/v1/jobs/{job}/artifacts/{artifact}/viewers')
    def options(job: str, artifact: str, role: str, request: Request):
        bridge.actor(request, 'context')
        return service.options(job, artifact, role)

    @app.post('/api/v1/jobs/{job}/artifacts/{artifact}/prepare-viewer')
    def prepare(job: str, artifact: str, payload: ViewerPrepare, request: Request):
        bridge.actor(request, 'run')
        return service.prepare(job, artifact, payload.role)

    @app.post('/api/v1/jobs/{job}/artifacts/{artifact}/open-viewer')
    def open_viewer(job: str, artifact: str, payload: ViewerOpen, request: Request):
        bridge.actor(request, 'run')
        return service.open(job, artifact, payload.role, payload.viewer)
