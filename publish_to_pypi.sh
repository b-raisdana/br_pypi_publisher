#!/bin/sh
set -eu
script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)

# Always run through the active environment (venv or conda). Resolving a bare
# `python` can land on the base interpreter, which has no build/twine/pre-commit.
py=""
if [ -n "${VIRTUAL_ENV:-}" ]; then
    for c in "$VIRTUAL_ENV/bin/python" "$VIRTUAL_ENV/Scripts/python.exe"; do
        [ -x "$c" ] && py="$c" && break
    done
elif [ -n "${CONDA_PREFIX:-}" ]; then
    for c in "$CONDA_PREFIX/bin/python" "$CONDA_PREFIX/python.exe"; do
        [ -x "$c" ] && py="$c" && break
    done
fi
[ -z "$py" ] && py=$(command -v python || command -v python3 || true)

if [ -z "$py" ]; then
    echo "ERROR: no python found. Activate a venv or conda environment first." >&2
    exit 1
fi

exec "$py" "$script_dir/publish_to_pypi.py" "$@"