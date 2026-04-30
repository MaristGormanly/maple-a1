"""Git repository cloning service (extracted from main.py to break circular import).

pipeline.py → git_ingest.py (no upward dependency on main)
main.py     → git_ingest.py (catches CloneError, wraps into MapleAPIError)
"""
from __future__ import annotations

import asyncio
import os
import shutil
from pathlib import Path
from tempfile import NamedTemporaryFile

from .llm import redact


class CloneError(Exception):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        super().__init__(message)


async def clone_repository(clone_url: str, destination_path: Path, github_pat: str) -> str:
    if destination_path.exists() and (
        not destination_path.is_dir() or any(destination_path.iterdir())
    ):
        raise CloneError(
            status_code=409,
            code="CLONE_ERROR",
            message="The local clone path already exists and is not empty. Clear it before retrying.",
        )

    destination_path.parent.mkdir(parents=True, exist_ok=True)

    with NamedTemporaryFile(
        "w", delete=False, prefix="maple-git-askpass-", suffix=".sh"
    ) as askpass_file:
        askpass_file.write(
            "#!/bin/sh\n"
            'case "$1" in\n'
            '  *Username*) printf "%s\\n" "x-access-token" ;;\n'
            '  *Password*) printf "%s\\n" "$MAPLE_GITHUB_PAT" ;;\n'
            '  *) printf "\\n" ;;\n'
            "esac\n"
        )
        askpass_path = Path(askpass_file.name)

    askpass_path.chmod(0o700)

    env = os.environ.copy()
    env.update(
        {
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_ASKPASS": str(askpass_path),
            "MAPLE_GITHUB_PAT": github_pat,
        }
    )

    try:
        process = await asyncio.create_subprocess_exec(
            "git",
            "clone",
            "--depth",
            "1",
            clone_url,
            str(destination_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        _stdout, stderr = await process.communicate()
    except FileNotFoundError as exc:
        raise CloneError(
            status_code=500,
            code="CONFIGURATION_ERROR",
            message="git is not installed on the server.",
        ) from exc
    finally:
        askpass_path.unlink(missing_ok=True)

    if process.returncode != 0:
        if destination_path.exists():
            shutil.rmtree(destination_path, ignore_errors=True)

        sanitized_stderr = redact(
            stderr.decode("utf-8", errors="replace")
        ).replace(github_pat, "[REDACTED]").strip()
        detail = "Repository clone failed."
        if sanitized_stderr:
            detail = f"{detail} {sanitized_stderr}"

        raise CloneError(status_code=502, code="CLONE_ERROR", message=detail)

    try:
        head_process = await asyncio.create_subprocess_exec(
            "git",
            "-C",
            str(destination_path),
            "rev-parse",
            "HEAD",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await head_process.communicate()
    except FileNotFoundError as exc:
        raise CloneError(
            status_code=500,
            code="CONFIGURATION_ERROR",
            message="git is not installed on the server.",
        ) from exc

    if head_process.returncode != 0:
        sanitized_stderr = stderr.decode("utf-8", errors="replace").strip()
        detail = "Repository cloned, but the checked-out commit hash could not be resolved."
        if sanitized_stderr:
            detail = f"{detail} {sanitized_stderr}"

        raise CloneError(status_code=502, code="CLONE_ERROR", message=detail)

    commit_hash = stdout.decode("utf-8", errors="replace").strip()
    if not commit_hash:
        raise CloneError(
            status_code=502,
            code="CLONE_ERROR",
            message="Repository cloned, but the checked-out commit hash was empty.",
        )

    return commit_hash
