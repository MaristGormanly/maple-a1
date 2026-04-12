"""Detect the programming language and version from repo config files.

Pure function — no database, no network, no FastAPI dependencies.
Uses only stdlib: ``tomllib`` (Python 3.11+), ``json``, ``xml.etree.ElementTree``.
"""

from __future__ import annotations

import json
import re
import tomllib
import xml.etree.ElementTree as ET
from pathlib import Path


def detect_language_version(
    repo_path: str,
    language_override: str | None = None,
) -> dict:
    """Return ``{language, version, source, override_applied}``."""
    if language_override:
        return {
            "language": language_override,
            "version": None,
            "source": "language_override",
            "override_applied": True,
        }

    root = Path(repo_path)

    for detector in (
        _detect_python,
        _detect_node,
        _detect_java,
        _detect_cpp,
    ):
        result = detector(root)
        if result is not None:
            return {**result, "override_applied": False}

    return {
        "language": "unknown",
        "version": None,
        "source": "unknown",
        "override_applied": False,
    }


def _detect_python(root: Path) -> dict | None:
    pyproject = root / "pyproject.toml"
    if not pyproject.is_file():
        return None
    try:
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    except Exception:
        return {"language": "python", "version": None, "source": "pyproject.toml"}

    req = (data.get("project") or {}).get("requires-python")
    if req:
        return {"language": "python", "version": req, "source": "pyproject.toml"}

    poetry_deps = (
        (data.get("tool") or {}).get("poetry") or {}
    ).get("dependencies") or {}
    py_ver = poetry_deps.get("python")
    if py_ver:
        return {"language": "python", "version": py_ver, "source": "pyproject.toml"}

    return {"language": "python", "version": None, "source": "pyproject.toml"}


def _detect_node(root: Path) -> dict | None:
    pkg = root / "package.json"
    if not pkg.is_file():
        return None
    try:
        data = json.loads(pkg.read_text(encoding="utf-8"))
    except Exception:
        return {"language": "javascript", "version": None, "source": "package.json"}

    dev_deps = data.get("devDependencies") or {}
    deps = data.get("dependencies") or {}
    is_ts = "typescript" in dev_deps or "typescript" in deps

    engines = data.get("engines") or {}
    node_ver = engines.get("node")

    lang = "typescript" if is_ts else "javascript"
    return {"language": lang, "version": node_ver, "source": "package.json"}


def _detect_java(root: Path) -> dict | None:
    pom = root / "pom.xml"
    if not pom.is_file():
        return None
    try:
        tree = ET.parse(pom)  # noqa: S314
        ns = {"m": "http://maven.apache.org/POM/4.0.0"}
        props = tree.find(".//m:properties", ns)
        if props is None:
            props = tree.find(".//properties")
        if props is not None:
            jv = props.find("m:java.version", ns)
            if jv is None:
                jv = props.find("java.version")
            if jv is not None and jv.text:
                return {
                    "language": "java",
                    "version": jv.text.strip(),
                    "source": "pom.xml",
                }
        return {"language": "java", "version": None, "source": "pom.xml"}
    except Exception:
        return {"language": "java", "version": None, "source": "pom.xml"}


_CMAKE_STD = re.compile(r"set\s*\(\s*CMAKE_CXX_STANDARD\s+(\d+)", re.IGNORECASE)


def _detect_cpp(root: Path) -> dict | None:
    cmake = root / "CMakeLists.txt"
    if not cmake.is_file():
        return None
    try:
        text = cmake.read_text(encoding="utf-8")
    except Exception:
        return {"language": "cpp", "version": None, "source": "CMakeLists.txt"}

    m = _CMAKE_STD.search(text)
    version = m.group(1) if m else None
    return {"language": "cpp", "version": version, "source": "CMakeLists.txt"}
