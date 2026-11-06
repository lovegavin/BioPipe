"""JSON report descriptors for original tool outputs (no new SDK dependency)."""
import tempfile
from pathlib import Path
from uuid import uuid4
from biopipe.bytecode import io_path


def output_directory(ctx, name):
    artifact_path = getattr(ctx, 'artifact_path', None)
    if callable(artifact_path):
        base = Path(artifact_path(f'{name}/{uuid4().hex}'))
    else:
        base = Path(getattr(ctx, 'task_dir', tempfile.gettempdir())) / 'artifacts' / name / uuid4().hex
    directory = base
    io_path(directory).mkdir(parents=True, exist_ok=True)
    return directory


def result_file(file_id, path, format, title=None):
    path = Path(path)
    return {'id': file_id, 'path': str(path), 'filename': path.name,
            'format': format, 'title': title or path.name, 'bytes': io_path(path).stat().st_size}


def remember_native(ctx, output_name, files):
    """Small per-run index; the producer report remains the isolation fallback."""
    artifacts = getattr(ctx, 'artifacts', None)
    if artifacts is None:
        return
    artifacts.setdefault('native_results', {})[output_name] = {
        'index': len(artifacts.get('exports', [])) + 1, 'files': files}
