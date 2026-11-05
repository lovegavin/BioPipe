"""Desktop-first handoff of retained artifacts, independent of the canvas.

Only profile settings choose executables. Workflow data never supplies commands.
"""
from functools import lru_cache
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import threading
import time
from urllib.parse import urlparse

from .bytecode import io_path
from .documents import CommandError
from .user_config import UserConfig
from src.web.storage import FileLock


def system():
    return platform.system().lower().replace('darwin', 'macos')


def executable(path):
    path = Path(path).expanduser()
    if not path.is_absolute() or not path.is_file():
        raise ValueError('Choose an existing absolute application path')
    if path.suffix.lower() in {'.bat', '.cmd', '.ps1', '.lnk', '.py', '.sh'}:
        raise ValueError('Choose the application executable or GUI JAR, not a shell script/shortcut')
    if system() == 'windows' and path.suffix.lower() not in {'.exe', '.jar'}:
        raise ValueError('Windows viewers require an EXE or GUI JAR')
    if system() != 'windows' and path.suffix.lower() != '.jar' and not os.access(path, os.X_OK):
        raise ValueError('Application is not executable')
    return str(path.resolve())


@lru_cache(maxsize=128)
def discover(commands):
    """PATH and Windows App Paths only: no recursive disk or import scan."""
    for command in commands:
        found = shutil.which(command)
        if found:
            try:
                return executable(found)
            except ValueError:
                pass
    if system() == 'windows':
        import winreg
        for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
            for access in (winreg.KEY_READ | winreg.KEY_WOW64_64KEY, winreg.KEY_READ | winreg.KEY_WOW64_32KEY):
                for command in commands:
                    try:
                        with winreg.OpenKey(hive, 'Software\\Microsoft\\Windows\\CurrentVersion\\App Paths\\' + command, 0, access) as key:
                            return executable(winreg.QueryValue(key, None).strip('"'))
                    except (OSError, ValueError):
                        continue
    return None


def load_catalog(path):
    data = json.loads(io_path(path).read_text(encoding='utf-8'))
    if data.get('schema_version') != 1 or not isinstance(data.get('viewers'), list):
        raise ValueError('Viewer catalog needs schema_version=1 and viewers[]')
    result = {}
    for entry in data['viewers']:
        key = entry.get('id', '')
        if not re.fullmatch(r'[a-z][a-z0-9_-]{0,63}', key) or key in result:
            raise ValueError('Invalid or duplicate viewer ID')
        if entry.get('kind') not in {'desktop', 'web'} or entry.get('mode') not in {'file', 'manual'}:
            raise ValueError('Unknown viewer kind or launch mode')
        for field in ('name', 'domain', 'notes', 'source'):
            if not isinstance(entry.get(field), str):
                raise ValueError('Viewer metadata must contain name/domain/notes/source strings')
        extensions = entry.get('extensions')
        if not isinstance(extensions, list) or not extensions or any(not re.fullmatch(r'\.[a-z0-9.]+', x) for x in extensions):
            raise ValueError('Viewer extensions must be explicit lowercase file suffixes')
        # Documents that can execute code are never generic viewer inputs.
        if set(extensions) & {'.exe', '.jar', '.py', '.pml', '.pse', '.cxc', '.js', '.html', '.bat', '.cmd', '.sh', '.ps1', '.pkl'}:
            raise ValueError('Executable/script formats cannot be registered as viewer data')
        if entry['kind'] == 'web':
            url = urlparse(entry.get('url', ''))
            if url.scheme != 'https' or not url.hostname or url.username or url.password or url.query or url.fragment:
                raise ValueError('Web viewer must have a static HTTPS URL without credentials/query/fragment')
        else:
            if not isinstance(entry.get('commands'), list) or any(not isinstance(x, str) or '/' in x or '\\' in x for x in entry['commands']):
                raise ValueError('Discovery commands must be plain executable names')
            if not isinstance(entry.get('args'), list) or any(not isinstance(x, str) or any(c in x for c in '\r\n\0{}') for x in entry['args']):
                raise ValueError('Viewer arguments must be literal strings, not shell templates')
        result[key] = entry
    return result


class ViewerService:
    def __init__(self, application):
        self.app = application
        self.directory = application.service.directory / 'viewers'
        self.user_config = UserConfig(application.service.directory)

    def catalog(self):
        entries = load_catalog(Path(__file__).with_name('viewers.json'))
        custom = self.directory / 'catalog.json'
        if custom.is_file():
            entries.update(load_catalog(custom))
        return entries

    def settings(self):
        return self.user_config.read().get('viewers', {}).get('paths', {})

    def defaults(self):
        return self.user_config.read().get('viewers', {}).get('defaults', {})

    def set_default(self, extension, viewer):
        catalog = self.catalog()
        supported = {s for v in catalog.values() if v['kind'] == 'desktop' for s in v['extensions']}
        if extension not in supported and not (viewer is None and extension in self.defaults()):
            raise ValueError('Choose a registered file extension')
        if viewer is not None:
            entry = catalog.get(viewer)
            if not entry or entry['kind'] != 'desktop' or extension not in entry['extensions']:
                raise ValueError('Choose a compatible desktop viewer')
        def edit(config):
            defaults = config.setdefault('viewers', {}).setdefault('defaults', {})
            if viewer is None:
                defaults.pop(extension, None)
            else:
                defaults[extension] = viewer
        self.user_config.update(edit)
        return self.listing()

    def listing(self, refresh=False):
        if refresh:
            discover.cache_clear()
        settings = self.settings()
        result = []
        for key, entry in self.catalog().items():
            item = dict(entry)
            item['configured_path'] = settings.get(key)
            item['executable'] = None
            if entry['kind'] == 'web':
                item.update(available=True, status='web')
            elif system() not in entry.get('platforms', ['windows', 'linux', 'macos']):
                item.update(available=False, status='unsupported_system')
            else:
                candidate = settings.get(key) or discover(tuple(entry['commands']))
                try:
                    item['executable'] = executable(candidate) if candidate else None
                except ValueError:
                    pass
                ready = bool(item['executable'])
                reason = 'ready' if ready else 'not_found'
                if ready and Path(item['executable']).suffix.lower() == '.jar' and not discover(('javaw.exe', 'java.exe', 'java')):
                    ready, reason = False, 'java_required'
                if ready and system() == 'linux' and not (os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY')):
                    ready, reason = False, 'desktop_required'
                item.update(available=ready, status=reason)
            result.append(item)
        result.sort(key=lambda e: (e['kind'] == 'web', not e['available'], e['name'].casefold()))
        return {'schema_version': 1, 'viewers': result, 'defaults': self.defaults()}

    def configure(self, key, path):
        entry = self.catalog().get(key)
        if not entry or entry['kind'] != 'desktop':
            raise ValueError('Choose a registered desktop viewer')
        value = executable(path) if path else None
        def edit(config):
            settings = config.setdefault('viewers', {}).setdefault('paths', {})
            if value:
                settings[key] = value
            else:
                settings.pop(key, None)
        self.user_config.update(edit)
        return self.listing(refresh=True)

    def context(self, job, artifact, role):
        preview = self.app.artifacts.preview(job, artifact, limit=0)
        files = preview.get('files', [])
        selected = next((f for f in files if f['role'] == role and f.get('downloadable')), None)
        if selected is None:
            raise CommandError('file_unavailable', 'Select a retained output file role, not an external input', 404)
        return selected, files

    def options(self, job, artifact, role):
        selected, _ = self.context(job, artifact, role)
        name = selected['name'].lower()
        listing = self.listing()
        viewers = [v for v in listing['viewers'] if any(name.endswith(s) for s in v['extensions'])]
        # The most specific saved suffix wins (e.g. .vcf.gz before .gz).
        suffix = next((s for s in sorted(listing['defaults'], key=len, reverse=True) if name.endswith(s)), None)
        preferred = listing['defaults'].get(suffix) if suffix else None
        fallback = next((v['id'] for v in viewers if v['kind'] == 'desktop' and v['available']), None)
        return {'file': selected, 'viewers': viewers, 'default_viewer': preferred or fallback,
                'default_source': 'configured' if preferred else 'automatic'}

    def prepare(self, job, artifact, role):
        selected, files = self.context(job, artifact, role)
        primary = Path(self.app.artifacts.file(job, artifact, role)).resolve()
        if not primary.is_file():
            raise CommandError('file_unavailable', 'The retained result no longer exists', 404)
        # Include only associated indexes, not every large output in the artifact.
        names = {selected['name'] + suffix for suffix in ('.bai', '.crai', '.tbi', '.csi', '.fai', '.gzi')}
        names.add(str(Path(selected['name']).with_suffix('.bai')))
        names.add(str(Path(selected['name']).with_suffix('.crai')))
        companions = [f for f in files if f.get('downloadable') and f['role'] != role and f['name'] in names]
        paths = [(selected, primary)] + [(f, Path(self.app.artifacts.file(job, artifact, f['role'])).resolve()) for f in companions]
        if any(p.parent != primary.parent or p.name != f['name'] for f, p in paths):
            signature = [(f['role'], str(p), p.stat().st_size, p.stat().st_mtime_ns) for f, p in paths]
            key = hashlib.sha256(json.dumps(signature).encode()).hexdigest()
            folder = self.directory / 'files' / key
            with FileLock(folder.with_suffix('.lock')):
                folder.mkdir(parents=True, exist_ok=True)
                used = set()
                for f, source in paths:
                    name = f['name']
                    if Path(name).name != name or '\\' in name or ':' in name or name.casefold() in used:
                        raise ValueError('Ambiguous or unsafe output filenames')
                    used.add(name.casefold())
                    target = folder / name
                    if not target.is_file() or target.stat().st_size != source.stat().st_size:
                        pending = target.with_name(target.name + '.part')
                        try:
                            shutil.copyfile(io_path(source), io_path(pending))
                            io_path(pending).replace(io_path(target))
                        finally:
                            io_path(pending).unlink(missing_ok=True)
                primary = folder / selected['name']
        return {'path': str(primary), 'sidecars': [f['name'] for f in companions]}

    def open(self, job, artifact, role, viewer=None):
        options = self.options(job, artifact, role)
        viewer = viewer or options['default_viewer']
        entry = next((v for v in options['viewers'] if v['id'] == viewer), None)
        if not entry or entry['kind'] != 'desktop':
            if not viewer or options['default_source'] == 'configured' and viewer == options['default_viewer']:
                raise CommandError('viewer_unavailable', 'Choose an installed default viewer in Settings', 409)
            raise ValueError('Choose a compatible desktop viewer; web links require a user browser action')
        if not entry['available']:
            raise CommandError('viewer_unavailable', 'Configure an installed viewer application; status: ' + entry['status'], 409)
        prepared = self.prepare(job, artifact, role)
        path = prepared['path']
        if not any(path.lower().endswith(s) for s in entry['extensions']):
            raise ValueError('Resolved file type differs from the advertised output')
        program = executable(entry['executable'])
        argv = [program]
        if Path(program).suffix.lower() == '.jar':
            java = discover(('javaw.exe', 'java.exe', 'java'))
            if not java:
                raise ValueError('A Java runtime is required for this GUI JAR')
            argv = [java, '-jar', program]
        argv += entry['args']
        if entry['mode'] == 'file':
            argv.append(path)
            if viewer == 'cellxgene':
                argv.append('--open')
        self.directory.mkdir(parents=True, exist_ok=True)
        log_path = self.directory / 'launch.log'
        with io_path(log_path).open('a', encoding='utf-8') as log:
            log.write(f'\n{time.strftime("%Y-%m-%dT%H:%M:%S")} viewer={viewer} job={job} role={role}\n')
            log.flush()
            try:
                process = subprocess.Popen(argv, shell=False, cwd=str(Path(program).parent),
                                           stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                                           close_fds=True, **({'start_new_session': True} if os.name != 'nt' else
                                                             {'creationflags': subprocess.CREATE_BREAKAWAY_FROM_JOB}))
            except OSError as exc:
                raise CommandError('viewer_launch_failed', str(exc), 409) from exc
        # Reap without pipes or non-daemon executors that can block Studio exit.
        def monitor():
            code = process.wait()
            with io_path(log_path).open('a', encoding='utf-8') as log:
                log.write(f'viewer={viewer} pid={process.pid} exit={code}\n')
        threading.Thread(target=monitor, daemon=True, name='viewer-launch').start()
        return {**prepared, 'viewer': viewer, 'status': 'started', 'mode': entry['mode'],
                'pid': process.pid, 'log': str(log_path), 'notes': entry['notes']}
