from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from requirements_check import check_requirements


def run(
    command: list[str],
    *,
    cwd: Path,
) -> str:
    result = subprocess.run(
        command,
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def ensure_kilo_cli() -> None:
    """Install Kilo CLI if it is not already available."""
    if shutil.which("kilo") is None:
        if shutil.which("npm") is None:
            raise RuntimeError("Kilo CLI is not installed and npm was not found. Install Node.js/npm first.")

        print("Kilo CLI not found. Installing @kilocode/cli...")
        subprocess.run(
            ["npm", "install", "--global", "@kilocode/cli"],
            check=True,
        )

    try:
        version = run(["kilo", "--version"], cwd=Path.cwd())
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        raise RuntimeError("Kilo CLI installation failed or 'kilo' is not available on PATH.") from exc

    print(f"Using Kilo CLI: {version}")


def get_previous_release_tag(repo: Path) -> str:
    """Return the most recent tag reachable before HEAD."""
    try:
        return run(
            [
                "git",
                "describe",
                "--tags",
                "--abbrev=0",
                "HEAD^",
            ],
            cwd=repo,
        )
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            "Could not determine the previous release tag. Make sure the repository has at least one previous tag."
        ) from exc


def generate_changelog(
    repo: Path,
    previous_tag: str,
) -> str:
    """Generate a changelog from previous_tag through the current HEAD."""
    prompt = f"""
Generate a changelog for all changes from release tag
{previous_tag} to the current HEAD.

You are working directly inside the repository.

First inspect the Git history and actual code changes. In particular,
use the equivalent of:

    git log {previous_tag}..HEAD
    git diff {previous_tag}..HEAD

Inspect relevant changed files when necessary to understand the
behavioral impact of the changes.

Requirements:

- Analyze the actual changes rather than simply copying commit messages.
- Group changes into meaningful categories.
- Identify user-visible features and improvements.
- Identify bug fixes.
- Identify breaking changes separately when applicable.
- Mention important internal/engineering changes when they are
  relevant to maintainers or the release.
- Ignore insignificant formatting-only changes.
- Do not invent functionality or behavior that is not supported by
  the repository history and code.
- Do not include commits that are outside the range
  {previous_tag}..HEAD.
- Use concise, professional Markdown.
- Do not include a version heading; the caller will provide it.
- Output only the final Markdown changelog content.
"""

    result = subprocess.run(
        [
            "kilo",
            "run",
            "--auto",
            prompt,
        ],
        cwd=repo,
        check=True,
        text=True,
    )

    return result.stdout.strip()


def main() -> None:
    check_requirements()
    repo = Path.cwd()

    if not (repo / ".git").exists():
        raise RuntimeError(f"{repo} is not a Git repository.")

    ensure_kilo_cli()

    previous_tag = get_previous_release_tag(repo)

    print(f"Generating changelog: {previous_tag}..HEAD")

    changelog = generate_changelog(
        repo=repo,
        previous_tag=previous_tag,
    )

    if not changelog:
        raise RuntimeError("Kilo returned an empty changelog.")

    print()
    print(changelog)


if __name__ == "__main__":
    main()
