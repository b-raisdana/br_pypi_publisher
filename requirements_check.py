from __future__ import annotations

import importlib.metadata
import re
import subprocess
import sys
from pathlib import Path


def _normalize_name(name: str) -> str:
    """Normalize a distribution name for importlib.metadata lookup (PEP 503)."""
    return re.sub(r"[-_.]+", "-", name).lower()


def _parse_requirements(path: Path) -> list[tuple[str, str]]:
    """Parse a requirements.txt file into (package_name, version_spec) pairs."""
    parsed: list[tuple[str, str]] = []
    for line in path.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("-"):
            continue
        token = re.split(r";", stripped, maxsplit=1)[0].split("#", 1)[0].strip()
        match = re.match(r"^(?P<name>[A-Za-z0-9_.\-]+)\s*(?P<spec>.*)$", token)
        if match:
            parsed.append((match.group("name"), match.group("spec").strip()))
    return parsed


def _version_tuple(version: str) -> tuple[int, ...]:
    return tuple(int(n) for n in re.findall(r"\d+", version))


def _satisfies(installed: str, spec: str) -> bool:
    """Return True if *installed* satisfies the version *spec* (e.g. '>=3.0')."""
    spec = spec.strip()
    if not spec:
        return True
    match = re.match(r"^(?P<op>>=|<=|==|!=|~=|>|<)?\s*(?P<req>.+)$", spec)
    if not match:
        return True
    op = match.group("op") or "=="
    inst = _version_tuple(installed)
    req = _version_tuple(match.group("req"))
    length = max(len(inst), len(req))
    inst = inst + (0,) * (length - len(inst))
    req = req + (0,) * (length - len(req))
    if op == ">=":
        return inst >= req
    if op == ">":
        return inst > req
    if op == "<=":
        return inst <= req
    if op == "<":
        return inst < req
    if op == "!=":
        return inst != req
    if op == "~=":
        return inst >= req and (len(req) <= 1 or inst[: len(req) - 1] == req[: len(req) - 1])
    return inst == req


def _check_errors(req_path: Path) -> list[dict[str, str | None]]:
    """Check *req_path* against the currently running interpreter.

    Returns a list of error descriptors; an empty list means all satisfied.
    """
    errors: list[dict[str, str | None]] = []
    for name, spec in _parse_requirements(req_path):
        try:
            installed = importlib.metadata.version(_normalize_name(name))
        except importlib.metadata.PackageNotFoundError:
            errors.append({"name": name, "spec": spec, "installed": None})
            continue
        if not _satisfies(installed, spec):
            errors.append({"name": name, "spec": spec, "installed": installed})
    return errors


def _format_errors(req_path: Path, errors: list[dict[str, str | None]], install_python: Path) -> str:
    missing = [e for e in errors if e["installed"] is None]
    outdated = [e for e in errors if e["installed"] is not None]
    lines: list[str] = [f"ERROR: {len(errors)} requirement(s) from {req_path} are not satisfied."]
    if missing:
        lines += ["", "Missing:"]
        for e in missing:
            spec = f" {e['spec']}" if e["spec"] else ""
            lines.append(f"  - {e['name']}{spec}")
    if outdated:
        lines += ["", "Outdated:"]
        for e in outdated:
            spec = f" {e['spec']}" if e["spec"] else ""
            lines.append(f"  - {e['name']} {e['installed']} (needs{spec})")
    lines += [
        "",
        "Install/upgrade them with:",
        f"  {install_python} -m pip install -r {req_path}",
    ]
    return "\n".join(lines)


def _find_repo_root(start: Path) -> Path | None:
    """Find the host repository root that owns this submodule.

    The submodule lives at ``<repo_root>/br_pypi_publisher``, so the host root
    is the first ancestor directory containing a ``.venv`` (or, failing that, a
    ``.git``/``pyproject.toml`` pair).
    """
    for candidate in (start.parent, *start.parents):
        if (candidate / ".venv").is_dir():
            return candidate
    for candidate in (start.parent, *start.parents):
        if (candidate / ".git").exists() and (candidate / "pyproject.toml").exists():
            return candidate
    return None


def _find_venv_python(repo_root: Path) -> Path | None:
    """Return the virtualenv's Python executable, if a ``.venv`` exists."""
    venv_dir = repo_root / ".venv"
    if not venv_dir.is_dir():
        return None
    bindir = "Scripts" if sys.platform == "win32" else "bin"
    exe = "python.exe" if sys.platform == "win32" else "python"
    candidate = venv_dir / bindir / exe
    return candidate if candidate.exists() else None


def check_requirements() -> None:
    """Verify br_pypi_publisher/requirements.txt is satisfied in the repo venv.

    Locates ``requirements.txt`` next to this module, resolves the owning host
    repository's ``.venv``, and checks every requirement there. Falls back to
    the currently running interpreter when no ``.venv`` is found. Exits the
    process with a remediation hint when any requirement is missing or outdated.
    """
    script_dir = Path(__file__).resolve().parent
    req_path = script_dir / "requirements.txt"
    if not req_path.exists():
        return

    repo_root = _find_repo_root(script_dir) or script_dir.parent
    venv_python = _find_venv_python(repo_root)
    module = Path(__file__).resolve()

    if venv_python is not None and venv_python.resolve() != Path(sys.executable).resolve():
        # The venv exists but is not the active interpreter: check it directly
        # so we validate the real environment the scripts shell out to.
        result = subprocess.run(
            [str(venv_python), str(module), str(req_path)],
            check=False,
        )
        if result.returncode != 0:
            sys.exit(result.returncode)
        return

    errors = _check_errors(req_path)
    if errors:
        sys.stderr.write(_format_errors(req_path, errors, Path(sys.executable).resolve()))
        sys.stderr.flush()
        sys.exit(1)


if __name__ == "__main__":
    # CLI mode: invoked as `<python> requirements_check.py <requirements.txt>`.
    # Used by check_requirements() to validate a target virtualenv.
    req_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent / "requirements.txt"
    errors = _check_errors(req_path)
    if errors:
        sys.stderr.write(_format_errors(req_path, errors, Path(sys.executable)))
        sys.stderr.flush()
        sys.exit(1)
