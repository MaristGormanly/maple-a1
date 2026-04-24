"""Rate limiting middleware for MAPLE A1 (M4.A.5).

Defaults every route to 30 requests/minute per client IP. The
/evaluate route is expected to decorate itself with a stricter
5/minute limit to cap LLM cost runaway during a deadline-bunched
pilot (design-doc §7 Risk 3).

Client IP is read from X-Forwarded-For first (production runs behind
Nginx), falling back to the direct socket address. In the test
environment the limiter is installed but disabled so existing tests
are not flaky.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

from app.utils.responses import error_response


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return get_remote_address(request)


limiter = Limiter(
    key_func=_client_ip,
    default_limits=["30/minute"],
    headers_enabled=False,
)


def _rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return error_response(
        status_code=429,
        code="RATE_LIMITED",
        message=f"Rate limit exceeded: {exc.detail}",
    )


def install_rate_limiting(app: FastAPI, *, test_env: bool = False) -> None:
    """Attach the limiter and its 429 handler to a FastAPI app.

    Pass test_env=True to disable enforcement (limiter is still
    installed so @limiter.limit decorators on routes remain valid).
    """
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)
    app.add_middleware(SlowAPIMiddleware)
    limiter.enabled = not test_env
