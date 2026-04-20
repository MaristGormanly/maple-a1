from __future__ import annotations

import contextlib
import fcntl
import hashlib
import json
import os
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class RepositoryCacheError(Exception):
    """Raised when repository cache metadata cannot be read or written safely."""


@dataclass(frozen=True)
class RubricFingerprint:
    digest: str
    normalization_method: str


@dataclass(frozen=True)
class RepositoryCacheKey:
    value: str
    path_token: str
    commit_hash: str
    rubric_digest: str


@dataclass(frozen=True)
class RepositoryCacheEntry:
    cache_key: str
    path_token: str
    assignment_id: str | None
    rubric_digest: str
    rubric_normalization_method: str
    commit_hash: str
    full_repo_name: str
    local_repo_path: str
    created_at: str
    last_used_at: str


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def fingerprint_rubric_content(rubric_content: Any) -> RubricFingerprint:
    normalized_content, normalization_method = _normalize_rubric_content(rubric_content)
    digest = hashlib.sha256(normalized_content.encode("utf-8")).hexdigest()
    return RubricFingerprint(
        digest=digest,
        normalization_method=normalization_method,
    )


def build_repository_cache_key(commit_hash: str, rubric_digest: str) -> RepositoryCacheKey:
    normalized_commit_hash = commit_hash.strip()
    normalized_rubric_digest = rubric_digest.strip()
    if not normalized_commit_hash or not normalized_rubric_digest:
        raise RepositoryCacheError(
            "commit_hash and rubric_digest are required to build a cache key."
        )

    value = f"{normalized_commit_hash}::{normalized_rubric_digest}"
    path_token = hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]
    return RepositoryCacheKey(
        value=value,
        path_token=path_token,
        commit_hash=normalized_commit_hash,
        rubric_digest=normalized_rubric_digest,
    )


@contextlib.contextmanager
def _exclusive_lock(index_path: Path):
    lock_path = index_path.with_suffix(".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with open(lock_path, "w") as _lf:
        fcntl.flock(_lf, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(_lf, fcntl.LOCK_UN)


def load_repository_cache_entry(
    index_path: Path,
    project_root: Path,
    cache_key: str,
) -> RepositoryCacheEntry | None:
    with _exclusive_lock(index_path):
        index = _load_cache_index(index_path)
        payload = index["entries"].get(cache_key)
        if payload is None:
            return None

        entry = RepositoryCacheEntry(**payload)
        cached_repo_path = project_root / entry.local_repo_path
        if not cached_repo_path.exists() or not cached_repo_path.is_dir():
            del index["entries"][cache_key]
            _write_cache_index(index_path, index)
            return None

        refreshed_payload = {**payload, "last_used_at": _utcnow_iso()}
        index["entries"][cache_key] = refreshed_payload
        _write_cache_index(index_path, index)
        return RepositoryCacheEntry(**refreshed_payload)


def save_repository_cache_entry(index_path: Path, entry: RepositoryCacheEntry) -> None:
    with _exclusive_lock(index_path):
        index = _load_cache_index(index_path)
        index["entries"][entry.cache_key] = asdict(entry)
        _write_cache_index(index_path, index)


def create_repository_cache_entry(
    *,
    cache_key: RepositoryCacheKey,
    assignment_id: str | None,
    rubric_fingerprint: RubricFingerprint,
    full_repo_name: str,
    local_repo_path: Path,
    project_root: Path,
) -> RepositoryCacheEntry:
    timestamp = _utcnow_iso()
    return RepositoryCacheEntry(
        cache_key=cache_key.value,
        path_token=cache_key.path_token,
        assignment_id=assignment_id,
        rubric_digest=rubric_fingerprint.digest,
        rubric_normalization_method=rubric_fingerprint.normalization_method,
        commit_hash=cache_key.commit_hash,
        full_repo_name=full_repo_name,
        local_repo_path=str(local_repo_path.relative_to(project_root)),
        created_at=timestamp,
        last_used_at=timestamp,
    )


def _load_cache_index(index_path: Path) -> dict[str, dict[str, object]]:
    if not index_path.exists():
        return {"entries": {}}

    try:
        raw_payload = json.loads(index_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RepositoryCacheError("Repository cache index could not be read.") from exc

    entries = raw_payload.get("entries", {})
    if not isinstance(entries, dict):
        raise RepositoryCacheError("Repository cache index is malformed.")

    return {"entries": entries}
def _write_cache_index(index_path: Path, payload: dict[str, dict[str, object]]) -> None:
    try:
        index_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = index_path.with_suffix(".tmp")
        tmp_path.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        os.replace(tmp_path, index_path)
    except OSError as exc:
        raise RepositoryCacheError("Repository cache index could not be written.") from exc


def _normalize_rubric_content(rubric_content: Any) -> tuple[str, str]:
    if isinstance(rubric_content, str):
        normalized_text = re.sub(r"\s+", " ", rubric_content).strip()
        if not normalized_text:
            raise RepositoryCacheError("rubric must be a non-empty string, object, or array.")
        return normalized_text, "text_whitespace_canonicalization"

    if isinstance(rubric_content, (dict, list)):
        canonical_payload = _canonicalize_rubric_value(rubric_content)
        if canonical_payload in ({}, []):
            raise RepositoryCacheError("rubric must be a non-empty string, object, or array.")
        try:
            normalized_json = json.dumps(
                canonical_payload,
                ensure_ascii=True,
                separators=(",", ":"),
                sort_keys=True,
            )
        except (TypeError, ValueError) as exc:
            raise RepositoryCacheError(
                "rubric must be JSON-serializable for normalization."
            ) from exc
        return normalized_json, "json_canonicalization"

    raise RepositoryCacheError("rubric must be a non-empty string, object, or array.")


def _canonicalize_rubric_value(value: Any) -> Any:
    if isinstance(value, str):
        return re.sub(r"\s+", " ", value).strip()

    if isinstance(value, list):
        return [_canonicalize_rubric_value(item) for item in value]

    if isinstance(value, dict):
        return {
            str(key): _canonicalize_rubric_value(nested_value)
            for key, nested_value in sorted(value.items(), key=lambda item: str(item[0]))
        }

    if value is None or isinstance(value, (bool, int, float)):
        return value

    raise RepositoryCacheError("rubric must be JSON-serializable for normalization.")
