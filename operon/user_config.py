"""One profile-scoped config for application preferences, shared by UI and CLI."""
import json
from pathlib import Path

from .bytecode import io_path
from src.web.storage import FileLock, atomic_json


class UserConfig:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.path = self.directory / 'config.json'
        self.lock = FileLock(self.directory / 'config.lock')

    @staticmethod
    def _read(path):
        native = io_path(path)
        if not native.is_file():
            return {}
        value = json.loads(native.read_text(encoding='utf-8'))
        if not isinstance(value, dict):
            raise ValueError(f'Expected a settings object in {path.name}')
        return value

    def _load(self):
        if io_path(self.path).is_file():
            return self._read(self.path)
        # Import earlier settings once. Preserve the originals as a fallback
        # for older versions; after config.json exists it is the only authority.
        value = self._read(self.directory / 'preferences.json')
        viewers = {}
        for name, filename in (('paths', 'settings.json'), ('defaults', 'defaults.json')):
            path = self.directory / 'viewers' / filename
            if io_path(path).is_file():
                viewers[name] = self._read(path)
        if viewers:
            value['viewers'] = viewers
        if value:
            atomic_json(self.path, value)
        return value

    def read(self):
        with self.lock:
            return self._load()

    def update(self, edit):
        """Merge the edited fields under one lock; never replace unrelated settings."""
        with self.lock:
            value = self._load()
            before = json.dumps(value, sort_keys=True)
            edit(value)
            if json.dumps(value, sort_keys=True) != before or not io_path(self.path).is_file():
                atomic_json(self.path, value)
            return value
