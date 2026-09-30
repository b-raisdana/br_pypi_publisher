#!/usr/bin/env python3
import glob
import os
import re
import subprocess
import sys
import tomllib
from datetime import datetime, timezone
from pathlib import Path

from requirements_check import check_requirements


def run(cmd, **kwargs):
    print(f"+ {' '.join(cmd)}")
    result = subprocess.run(cmd, check=False, **kwargs)
    if result.returncode != 0:
        sys.exit(result.returncode)
    return result


def load_config(repo_root: Path) -> dict:
    config_path = repo_root / ".br-pypi-publisher.toml"
    if config_path.exists():
        with open(config_path, "rb") as f:
            data = tomllib.load(f)
            return data.get("tool", {}).get("br_pypi_publisher", {})
    return {}


def load_env(repo_root: Path):
    env_path = repo_root / ".env"
    if not env_path.exists():
        print("ERROR: .env file not found at", env_path)
        sys.exit(1)
    env_vars = {}
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            key, _, value = line.partition("=")
            env_vars[key.strip()] = value.strip()
    return env_vars


def parse_version(pyproject: Path) -> str:
    content = pyproject.read_text()
    match = re.search(r'^version = "([^"]+)"', content, re.MULTILINE)
    if not match:
        print("ERROR: Could not parse current version from pyproject.toml")
        sys.exit(1)
    return match.group(1)


def bump_version(version: str, bump_type: str) -> str:
    major, minor, patch = map(int, version.split("."))
    if bump_type == "major":
        major += 1
        minor = 0
        patch = 0
    elif bump_type == "minor":
        minor += 1
        patch = 0
    elif bump_type in ("bug fix", "bugfix", "patch"):
        patch += 1
    else:
        print(f"ERROR: Invalid release type '{bump_type}'. Use: major, minor, or bug fix")
        sys.exit(1)
    return f"{major}.{minor}.{patch}"


def update_pyproject_version(pyproject: Path, new_version: str):
    content = pyproject.read_text()
    content = re.sub(
        r'^version = "([^"]+)"',
        f'version = "{new_version}"',
        content,
        count=1,
        flags=re.MULTILINE,
    )
    pyproject.write_text(content)


def get_changelog_body(repo_root: Path) -> str:
    result = subprocess.run(
        ["git", "describe", "--tags", "--abbrev=0"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    last_tag = result.stdout.strip() if result.returncode == 0 else ""
    if last_tag:
        cmd = ["git", "log", "--oneline", "--graph", "--decorate", f"{last_tag}..HEAD"]
    else:
        cmd = ["git", "log", "--oneline", "--graph", "--decorate"]
    result = subprocess.run(cmd, cwd=repo_root, capture_output=True, text=True, check=False)
    return result.stdout


def update_changelog(changelog: Path, new_version: str, log_body: str):
    if changelog.exists():
        content = changelog.read_text()
    else:
        print(f'Changelog file not fount at {changelog}')
        content = ""
    today = datetime.now(timezone.utc).date().isoformat()
    new_section = (
        f"## [{new_version}] - {today}\n\n### Added\n\n- \n\n### Changed\n\n- \n\n### Fixed\n\n- \n\n{log_body}"
    )
    pattern = rf"## \[{re.escape(new_version)}\] - .*?(?=\n## \[|$)"
    content = re.sub(pattern, "", content, flags=re.DOTALL)
    content = content.replace("# Changelog", f"# Changelog\n\n{new_section}", 1)
    changelog.write_text(content)


def _tracked_file_snapshot(repo_root: Path) -> dict[str, bytes]:
    """Snapshot every tracked file's contents so hook auto-fixes are detectable.

    Git normalizes line endings (core.autocrlf=true) and may stage fixes
    itself, so `git diff`/`git status` cannot reliably signal that a fixing
    hook modified a file. Comparing raw file bytes is the robust signal.
    """
    out = subprocess.run(
        ["git", "ls-files"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    ).stdout
    snapshot: dict[str, bytes] = {}
    for line in out.splitlines():
        path = repo_root / line
        if path.is_file():
            snapshot[line] = path.read_bytes()
    return snapshot


def detect_active_env() -> tuple[str, Path, Path] | None:
    """Return (kind, root, scripts) for the active environment, or None.

    Accepts both standard-library venvs and conda environments. ``None`` means
    no environment is active and the process must not continue.
    """
    prefix = Path(sys.prefix)
    if prefix == Path(sys.base_prefix):
        return None
    scripts = prefix / ("Scripts" if os.name == "nt" else "bin")
    if not scripts.is_dir():
        return None
    conda_prefix = os.environ.get("CONDA_PREFIX")
    try:
        same_as_conda = conda_prefix is not None and Path(conda_prefix).resolve() == prefix.resolve()
    except OSError:
        same_as_conda = False
    kind = "conda" if same_as_conda or (prefix / "conda-meta").is_dir() else "venv"
    return kind, prefix, scripts


def require_active_env():
    """Stop the process unless a venv or conda environment is active.

    Every tool it drives (build, twine, pre-commit) must come from the same
    interpreter as the host project, so a base-interpreter run is a hard error
    rather than a confusing 'No module named build' later on.
    """
    detected = detect_active_env()
    if detected is None:
        print("ERROR: No active environment detected.")
        print(f"       Interpreter    : {sys.executable}")
        print(f"       Base interpreter: {sys.base_prefix}")
        print("       br_pypi_publisher must run inside a venv or conda environment.")
        print("       Activate one first, e.g.:")
        print("         .\\.venv\\Scripts\\Activate.ps1")
        print("         conda activate <env-name>")
        sys.exit(1)
    kind, prefix, scripts = detected
    print(f"Using Python: {sys.executable}")
    print(f"Active environment ({kind}): {prefix}")
    print(f"Environment scripts: {scripts}")


def toolchain_env(repo_root: Path) -> dict:
    """Environment that pins every child tool to the active environment.

    Bare ``python`` is not trustworthy: on Windows a venv launcher resolved by
    bare name can fall back to the base interpreter, and the repo's ./build/
    directory then shadows the real build package. Invoking sys.executable by
    full path avoids that; __PYVENV_LAUNCHER__ repairs the same fallback for
    the bare-name invocations we cannot control, such as the
    ``language: system`` pre-commit hooks (entry: python -m ...).
    """
    kind, _, scripts = detect_active_env() or ("venv", Path(sys.prefix), Path(sys.prefix))
    env = os.environ.copy()
    env["SKIP_NO_COMMIT_TO_MAIN"] = "1"
    if kind == "venv":
        # Only meaningful for venv launchers; a conda interpreter resolves its
        # own prefix correctly and must not be pointed at a pyvenv.cfg lookup.
        env["__PYVENV_LAUNCHER__"] = sys.executable
    # The git pre-commit hook sets these env vars before running pre-commit;
    # replicate them here so the br_pre_commit hooks (ratchet, backup, ...)
    # resolve their own repo root and import paths the same way.
    br_pre_commit_root = repo_root / "br_pre_commit"
    env.setdefault("USER_REPO_ROOT", str(repo_root))
    env.setdefault("BR_PRE_COMMIT_REPO_ROOT", str(br_pre_commit_root))
    env["PYTHONPATH"] = str(br_pre_commit_root / "src") + os.pathsep + env.get("PYTHONPATH", "")
    # On Windows, subprocess resolves executables from the *process* PATH, not
    # the env= dict, so prepend to os.environ and resolve the binary explicitly.
    env["PATH"] = str(scripts) + os.pathsep + env.get("PATH", "")
    os.environ["PATH"] = env["PATH"]
    return env


def resolve_build_command(build_command: str) -> list[str]:
    """Split a configured build command, pinning its interpreter to the active env."""
    parts = build_command.split()
    if parts and Path(parts[0]).name.lower().startswith("python"):
        parts[0] = sys.executable
    return parts


def run_precommit(repo_root: Path, env: dict):
    pre_commit_cmd = [sys.executable, "-m", "pre_commit", "run", "--all-files"]
    for attempt in range(3):
        print(f"Running pre-commit checks... (attempt {attempt + 1})")
        before = _tracked_file_snapshot(repo_root)
        result = subprocess.run(
            pre_commit_cmd,
            cwd=repo_root,
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )
        print(result.stdout)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        after = _tracked_file_snapshot(repo_root)
        if after != before:
            print("Staging pre-commit auto-fixes...")
            run(["git", "add", "-A"], cwd=repo_root)
            continue
        if re.search(r"^(ruff|pytest|incremental ratchet).*Failed", result.stdout, re.MULTILINE):
            print("ERROR: Pre-commit checks failed. Fix issues and retry.")
            sys.exit(1)
        if result.returncode != 0:
            print("ERROR: Pre-commit checks failed. Fix issues and retry.")
            sys.exit(1)
        return
    print("ERROR: Pre-commit auto-fixes did not converge after retries.")
    sys.exit(1)


def find_repo_root(start: Path) -> Path:
    for candidate in (start.parent, *start.parents):
        if (candidate / ".git").exists() and (candidate / "pyproject.toml").exists():
            return candidate
    return start.parent


def main():
    check_requirements()
    script_dir = Path(__file__).resolve().parent
    repo_root = find_repo_root(script_dir)

    os.chdir(repo_root)

    require_active_env()
    env = toolchain_env(repo_root)

    config = load_config(repo_root)
    release_branch = config.get("release_branch", "main")
    package_name = config.get("package_name", "unknown-package")
    changelog_path = config.get("changelog_path", "CHANGELOG.md")
    skip_precommit = config.get("skip_precommit", False)
    build_command = config.get("build_command", "python -m build")

    current_branch = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    ).stdout.strip()
    if current_branch != release_branch:
        print(f"ERROR: Must be on '{release_branch}' to release. Current branch: {current_branch}")
        sys.exit(1)

    env_vars = load_env(repo_root)
    pypi_api_key = env_vars.get("PYPI_API_KEY")
    if not pypi_api_key:
        print("ERROR: PYPI_API_KEY is not set in .env")
        sys.exit(1)

    pyproject = repo_root / "pyproject.toml"
    current_version = parse_version(pyproject)

    bump_type = sys.argv[1] if len(sys.argv) > 1 else ""
    while not bump_type:
        bump_type = input("Release type (major/minor/bug fix): ").strip()

    new_version = bump_version(current_version, bump_type)
    print(f"Bumping version: {current_version} -> {new_version}")

    update_pyproject_version(pyproject, new_version)

    changelog = repo_root / changelog_path
    log_body = get_changelog_body(repo_root)
    update_changelog(changelog, new_version, log_body)

    if not skip_precommit:
        run_precommit(repo_root, env)

    print("Building package...")
    run(resolve_build_command(build_command), cwd=repo_root, env=env)

    print("Publishing to PyPI...")
    dist_files = sorted(glob.glob(str(repo_root / "dist" / f"*{new_version}*")))
    if not dist_files:
        print(f"ERROR: no distributions found in {repo_root / 'dist'} for version {new_version}")
        sys.exit(1)
    run(
        [
            sys.executable,
            "-m",
            "twine",
            "upload",
            *dist_files,
            "-u",
            "__token__",
            "-p",
            pypi_api_key,
        ],
        cwd=repo_root,
        env=env,
    )

    run(["git", "add", "pyproject.toml", changelog_path], cwd=repo_root)
    run(["git", "commit", "-m", f"chore: release v{new_version}"], cwd=repo_root)
    run(["git", "push", "origin", release_branch], cwd=repo_root)

    tag_name = f"v{new_version}"
    print(f"Creating tag {tag_name}...")
    run(["git", "tag", tag_name], cwd=repo_root)
    run(["git", "push", "origin", tag_name], cwd=repo_root)

    print(f"Successfully published version {new_version} to PyPI")
    print(f"View at: https://pypi.org/project/{package_name}/{new_version}/")


if __name__ == "__main__":
    main()
