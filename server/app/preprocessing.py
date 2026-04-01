from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path


STRIP_DIRECTORY_NAMES = {
    ".git",
    "node_modules",
    "venv",
    ".venv",
    "__pycache__",
}

COMPILED_BINARY_SUFFIXES = {
    ".a",
    ".class",
    ".dll",
    ".dylib",
    ".exe",
    ".jar",
    ".lib",
    ".nar",
    ".o",
    ".obj",
    ".pyc",
    ".pyd",
    ".pyo",
    ".so",
    ".war",
}


class RepositoryPreprocessingError(Exception):
    """Raised when repository preprocessing cannot complete safely."""


@dataclass(frozen=True)
class PreprocessingSummary:
    removed_directories: tuple[str, ...]
    removed_files: tuple[str, ...]


def _remove_directory_tree(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink(missing_ok=True)
        return
    shutil.rmtree(path, ignore_errors=False)


def preprocess_repository(repository_path: Path) -> PreprocessingSummary:
    if not repository_path.exists() or not repository_path.is_dir():
        raise RepositoryPreprocessingError(
            "Repository preprocessing could not start because the local clone path is invalid."
        )

    removed_directories: list[str] = []
    removed_files: list[str] = []

    try:
        for current_root, dirnames, filenames in os.walk(repository_path, topdown=True):
            current_root_path = Path(current_root)
            removable_dirnames = [dirname for dirname in dirnames if dirname in STRIP_DIRECTORY_NAMES]
            dirnames[:] = [dirname for dirname in dirnames if dirname not in STRIP_DIRECTORY_NAMES]

            for dirname in removable_dirnames:
                target_directory = current_root_path / dirname
                _remove_directory_tree(target_directory)
                removed_directories.append(target_directory.relative_to(repository_path).as_posix())

            for filename in filenames:
                if Path(filename).suffix.lower() in COMPILED_BINARY_SUFFIXES:
                    target_file = current_root_path / filename
                    target_file.unlink(missing_ok=True)
                    removed_files.append(target_file.relative_to(repository_path).as_posix())
    except OSError as exc:
        raise RepositoryPreprocessingError(
            "Repository preprocessing failed while stripping ignored directories or compiled artifacts."
        ) from exc

    return PreprocessingSummary(
        removed_directories=tuple(sorted(removed_directories)),
        removed_files=tuple(sorted(removed_files)),
    )
