#!/usr/bin/env bash
# Operon Operator Library: install the dependencies declared by the library.
#
#   ./install-dependencies.sh --profile-dir /srv/operon --dry-run
#   ./install-dependencies.sh --profile-dir /srv/operon
#   ./install-dependencies.sh --profile-dir /srv/operon --tools
#
# The script re-launches itself with the interpreter recorded in server.json,
# so the calling python only needs to be a recent Python 3.
set -euo pipefail
DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="${PYTHON:-}"
if [ -z "$PYTHON_BIN" ]; then
  if command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN=python3
  elif command -v python >/dev/null 2>&1; then
    PYTHON_BIN=python
  else
    echo "python3 was not found; set PYTHON=/path/to/python and retry." >&2
    exit 1
  fi
fi
exec "$PYTHON_BIN" "$DIR/install_dependencies.py" "$@"
