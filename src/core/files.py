"""Small, validated references to immutable disk datasets; never array payloads."""
from dataclasses import dataclass, field
import json
from pathlib import Path

from .errors import ValidationError


@dataclass
class FileArtifact:
    format: str
    files: dict[str, str]
    info: dict = field(default_factory=dict)
    fingerprints: dict = field(default_factory=dict)

    def __post_init__(self):
        self.files = {key: str(Path(value).resolve()) for key, value in self.files.items()}
        self.info = {**self.info, "representation": self.format}
        if not self.fingerprints:
            self.fingerprints = {key: self._stamp(Path(value)) for key, value in self.files.items()}

    @staticmethod
    def _stamp(path):
        stat = path.stat()
        return {"size": stat.st_size, "mtime_ns": stat.st_mtime_ns}

    @property
    def dims(self):
        return []

    @property
    def labels(self):
        return {}

    @property
    def axis_info(self):
        return {}

    def validate(self):
        if not isinstance(self.format, str) or not self.format or not self.files:
            raise ValidationError("FileArtifact", "format and file roles are required")
        if self.info.get("representation") != self.format:
            raise ValidationError("FileArtifact", "representation differs from file format")
        if set(self.fingerprints) != set(self.files):
            raise ValidationError("FileArtifact", "file fingerprint roles differ")
        for role, value in self.files.items():
            path = Path(value)
            if not isinstance(role, str) or not role or not path.is_absolute() or not path.is_file():
                raise ValidationError("FileArtifact", f"missing file for role {role!r}: {value}")
            if self._stamp(path) != self.fingerprints[role]:
                raise ValidationError("FileArtifact", f"file changed after registration: {value}")
        json.dumps(self.to_dict(), allow_nan=False)

    def to_dict(self):
        return {"format": self.format, "files": self.files, "info": self.info,
                "fingerprints": self.fingerprints}

    @property
    def file_bytes(self):
        return sum(item["size"] for item in self.fingerprints.values())
