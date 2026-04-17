"""
Linter execution service for MAPLE A1 — Milestone 3.

Runs pylint (Python) and eslint (JS/TS) statically inside ephemeral Docker
containers, returning structured Violation objects.

Design-doc references:
    - §8 "Run pylint/eslint statically inside the Docker container and capture violations JSON"
    - §3 §II "During the Static Analysis phase, linters (pylint/eslint) identify convention violations"
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from .docker_runner import ContainerConfig, run_container
from .sandbox_images import get_lint_profile

logger = logging.getLogger(__name__)


@dataclass
class Violation:
    """A single linter violation produced by pylint or eslint."""

    file: str
    line: int
    rule_id: str
    severity: str
    message: str


def _parse_violations(language: str, stdout: str) -> list[Violation]:
    """Parse linter JSON output into a list of Violation objects.

    Supports pylint JSON format and eslint JSON format. Returns an empty list
    on JSON parse errors (logged as warnings).
    """
    if not stdout or not stdout.strip():
        return []

    try:
        raw = json.loads(stdout)
    except json.JSONDecodeError as exc:
        logger.warning(
            "linter_parse_error",
            extra={"language": language, "error": str(exc), "stdout_preview": stdout[:200]},
        )
        return []

    violations: list[Violation] = []

    if language == "python":
        # pylint JSON: list of dicts with keys path, line, symbol, type, message
        if not isinstance(raw, list):
            return []
        for item in raw:
            try:
                violations.append(
                    Violation(
                        file=item.get("path", ""),
                        line=int(item.get("line", 0)),
                        rule_id=item.get("symbol", ""),
                        severity=item.get("type", ""),
                        message=item.get("message", ""),
                    )
                )
            except (TypeError, ValueError):
                continue

    elif language in ("javascript", "typescript"):
        # eslint JSON: list of file results, each with filePath and messages list
        if not isinstance(raw, list):
            return []
        severity_map = {1: "warning", 2: "error"}
        for file_result in raw:
            file_path = file_result.get("filePath", "")
            messages = file_result.get("messages", [])
            if not isinstance(messages, list):
                continue
            for msg in messages:
                try:
                    violations.append(
                        Violation(
                            file=file_path,
                            line=int(msg.get("line", 0)),
                            rule_id=msg.get("ruleId") or "",
                            severity=severity_map.get(msg.get("severity"), "warning"),
                            message=msg.get("message", ""),
                        )
                    )
                except (TypeError, ValueError):
                    continue

    return violations


async def run_linter(language: str, repo_host_path: str) -> list[Violation]:
    """Run the appropriate linter for *language* against the repo at *repo_host_path*.

    Returns a (possibly empty) list of Violation objects. Returns an empty list
    without raising if no lint profile exists for the given language.

    Args:
        language: One of "python", "javascript", "typescript" (case-insensitive).
        repo_host_path: Absolute path on the Docker host to the cloned repository.

    Returns:
        List of Violation objects parsed from the linter's JSON output.
    """
    profile = get_lint_profile(language)
    if profile is None:
        logger.warning(
            "linter_no_profile",
            extra={"language": language, "repo_host_path": repo_host_path},
        )
        return []

    config = ContainerConfig(
        image=profile.image,
        command=profile.command,
        volumes={repo_host_path: {"bind": "/workspace", "mode": "ro"}},
        environment={},
        working_dir="/workspace",
        timeout=60,
        network_disabled=True,
        mem_limit="512m",
        cpu_period=100000,
        cpu_quota=50000,
        cap_drop=["ALL"],
        security_opt=["no-new-privileges:true"],
        read_only=True,
        tmpfs={"/tmp": "rw,size=64m"},
    )

    result = await run_container(config)

    violations = _parse_violations(language, result.stdout)

    logger.info(
        json.dumps(
            {
                "event": "linter_run",
                "language": language,
                "violation_count": len(violations),
                "exit_code": result.exit_code,
            }
        )
    )

    return violations
