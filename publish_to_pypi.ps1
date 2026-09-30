#!/bin/sh
set -eu
# This script is called from the project root via the convenience `publish` script
# It finds the br_pypi_publisher submodule and runs the Python script

# Get the directory where this script is located (br_pypi_publisher/scripts/)
script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
# Go up to br_pypi_publisher/ then up to project root
publisher_root=$(dirname "$script_dir")
repo_root=$(dirname "$publisher_root")

exec python "$script_dir/publish_to_pypi.py" "$@"
