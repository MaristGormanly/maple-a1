from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from server.app.config import settings
from server.app.routers import auth, rubrics
from server.app.utils.responses import success_response, error_response

app = FastAPI(
    title="MAPLE A1 Code Evaluator",
    description="Automated code evaluation system for Marist College",
    version=APP_VERSION,
    docs_url="/api/v1/code-eval/docs",
    openapi_url="/api/v1/code-eval/openapi.json",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
    return build_error_response(exc.status_code, exc.code, exc.message)


@app.post("/api/v1/code-eval/evaluate", response_model=SubmissionResponse)
async def evaluate_submission(
    github_url: str = Form(...),
    assignment_id: str | None = Form(default=None),
    rubric: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SubmissionResponse:
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
