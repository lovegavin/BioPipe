"""Presentation preferences belong to the profile, not a workflow or loopback port."""
from typing import Literal
from pydantic import BaseModel, ConfigDict
from operon.user_config import UserConfig


class Preferences(BaseModel):
    model_config = ConfigDict(extra='forbid')
    language: Literal['system', 'zh-CN', 'en'] = 'system'
    theme: Literal['system', 'light', 'dark'] = 'system'


def presentation(value):
    return Preferences.model_validate({key: value[key] for key in Preferences.model_fields if key in value})


def load(directory):
    return presentation(UserConfig(directory).read())


def save(directory, preferences, initialize=False):
    def edit(config):
        for key, value in preferences.model_dump(exclude_unset=True).items():
            if not initialize or key not in config:
                config[key] = value
    return presentation(UserConfig(directory).update(edit))


def mount_preferences(app, service):
    @app.get('/api/preferences')
    def read_preferences():
        return load(service.directory)

    @app.post('/api/preferences')
    def write_preferences(preferences: Preferences, initialize: bool = False):
        # First boot can import old browser-only choices, but must not overwrite
        # an existing profile setting (including one saved by another client).
        return save(service.directory, preferences, initialize)
