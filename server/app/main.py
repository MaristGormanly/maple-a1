import asyncio
import json
import logging
import os
import re
import shutil
import sys
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote
from uuid import UUID, uuid4

logger = logging.getLogger(__name__)

import httpx
from fastapi import Depends, FastAPI, File, Form, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, HttpUrl, TypeAdapter, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from .cache import (
    RepositoryCacheError,
    build_repository_cache_key,
    create_repository_cache_entry,
    fingerprint_rubric_content,
    load_repository_cache_entry,
    save_repository_cache_entry,
)

from .config import get_required_github_pat, settings
from .middleware.auth import get_current_user
from .middleware.rate_limit import install_rate_limiting, limiter
from .models.database import get_db
from .preprocessing import RepositoryPreprocessingError, preprocess_repository
from .routers import assignments, auth, rubrics, submissions
from .services.assignments import parse_assignment_id, validate_assignment_exists
from .services.git_ingest import CloneError, clone_repository
from .services.llm import redact
from .services.pipeline import run_pipeline
# region agent log
from .services._debug_log import dlog as _dlog  # debug session d6fd1e
# endregion
from .services.submissions import create_submission, recover_orphaned_submissions
from .utils.responses import error_response, success_response

APP_VERSION = "1.0.0"
_url_adapter = TypeAdapter(HttpUrl)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_REPOS_ROOT = PROJECT_ROOT / "data" / "raw"
CACHE_INDEX_PATH = PROJECT_ROOT / "data" / "cache" / "repository-cache-index.json"


class MapleAPIError(Exception):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        super().__init__(message)


def sanitize_clone_path_segment(value: str) -> str:
    sanitized = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip().lower())
    sanitized = sanitized.strip("._-")
    if not sanitized:
        raise ValueError("Repository path contains an invalid empty segment.")
    return sanitized


def determine_raw_clone_path(full_repo_name: str, commit_hash: str, cache_path_token: str) -> Path:
    owner, repo_name = full_repo_name.split("/", 1)
    raw_clone_path = RAW_REPOS_ROOT / (
        f"{sanitize_clone_path_segment(owner)}-"
        f"{sanitize_clone_path_segment(repo_name)}-"
        f"{commit_hash[:12].lower()}-"
        f"{cache_path_token[:8].lower()}"
    )
    RAW_REPOS_ROOT.mkdir(parents=True, exist_ok=True)
    return raw_clone_path


def create_staging_clone_path(full_repo_name: str) -> Path:
    owner, repo_name = full_repo_name.split("/", 1)
    staging_path = RAW_REPOS_ROOT / (
        f"{sanitize_clone_path_segment(owner)}-"
        f"{sanitize_clone_path_segment(repo_name)}-"
        f"staging-{uuid4().hex[:8]}"
    )
    RAW_REPOS_ROOT.mkdir(parents=True, exist_ok=True)
    return staging_path


def parse_github_repo_url(url: HttpUrl) -> tuple[str, str]:
    if url.scheme != "https":
        raise ValueError("github_url must use https://")

    if url.host not in {"github.com", "www.github.com"}:
        raise ValueError("github_url must point to github.com")

    path_parts = [part for part in url.path.split("/") if part]
    if len(path_parts) < 2:
        raise ValueError(
            "github_url must be a repository URL in the form https://github.com/<owner>/<repo>"
        )

    owner, repo_name = path_parts[0], path_parts[1]
    if repo_name.endswith(".git"):
        repo_name = repo_name[:-4]

    if not owner or not repo_name:
        raise ValueError("github_url must include both an owner and repository name")

    return owner, repo_name


class SubmissionData(BaseModel):
    submission_id: str
    github_url: str
    assignment_id: str | None
    rubric_digest: str
    status: str
    local_repo_path: str
    commit_hash: str


class GitHubRepoMetadata(BaseModel):
    full_name: str
    default_branch: str
    visibility: str
    clone_url: str


class ResponseMetadata(BaseModel):
    timestamp: str
    module: str
    version: str


class ErrorDetails(BaseModel):
    code: str
    message: str


class SubmissionResponse(BaseModel):
    success: bool
    data: SubmissionData
    error: None = None
    metadata: ResponseMetadata


def build_response_metadata() -> ResponseMetadata:
    return ResponseMetadata(
        timestamp=datetime.now(timezone.utc).isoformat(),
        module="a1",
        version=APP_VERSION,
    )


def build_error_response(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "success": False,
            "data": None,
            "error": ErrorDetails(code=code, message=message).model_dump(),
            "metadata": build_response_metadata().model_dump(),
        },
    )


async def validate_github_repo_access(
    owner: str, repo_name: str, github_pat: str
) -> GitHubRepoMetadata:
    headers = {
        "Authorization": f"Bearer {github_pat}",
        "Accept": "application/vnd.github+json",
    }
    github_api_url = f"https://api.github.com/repos/{owner}/{repo_name}"

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.get(github_api_url, headers=headers)
        except httpx.HTTPError as exc:
            # region agent log
            _dlog(
                location="main.py:validate_github_repo_access:http_error",
                hypothesis_id="G1",
                message="GitHub repo validation request failed before response",
                data={
                    "owner": owner,
                    "repo_name": repo_name,
                    "exc_type": type(exc).__name__,
                    "exc_str": str(exc)[:300],
                },
            )
            # endregion
            raise MapleAPIError(
                status_code=502,
                code="EXTERNAL_SERVICE_ERROR",
                message="Unable to reach the GitHub API to validate repository access.",
            ) from exc

    # region agent log
    _dlog(
        location="main.py:validate_github_repo_access:response",
        hypothesis_id="G1,G2",
        message="GitHub repo validation response received",
        data={
            "owner": owner,
            "repo_name": repo_name,
            "status_code": response.status_code,
            "rate_limit_remaining": response.headers.get("X-RateLimit-Remaining"),
            "rate_limit_reset": response.headers.get("X-RateLimit-Reset"),
            "response_preview": response.text[:200],
        },
    )
    # endregion

    if response.status_code == 401:
        raise MapleAPIError(
            status_code=401,
            code="AUTHENTICATION_ERROR",
            message="GITHUB_PAT is invalid or expired.",
        )

    if response.status_code == 403:
        if response.headers.get("X-RateLimit-Remaining") == "0":
            raise MapleAPIError(
                status_code=503,
                code="EXTERNAL_SERVICE_ERROR",
                message="GitHub API rate limit exceeded while validating repository access.",
            )

        raise MapleAPIError(
            status_code=400,
            code="VALIDATION_ERROR",
            message="Repository not found or inaccessible with the current GITHUB_PAT.",
        )

    if response.status_code == 404:
        raise MapleAPIError(
            status_code=400,
            code="VALIDATION_ERROR",
            message="Repository not found or inaccessible with the current GITHUB_PAT.",
        )

    if response.status_code != 200:
        raise MapleAPIError(
            status_code=502,
            code="EXTERNAL_SERVICE_ERROR",
            message="GitHub API returned an unexpected response while validating repository access.",
        )

    payload = response.json()
    return GitHubRepoMetadata(
        full_name=payload["full_name"],
        default_branch=payload["default_branch"],
        visibility=payload["visibility"],
        clone_url=payload["clone_url"],
    )


async def resolve_repository_head_commit_hash(
    owner: str, repo_name: str, branch_name: str, github_pat: str
) -> str:
    headers = {
        "Authorization": f"Bearer {github_pat}",
        "Accept": "application/vnd.github+json",
    }
    encoded_branch_name = quote(branch_name, safe="")
    github_api_url = f"https://api.github.com/repos/{owner}/{repo_name}/commits/{encoded_branch_name}"

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.get(github_api_url, headers=headers)
        except httpx.HTTPError as exc:
            # region agent log
            _dlog(
                location="main.py:resolve_repository_head_commit_hash:http_error",
                hypothesis_id="G3",
                message="GitHub commit resolution request failed before response",
                data={
                    "owner": owner,
                    "repo_name": repo_name,
                    "branch_name": branch_name,
                    "exc_type": type(exc).__name__,
                    "exc_str": str(exc)[:300],
                },
            )
            # endregion
            raise MapleAPIError(
                status_code=502,
                code="EXTERNAL_SERVICE_ERROR",
                message="Unable to resolve the repository commit SHA from the GitHub API.",
            ) from exc

    # region agent log
    _dlog(
        location="main.py:resolve_repository_head_commit_hash:response",
        hypothesis_id="G3,G4",
        message="GitHub commit resolution response received",
        data={
            "owner": owner,
            "repo_name": repo_name,
            "branch_name": branch_name,
            "status_code": response.status_code,
            "rate_limit_remaining": response.headers.get("X-RateLimit-Remaining"),
            "rate_limit_reset": response.headers.get("X-RateLimit-Reset"),
            "response_preview": response.text[:200],
        },
    )
    # endregion

    if response.status_code == 401:
        raise MapleAPIError(
            status_code=401,
            code="AUTHENTICATION_ERROR",
            message="GITHUB_PAT is invalid or expired.",
        )

    if response.status_code in {403, 404}:
        raise MapleAPIError(
            status_code=400,
            code="VALIDATION_ERROR",
            message="Repository commit SHA could not be resolved for the current default branch.",
        )

    if response.status_code != 200:
        raise MapleAPIError(
            status_code=502,
            code="EXTERNAL_SERVICE_ERROR",
            message="GitHub API returned an unexpected response while resolving the repository commit SHA.",
        )

    payload = response.json()
    commit_hash = payload.get("sha", "").strip()
    if not commit_hash:
        raise MapleAPIError(
            status_code=502,
            code="EXTERNAL_SERVICE_ERROR",
            message="GitHub API returned an empty commit SHA for the repository.",
        )

    return commit_hash


@asynccontextmanager
async def lifespan(_app: FastAPI):
    count = await recover_orphaned_submissions()
    if count:
        logger.warning(
            "startup: recovered %d orphaned submission(s) stuck in Testing/Evaluating → Failed",
            count,
        )
    yield


app = FastAPI(
    title="MAPLE A1 Code Evaluator",
    description="Automated code evaluation system for Marist College",
    version=APP_VERSION,
    docs_url="/api/v1/code-eval/docs",
    openapi_url="/api/v1/code-eval/openapi.json",
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limiting (30/min default per IP; /evaluate tightens to 5/min below)
install_rate_limiting(
    app,
    test_env=(
        settings.APP_ENV == "test"
        or "PYTEST_CURRENT_TEST" in os.environ
        or "pytest" in sys.modules
    ),
)

# Include routers
app.include_router(auth.router, prefix="/api/v1/code-eval")
app.include_router(assignments.router, prefix="/api/v1/code-eval")
app.include_router(rubrics.router, prefix="/api/v1/code-eval")
app.include_router(submissions.router, prefix="/api/v1/code-eval")

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    details = "; ".join(
        f"{'.'.join(str(loc) for loc in e['loc'])}: {e['msg']}" for e in exc.errors()
    )
    return error_response(
        status_code=400,
        code="VALIDATION_ERROR",
        message=details,
    )


@app.exception_handler(MapleAPIError)
async def handle_maple_api_error(_request: Request, exc: MapleAPIError) -> JSONResponse:
    # region agent log
    _dlog(
        location="main.py:handle_maple_api_error",
        hypothesis_id="H1,H2,H3",
        message="MapleAPIError converted to HTTP response",
        data={
            "path": str(_request.url.path),
            "status_code": exc.status_code,
            "code": exc.code,
            "message": exc.message,
        },
    )
    # endregion
    return build_error_response(exc.status_code, exc.code, exc.message)


@app.post("/api/v1/code-eval/evaluate", response_model=SubmissionResponse)
@limiter.limit("5/minute")
async def evaluate_submission(
    request: Request,
    github_url: str = Form(...),
    assignment_id: str | None = Form(default=None),
    rubric: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SubmissionResponse:
    # region agent log
    _dlog(
        location="main.py:evaluate_submission:entry",
        hypothesis_id="H1,H2,H3",
        message="evaluate_submission entered",
        data={
            "github_url": github_url,
            "assignment_id": assignment_id,
            "rubric_filename": getattr(rubric, "filename", None),
            "user_role": current_user.get("role") if isinstance(current_user, dict) else None,
        },
    )
    # endregion
    try:
        validated_url = _url_adapter.validate_python(github_url)
    except ValidationError:
        raise MapleAPIError(
            status_code=400,
            code="VALIDATION_ERROR",
            message="github_url must be a valid URL.",
        )
    try:
        repo_owner, repo_name = parse_github_repo_url(validated_url)
    except ValueError as exc:
        raise MapleAPIError(
            status_code=400,
            code="VALIDATION_ERROR",
            message=str(exc),
        ) from exc

    rubric_bytes = await rubric.read()
    try:
        rubric_text = rubric_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise MapleAPIError(
            status_code=400,
            code="VALIDATION_ERROR",
            message="Rubric file must be UTF-8 encoded text or JSON.",
        ) from exc
    try:
        rubric_content: dict[str, Any] | list[Any] | str = json.loads(rubric_text)
    except json.JSONDecodeError:
        rubric_content = rubric_text

    try:
        rubric_fingerprint = fingerprint_rubric_content(rubric_content)
    except RepositoryCacheError as exc:
        raise MapleAPIError(
            status_code=400,
            code="VALIDATION_ERROR",
            message=str(exc),
        ) from exc

    try:
        student_id = UUID(current_user["sub"])
    except (ValueError, KeyError):
        raise MapleAPIError(
            status_code=401,
            code="AUTH_ERROR",
            message="Invalid user identity in token.",
        )

    parsed_assignment_id: UUID | None = None
    if assignment_id:
        try:
            parsed_assignment_id = parse_assignment_id(assignment_id)
        except ValueError:
            raise MapleAPIError(
                status_code=400,
                code="VALIDATION_ERROR",
                message="assignment_id must be a valid UUID.",
            )
        try:
            await validate_assignment_exists(db, parsed_assignment_id)
        except ValueError:
            raise MapleAPIError(
                status_code=404,
                code="NOT_FOUND",
                message=f"Assignment '{assignment_id}' does not exist.",
            )

    try:
        github_pat = get_required_github_pat()
    except RuntimeError as exc:
        raise MapleAPIError(
            status_code=500,
            code="CONFIGURATION_ERROR",
            message=str(exc),
        ) from exc

    repo_metadata = await validate_github_repo_access(repo_owner, repo_name, github_pat)
    resolved_commit_hash = await resolve_repository_head_commit_hash(
        repo_owner,
        repo_name,
        repo_metadata.default_branch,
        github_pat,
    )
    cache_key = build_repository_cache_key(resolved_commit_hash, rubric_fingerprint.digest)

    try:
        cached_entry = load_repository_cache_entry(CACHE_INDEX_PATH, PROJECT_ROOT, cache_key.value)
    except RepositoryCacheError as exc:
        raise MapleAPIError(
            status_code=500,
            code="CACHE_ERROR",
            message=str(exc),
        ) from exc

    if cached_entry is not None:
        submission = await create_submission(
            db,
            assignment_id=parsed_assignment_id,
            student_id=student_id,
            github_repo_url=str(validated_url),
            commit_hash=cached_entry.commit_hash,
            status="Pending" if parsed_assignment_id is not None else "cached",
        )
        # region agent log
        _dlog(
            location="main.py:evaluate_submission:cache_hit",
            hypothesis_id="F",
            message="cache hit — pipeline scheduled if assignment present",
            data={
                "submission_id": str(submission.id),
                "assignment_id": str(parsed_assignment_id) if parsed_assignment_id else None,
                "commit_hash": cached_entry.commit_hash,
                "schedule_pipeline": parsed_assignment_id is not None,
            },
        )
        # endregion
        if parsed_assignment_id is not None:
            student_abs = str(
                (PROJECT_ROOT / Path(cached_entry.local_repo_path)).resolve()
            )
            asyncio.create_task(
                run_pipeline(
                    submission.id,
                    parsed_assignment_id,
                    student_abs,
                    rubric_content,
                    github_pat,
                )
            )
        response_status = "Pending" if parsed_assignment_id is not None else "cached"
        return SubmissionResponse(
            success=True,
            data=SubmissionData(
                submission_id=str(submission.id),
                github_url=github_url,
                assignment_id=assignment_id,
                rubric_digest=rubric_fingerprint.digest,
                status=response_status,
                local_repo_path=cached_entry.local_repo_path,
                commit_hash=cached_entry.commit_hash,
            ),
            metadata=build_response_metadata(),
        )

    staging_clone_path = create_staging_clone_path(repo_metadata.full_name)

    try:
        commit_hash = await clone_repository(repo_metadata.clone_url, staging_clone_path, github_pat)
        preprocess_repository(staging_clone_path)
    except CloneError as exc:
        shutil.rmtree(staging_clone_path, ignore_errors=True)
        raise MapleAPIError(exc.status_code, exc.code, exc.message) from exc
    except RepositoryPreprocessingError as exc:
        shutil.rmtree(staging_clone_path, ignore_errors=True)
        raise MapleAPIError(
            status_code=500,
            code="PREPROCESSING_ERROR",
            message=str(exc),
        ) from exc

    actual_cache_key = build_repository_cache_key(commit_hash, rubric_fingerprint.digest)
    final_repo_path = determine_raw_clone_path(
        repo_metadata.full_name,
        commit_hash,
        actual_cache_key.path_token,
    )

    if final_repo_path.exists():
        shutil.rmtree(staging_clone_path, ignore_errors=True)
    else:
        final_repo_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(staging_clone_path), str(final_repo_path))

    try:
        cache_entry = create_repository_cache_entry(
            cache_key=actual_cache_key,
            assignment_id=assignment_id,
            rubric_fingerprint=rubric_fingerprint,
            full_repo_name=repo_metadata.full_name,
            local_repo_path=final_repo_path,
            project_root=PROJECT_ROOT,
        )
        save_repository_cache_entry(CACHE_INDEX_PATH, cache_entry)
    except RepositoryCacheError as exc:
        raise MapleAPIError(
            status_code=500,
            code="CACHE_ERROR",
            message=str(exc),
        ) from exc

    submission = await create_submission(
        db,
        assignment_id=parsed_assignment_id,
        student_id=student_id,
        github_repo_url=str(validated_url),
        commit_hash=commit_hash,
        status="Pending" if parsed_assignment_id is not None else "cloned",
    )
    # region agent log
    _dlog(
        location="main.py:evaluate_submission:cache_miss",
        hypothesis_id="F",
        message="cache miss — pipeline scheduled if assignment present",
        data={
            "submission_id": str(submission.id),
            "assignment_id": str(parsed_assignment_id) if parsed_assignment_id else None,
            "commit_hash": commit_hash,
            "schedule_pipeline": parsed_assignment_id is not None,
        },
    )
    # endregion
    if parsed_assignment_id is not None:
        asyncio.create_task(
            run_pipeline(
                submission.id,
                parsed_assignment_id,
                str(final_repo_path.resolve()),
                rubric_content,
                github_pat,
            )
        )

    response_status = "Pending" if parsed_assignment_id is not None else "cloned"
    return SubmissionResponse(
        success=True,
        data=SubmissionData(
            submission_id=str(submission.id),
            github_url=github_url,
            assignment_id=assignment_id,
            rubric_digest=rubric_fingerprint.digest,
            status=response_status,
            local_repo_path=str(final_repo_path.relative_to(PROJECT_ROOT)),
            commit_hash=commit_hash,
        ),
        metadata=build_response_metadata(),
    )


@app.get("/api/v1/code-eval/health")
async def health_check():
    return success_response({"status": "ok", "environment": settings.APP_ENV})
