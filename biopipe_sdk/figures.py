"""Backend-neutral, JSON-only figure artifacts. No plotting imports at discovery."""
from pathlib import Path
import re

FORMATS = {'png', 'pdf', 'svg', 'jpg', 'jpeg', 'tif', 'tiff', 'webp'}


def register_figure(context, figure_id, files, *, title=None, **metadata):
    """Describe already saved files inside this job; never copy or load pixels.

    Return a report with a flat ``figures`` list. Different formats of the same
    figure share an ID. Merge reports with ``figure_collection`` for multi-plots.
    """
    if not isinstance(figure_id, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', figure_id):
        raise ValueError('Figure ID must be a nonempty portable identifier')
    if not isinstance(files, dict) or not files:
        raise ValueError('A figure needs a format-to-path mapping')
    if set(metadata) - {'width_mm', 'height_mm', 'dpi', 'description'}:
        raise ValueError('Unknown figure metadata')
    import math
    for key in ('width_mm', 'height_mm', 'dpi'):
        if key in metadata and (isinstance(metadata[key], bool) or not isinstance(metadata[key], (int, float))
                                or not math.isfinite(metadata[key]) or metadata[key] <= 0):
            raise ValueError(f'{key} must be finite and positive')
    if 'description' in metadata and not isinstance(metadata['description'], str):
        raise ValueError('Figure description must be text')
    if title is not None and not isinstance(title, str):
        raise ValueError('Figure title must be text')
    base = Path(context.out_dir).resolve()
    entries = []
    for fmt, value in files.items():
        path = Path(value).resolve()
        if fmt not in FORMATS or path.suffix.lower() != '.' + fmt:
            raise ValueError('Figure format must match the saved file extension')
        if not path.is_relative_to(base) or not path.is_file():
            raise ValueError('Figure must be a saved file inside the job output directory')
        entries.append({'id': figure_id, 'title': title or figure_id, 'format': fmt,
                        'path': str(path), 'filename': path.name, **metadata})
    return {'figures': entries}


def figure_collection(*reports):
    """Combine independently rendered figures, rejecting ambiguous IDs/formats."""
    entries, seen = [], set()
    for report in reports:
        for item in report['figures']:
            key = (item['id'], item['format'])
            if key in seen:
                raise ValueError(f'Duplicate figure/format: {key}')
            seen.add(key)
            entries.append(dict(item))
    return {'figures': entries}


def save_matplotlib(context, figure, filename, *, figure_id=None, title=None):
    """Save a Matplotlib figure using BioPipe publication defaults, then close it."""
    from src.task.step.steps._plot_helpers import save_figure, figure_report
    report = figure_report({'path': save_figure(figure, context, filename)})
    entries = report['figures']
    return register_figure(context, figure_id or entries[0]['id'],
                           {item['format']: item['path'] for item in entries},
                           title=title, **{k: entries[0][k] for k in ('width_mm', 'height_mm', 'dpi')})


def publication_style(context=None):
    """Apply the shared static publication theme; never inherit the Studio theme."""
    from src.task.step.steps._plot_helpers import setup_style
    setup_style(context)
