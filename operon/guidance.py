"""Small, versioned operating guides bundled with every Operon installation."""
import hashlib
from importlib.resources import files

from . import __version__


TOPICS = {
    'start': ('Start here', 'Choose a task, permissions and the smallest useful query.'),
    'operators': ('Find an operator', 'Search summaries; fetch schemas or selected documentation only.'),
    'canvas': ('Edit a canvas', 'Read selection, apply one transaction and undo safely.'),
    'workflow': ('Prepare and run a workflow', 'Reuse a saved route or prepare a new one without a window.'),
    'server': ('Use a server or terminal', 'Select a runtime, validate YAML, prepare dependencies and monitor batch jobs.'),
    'jobs': ('Monitor and recover jobs', 'Wait, inspect bounded logs and retry without duplicate work.'),
    'results': ('Use analysis results', 'Inspect result metadata and open retained native files.'),
    'api': ('Connect another application', 'Discover the local API, authenticate and hand off native artifacts.'),
}


def guide(topic='start', *, if_sha256=None):
    """Read only a selected installed guide; never import an analysis operator."""
    if topic == 'index':
        return {'version': __version__, 'topics': [
            {'id': key, 'title': value[0], 'summary': value[1]} for key, value in TOPICS.items()]}
    if topic not in TOPICS:
        raise ValueError('Unknown guide topic. Use: ' + ', '.join(['index', *TOPICS]))
    content = files('operon').joinpath('guides', topic + '.md').read_text(encoding='utf-8')
    content = content.replace('\r\n', '\n').replace('\r', '\n')
    digest = hashlib.sha256(content.encode('utf-8')).hexdigest()
    result = {'topic': topic, 'title': TOPICS[topic][0], 'version': __version__, 'sha256': digest}
    if if_sha256 == digest:
        return {**result, 'not_modified': True}
    return {**result, 'content': content}


def instructions():
    return guide()['content']
