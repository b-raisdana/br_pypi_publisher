# br_pypi_publisher

A reusable Git submodule for publishing Python packages to PyPI. Designed to be used across multiple repositories with a consistent release workflow.

## Features

- **Automated version bumping** (major, minor, patch/bug fix)
- **Changelog generation** from git history
- **Pre-commit integration** for quality checks
- **PyPI publishing** with twine
- **Git tagging** and pushing
- **Configurable** for different projects

## Quick Start

### As a Git Submodule (Recommended)

Add this repository as a submodule to your project:

```bash
# From your project root
git submodule add https://github.com/your-org/br_pypi_publisher.git br_pypi_publisher
git submodule update --init --recursive
```

Then run the installer:

```bash
bash br_pypi_publisher/install.sh
```

### Manual Setup

Copy the `scripts/` directory to your project and ensure you have:
- Python 3.8+
- `build`, `twine`, `pre-commit` installed
- A `.env` file with `PYPI_API_KEY`

## Installation

Run the installer script from your project root:

```bash
bash br_pypi_publisher/install.sh
```

This will:
1. Create a `.env.example` template if it doesn't exist
2. Set up the pre-commit hook (via br_pre_commit submodule)
3. Create a convenience `publish` script in your project root
4. Add a `publish` command to your PATH (optional)

## Usage

After installation, you can publish a new version:

```bash
# Interactive mode (prompts for bump type)
./publish

# Or specify bump type directly
./publish minor
./publish major
./publish bug fix
```

### Bump Types

| Type | Example | Description |
|------|---------|-------------|
| `major` | 1.0.0 → 2.0.0 | Breaking changes |
| `minor` | 1.0.0 → 1.1.0 | New features (backward compatible) |
| `bug fix` / `patch` | 1.0.0 → 1.0.1 | Bug fixes (backward compatible) |

## What Happens During Release

1. **Validates** you're on `main` branch
2. **Loads** `PYPI_API_KEY` from `.env`
3. **Parses** current version from `pyproject.toml`
4. **Bumps** version based on bump type
5. **Updates** `pyproject.toml` with new version
6. **Generates** changelog entry from git log
7. **Runs** pre-commit checks (linting, tests, etc.)
8. **Builds** package with `python -m build`
9. **Publishes** to PyPI via `twine`
10. **Commits** version and changelog changes
11. **Tags** the release (e.g., `v1.2.3`)
12. **Pushes** commits and tags to origin

## Configuration

### Required Files in Your Project

- `pyproject.toml` - Must contain `version = "x.y.z"`
- `.env` - Must contain `PYPI_API_KEY=your_token`
- `CHANGELOG.md` - Will be updated automatically

### Optional Configuration

Create a `.br-pypi-publisher.toml` in your project root to customize:

```toml
# .br-pypi-publisher.toml
[tool.br_pypi_publisher]
# Branch to release from (default: "main")
release_branch = "main"

# Package name for PyPI URL display
package_name = "my-package"

# Custom changelog path (default: "CHANGELOG.md")
changelog_path = "CHANGELOG.md"

# Skip pre-commit checks (not recommended)
skip_precommit = false

# Custom build command (default: "python -m build")
build_command = "python -m build"

# Custom twine upload command
twine_command = "twine upload dist/*"
```

## Integration with br_pre_commit

This repository includes `br_pre_commit` as a submodule for pre-commit hooks. The installer automatically sets up the shared pre-commit wrapper.

To customize hooks, create `.pre-commit-config.yaml` in your project root (see br_pre_commit docs for details).

## Project Structure

```
br_pypi_publisher/
├── install.sh              # Installer script
├── publish_to_pypi.sh      # Root convenience script
├── scripts/
│   ├── publish_to_pypi.py  # Main release script
│   └── publish_to_pypi.sh  # Wrapper script
├── br_pre_commit/          # Git submodule (pre-commit infrastructure)
├── .gitmodules
└── README.md
```

## Requirements

- Git
- Python 3.8+
- `build` package (`pip install build`)
- `twine` package (`pip install twine`)
- `pre-commit` package (`pip install pre-commit`)
- PyPI API token with publish permissions

## Example Workflow

```bash
# 1. Add submodule to your project
git submodule add https://github.com/your-org/br_pypi_publisher.git br_pypi_publisher
git submodule update --init --recursive

# 2. Install
bash br_pypi_publisher/install.sh

# 3. Configure .env with your PyPI token
echo "PYPI_API_KEY=pypi-..." > .env

# 4. Make changes, commit to feature branch
git switch -c feature/new-feature
# ... make changes ...
git commit -am "feat: add new feature"

# 5. Merge to main
git switch main
git merge feature/new-feature

# 6. Release!
./publish minor
```

## Updating the Submodule

To update to the latest version of br_pypi_publisher:

```bash
cd br_pypi_publisher
git pull origin main
cd ..
git add br_pypi_publisher
git commit -m "chore: update br_pypi_publisher submodule"
bash br_pypi_publisher/install.sh  # Re-run installer if needed
```

## License

MIT License - See LICENSE file for details.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests: `./pre-commit` (if installed)
5. Submit a PR

## Related Projects

- [br_pre_commit](https://github.com/your-org/br_pre_commit) - Shared pre-commit infrastructure
- [br-logging-and-profiling](https://github.com/your-org/br-logging-and-profiling) - Example project using this publisher
