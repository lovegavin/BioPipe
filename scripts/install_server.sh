#!/usr/bin/env bash
# Run beside install_server.py. No sudo or desktop is required.
set -euo pipefail
script_dir=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
installer="$script_dir/install_server.py"
args=("$@")
python=''
for ((i=0; i<${#args[@]}; i++)); do
  if [[ ${args[i]} == --python ]]; then
    ((i+=1))
    if ((i >= ${#args[@]})); then echo '--python requires a Python 3.11+ executable' >&2; exit 2; fi
    python=${args[i]}
  fi
done
if [[ -n "$python" ]]; then
  "$python" -I -c 'import sys; sys.exit(0 if sys.version_info >= (3,11) else 2)' || {
    echo 'The selected Python must be 3.11 or newer. Omit --python to bootstrap automatically.' >&2; exit 2;
  }
elif command -v python3 >/dev/null && python3 -I -c 'import sys, venv, ensurepip; sys.exit(0 if sys.version_info >= (3,11) else 2)' 2>/dev/null; then
  python=$(command -v python3)
fi
if [[ -n "$python" ]]; then exec "$python" -I "$installer" "${args[@]}"; fi
for arg in "${args[@]}"; do
  if [[ "$arg" == --help || "$arg" == -h ]]; then
    printf '%s\n' 'Operon server installation' \
      'bash install_server.sh [--prefix DIR] [--workspace DIR] [--version VERSION]' \
      '  --source CHECKOUT | --app-wheel APP.whl --library-wheel LIBRARY.whl' \
      '  --python PYTHON3.11+  --wheel-dir OFFLINE_WHEELS  --result FILE.json' \
      'Without Python, a checksum-pinned Linux x86_64 runtime is bootstrapped.'
    exit 0
  fi
done
if [[ $(uname -s) != Linux || $(uname -m) != x86_64 ]]; then
  echo 'Automatic Python bootstrap supports Linux x86_64. Supply --python on other Linux architectures.' >&2
  exit 2
fi
test -f "$installer" || { echo 'Keep install_server.sh and install_server.py together.' >&2; exit 2; }
work=$(mktemp -d "${TMPDIR:-/tmp}/operon-setup.XXXXXXXX")
touch "$work/.operon-bootstrap-owned"
cleanup() { if [[ -f "$work/.operon-bootstrap-owned" ]]; then rm -rf -- "$work"; fi; }
trap cleanup EXIT
umask 077
# Same pinned static manager used by operon.remote.provision.
url='https://conda.anaconda.org/conda-forge/linux-64/micromamba-2.10.0-0.tar.bz2'
archive_sha='9a97976244929bbae28fb1fae504e74a3e7e6d1932870e3a03321f01b7fbd07b'
binary_sha='701f39c06f8e6a670a0e186c8479b9e5c0502a2f0cda6cef65d83bdd2875e8bd'
echo 'Preparing the verified Python bootstrap (no system environment changes)' >&2
if command -v curl >/dev/null; then
  curl --fail --location --retry 3 --connect-timeout 30 --max-time 600 "$url" -o "$work/manager.tar.bz2" >&2
elif command -v wget >/dev/null; then
  wget --timeout=30 --tries=3 -O "$work/manager.tar.bz2" "$url" >&2
else
  echo 'Install curl or wget to download Python.' >&2; exit 2
fi
printf '%s  %s\n' "$archive_sha" "$work/manager.tar.bz2" | sha256sum -c - >&2
mkdir "$work/bin"
tar -xOjf "$work/manager.tar.bz2" bin/micromamba > "$work/bin/micromamba"
printf '%s  %s\n' "$binary_sha" "$work/bin/micromamba" | sha256sum -c - >&2
chmod 700 "$work/bin/micromamba"
unset CONDA_PREFIX CONDA_DEFAULT_ENV CONDA_SHLVL CONDA_PROMPT_MODIFIER CONDA_EXE CONDA_PYTHON_EXE MAMBA_EXE MAMBA_ROOT_PREFIX _CE_CONDA _CE_M PYTHONPATH PYTHONHOME
export MAMBA_ROOT_PREFIX="$work/cache"
"$work/bin/micromamba" --no-rc create -y -p "$work/controller" --override-channels \
  -c https://conda.anaconda.org/conda-forge python=3.11 pip >&2
# The final runtime is another complete prefix inside the chosen installation;
# it does not retain paths to this temporary controller or need it after exit.
"$work/controller/bin/python" -I "$installer" --manager "$work/bin/micromamba" "${args[@]}"
