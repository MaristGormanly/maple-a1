from datetime import datetime, timezone
from fastapi.responses import JSONResponse


def _build_metadata() -> dict:
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "module": "a1",
        "version": "1.0.0",
    }


def success_response(data: dict) -> dict:
    return {
        "success": True,
        "data": data,
        "error": None,
        "metadata": _build_metadata(),
    }


def error_response(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "success": False,
            "data": None,
            "error": {"code": code, "message": message},
            "metadata": _build_metadata(),
        },
    )
