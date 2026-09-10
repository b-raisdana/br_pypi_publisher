#!/bin/sh
set -eu
cd "$(dirname "$0")"
exec ./scripts/publish_to_pypi.sh "$@"
