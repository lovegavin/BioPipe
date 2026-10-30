"""On-demand R runtime and immutable requirement-specific libraries.

Discovery reads declarations only. Installation never modifies a user's R
library. Receipts are committed only after version and load probes succeed.
"""
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import tarfile
import tempfile
import urllib.request
import uuid

from packaging.specifiers import SpecifierSet
from biopipe_sdk.r_dependencies import validate_r
from src.web.storage import FileLock, atomic_json


def runtime_root():
    if os.environ.get('BIOPIPE_R_HOME'):
        return Path(os.environ['BIOPIPE_R_HOME']).expanduser().resolve()
    from src.web.profile import resolve_profile
    return resolve_profile(Path(__file__).resolve().parents[1]).data_dir / 'runtimes/r'


def _quote(value):
    return json.dumps(str(value), ensure_ascii=True)


def _call(args, **kwargs):
    from biopipe.plugins import run_process, process_context
    import threading
    previous = getattr(process_context, 'cancel', None)
    if previous is None:
        process_context.cancel = threading.Event()
    try:
        return run_process(args, **kwargs)
    finally:
        process_context.cancel = previous


class RRuntime:
    def __init__(self, root=None):
        self.root = Path(root).resolve() if root is not None else runtime_root()

    def key(self, spec):
        return hashlib.sha256(json.dumps(validate_r(spec), sort_keys=True).encode()).hexdigest()[:24]

    def _r_version(self, executable):
        return _call([executable, '--vanilla', '-e', 'cat(as.character(getRversion()))'], env=self._env(None, executable)).strip()

    def _bootstrap(self, spec):
        override = os.environ.get('BIOPIPE_RSCRIPT')
        candidates = [override] if override else [shutil.which('Rscript')]
        for candidate in filter(None, candidates):
            try:
                if SpecifierSet(spec['version']).contains(self._r_version(candidate)):
                    return str(Path(candidate).resolve())
            except (ValueError, OSError):
                if override:
                    raise
        if override:
            raise ValueError('BIOPIPE_RSCRIPT does not satisfy the declared R version')
        system, machine = platform.system(), platform.machine().lower()
        target = {('Windows', 'amd64'): 'win-64', ('Windows', 'x86_64'): 'win-64',
                  ('Linux', 'x86_64'): 'linux-64', ('Linux', 'aarch64'): 'linux-aarch64',
                  ('Darwin', 'arm64'): 'osx-arm64', ('Darwin', 'x86_64'): 'osx-64'}.get((system, machine))
        if target is None:
            raise ValueError('Automatic R bootstrap is unavailable on this architecture; set BIOPIPE_RSCRIPT')
        executable = self.root / ('micromamba.exe' if system == 'Windows' else 'micromamba')
        # Fetch one executable member only; never extract arbitrary archive paths.
        if not executable.exists():
            with tempfile.TemporaryDirectory(dir=self.root) as tmp:
                archive = Path(tmp) / 'micromamba.tar.bz2'
                with urllib.request.urlopen(f'https://micro.mamba.pm/api/micromamba/{target}/latest', timeout=120) as source, archive.open('wb') as dest:
                    shutil.copyfileobj(source, dest)
                with tarfile.open(archive) as bundle:
                    member = bundle.getmember('Library/bin/micromamba.exe' if system == 'Windows' else 'bin/micromamba')
                    if not member.isfile():
                        raise ValueError('Invalid micromamba archive')
                    temporary = Path(tmp) / executable.name
                    with bundle.extractfile(member) as source, temporary.open('wb') as dest:
                        shutil.copyfileobj(source, dest)
                    temporary.chmod(0o755)
                    temporary.replace(executable)
        prefix = self.root / 'interpreters' / hashlib.sha256(spec['version'].encode()).hexdigest()[:16]
        rscript = prefix / ('Scripts/Rscript.exe' if system == 'Windows' else 'bin/Rscript')
        if not rscript.is_file():
            installer_home = self.root / 'installer-home'
            installer_home.mkdir(exist_ok=True)
            _call([executable, '--no-rc', 'install' if (prefix / 'conda-meta').is_dir() else 'create', '-y', '-p', prefix, '--override-channels', '-c', 'conda-forge',
                   '--strict-channel-priority', 'r-base' + spec['version']], timeout=1800,
                  env={**os.environ, 'MAMBA_ROOT_PREFIX': str(self.root / 'mamba'),
                       'CONDA_PKGS_DIRS': str(self.root / 'p'),
                       'HOME': str(installer_home), 'USERPROFILE': str(installer_home)})
        if not rscript.is_file() or not SpecifierSet(spec['version']).contains(self._r_version(rscript)):
            raise ValueError('Managed R installation did not satisfy the declaration')
        return str(rscript)

    @staticmethod
    def _env(library, executable=None):
        env = {k: v for k, v in os.environ.items() if not k.startswith(('R_LIBS', 'R_PROFILE', 'R_ENVIRON', 'R_HOME'))}
        if library is not None:
            env.update(R_LIBS_USER=str(library), R_LIBS_SITE=str(library))
        if executable:
            prefix = Path(executable).resolve().parent.parent
            if (prefix / 'conda-meta').is_dir():
                env['CONDA_PREFIX'] = str(prefix)
                env['R_HOME'] = str(prefix / 'lib/R')
                env['PATH'] = os.pathsep.join(str(prefix / p) for p in ('lib/R/bin/x64', 'Library/bin', 'Scripts', 'bin')) + os.pathsep + env.get('PATH', '')
                cert = prefix / 'Library/ssl/cacert.pem'
                if cert.is_file():
                    env.setdefault('SSL_CERT_FILE', str(cert))
        return env

    def _probe(self, executable, library, spec):
        code = '.libPaths(c(' + _quote(library) + ', .Library));\n'
        code += 'cat("BIOPIPE_R\\t",as.character(getRversion()),"\\n",sep="");\n'
        for package in spec['packages']:
            name = _quote(package['name'])
            code += f'loadNamespace({name}); cat({name},as.character(packageVersion({name})),sep="\\t");cat("\\n");\n'
        result = _call([executable, '--vanilla', '-e', code], env=self._env(library, executable))
        versions = dict(line.split('\t', 1) for line in result.splitlines() if '\t' in line)
        if not SpecifierSet(spec['version']).contains(versions.get('BIOPIPE_R', '0')):
            raise ValueError('R runtime version mismatch')
        for package in spec['packages']:
            version = versions.get(package['name'], '0').replace('-', '.')
            if not SpecifierSet(package['version']).contains(version) or version == '0':
                raise ValueError(f"R package {package['name']} requires {package['version']}; installed {version}")
        return versions

    def _install(self, executable, library, spec):
        code = f'options(repos=c(CRAN="https://cloud.r-project.org")); .libPaths(c({_quote(library)}, .Library));\n'
        for package in spec['packages']:
            name = _quote(package['name'])
            if package['source'] == 'bioconductor':
                code += 'if (!requireNamespace("BiocManager",quietly=TRUE)) install.packages("BiocManager");\n'
                release = ',version=' + _quote(spec['bioconductor']) if spec.get('bioconductor') else ''
                code += f'BiocManager::install({name},ask=FALSE,update=FALSE{release});\n'
            else:
                constraint = package['version']
                if constraint.startswith('==') and ',' not in constraint and '*' not in constraint:
                    code += 'if (!requireNamespace("remotes",quietly=TRUE)) install.packages("remotes");\n'
                    code += f'remotes::install_version({name},version={_quote(constraint[2:])},upgrade="never",dependencies=NA);\n'
                else:
                    code += f'install.packages({name},dependencies=NA);\n'
        _call([executable, '--vanilla', '-e', code], env=self._env(library, executable), timeout=1800)

    def ensure(self, declaration, *, repair=True, verify=False):
        spec = validate_r(declaration)
        key = self.key(spec)
        self.root.mkdir(parents=True, exist_ok=True)
        with FileLock(self.root / 'install.lock', timeout=3600):
            receipt = self.root / 'receipts' / (key + '.json')
            if receipt.is_file():
                record = json.loads(receipt.read_text(encoding='utf-8'))
                if record.get('spec') == spec and Path(record['executable']).is_file() and Path(record['library']).is_dir():
                    try:
                        if verify:
                            self._probe(record['executable'], record['library'], spec)
                        return record
                    except (ValueError, OSError):
                        if not repair:
                            raise
            if not repair:
                raise ValueError('R dependencies are not ready; run the dependency check with repair enabled')
            executable = self._bootstrap(spec)
            # A new directory on every attempted repair; never mutate a library
            # that a previously prepared/running job might still be using.
            library = self.root / 'libraries' / (key + '-' + uuid.uuid4().hex[:8])
            library.mkdir(parents=True)
            self._install(executable, library, spec)
            versions = self._probe(executable, library, spec)
            record = {'spec': spec, 'executable': executable, 'library': str(library.resolve()), 'versions': versions}
            atomic_json(receipt, record)
            return record


def run_r(context, declaration, script, *, inputs=None, timeout=1800):
    """Execute author R code with frozen JSON values and disk input references.

    R receives ``params``, ``inputs`` and ``output_dir``. Script text belongs in
    the operator's Python code so v3 code hashing/pinning covers it. No matrices
    are serialized in JSON. Output files can be registered with register_figure.
    """
    runtime = RRuntime()
    context.log('Preparing R dependencies')
    record = runtime.ensure(declaration)
    directory = context.artifact_path('r-' + uuid.uuid4().hex[:12] + '/parameters.json').parent
    request = {'params': context.step_params, 'inputs': inputs or {}, 'output_dir': str(directory)}
    atomic_json(directory / 'parameters.json', request)
    wrapper = f'.libPaths(c({_quote(record["library"])},.Library));\n'
    wrapper += 'request <- jsonlite::fromJSON(commandArgs(trailingOnly=TRUE)[1], simplifyVector=FALSE)\n'
    wrapper += 'params <- request$params; inputs <- request$inputs; output_dir <- request$output_dir\n'
    path = directory / 'plot.R'
    path.write_text(wrapper + script, encoding='utf-8')
    context.log('Running R', versions=record['versions'])
    try:
        output = _call([record['executable'], '--vanilla', path, directory / 'parameters.json'],
                       env=runtime._env(record['library'], record['executable']), timeout=timeout)
        if output.strip():
            context.log(output.strip())
    except Exception as exc:
        context.log('R failed: ' + str(exc))
        raise
    return directory
