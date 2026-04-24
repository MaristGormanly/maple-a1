"""Tests for M4.A.5 — rate limiting via slowapi.

Tests target the rate-limit middleware module in isolation against a
minimal FastAPI app so they do not depend on the full /evaluate route's
dependency graph. Coverage:

- Global default limit of 30/minute per IP
- Per-route stricter limit of 5/minute on /evaluate
- Per-IP isolation via X-Forwarded-For (behind Nginx in production)
- 429 response conforms to MAPLE Standard Envelope
- Disabled in test environment so the existing suite is unaffected
"""

import unittest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient


def _make_app(*, test_env: bool = False) -> FastAPI:
    """Build a minimal FastAPI app wired with the rate-limit middleware."""
    from app.middleware.rate_limit import install_rate_limiting, limiter

    app = FastAPI()
    install_rate_limiting(app, test_env=test_env)

    @app.get("/ping")
    async def ping(request: Request):
        return {"ok": True}

    @app.post("/evaluate")
    @limiter.limit("5/minute")
    async def evaluate(request: Request):
        return {"ok": True}

    return app


class RateLimitMiddlewareTests(unittest.TestCase):
    def test_global_rate_limit_30_per_minute(self) -> None:
        app = _make_app()
        client = TestClient(app)
        for i in range(30):
            r = client.get("/ping", headers={"X-Forwarded-For": "10.0.0.1"})
            self.assertEqual(r.status_code, 200, f"Request {i + 1} should succeed")
        r = client.get("/ping", headers={"X-Forwarded-For": "10.0.0.1"})
        self.assertEqual(r.status_code, 429)

    def test_evaluate_endpoint_5_per_minute(self) -> None:
        app = _make_app()
        client = TestClient(app)
        for i in range(5):
            r = client.post("/evaluate", headers={"X-Forwarded-For": "10.0.0.2"})
            self.assertEqual(r.status_code, 200, f"Request {i + 1} should succeed")
        r = client.post("/evaluate", headers={"X-Forwarded-For": "10.0.0.2"})
        self.assertEqual(r.status_code, 429)

    def test_rate_limit_isolated_per_ip(self) -> None:
        app = _make_app()
        client = TestClient(app)
        for _ in range(30):
            r = client.get("/ping", headers={"X-Forwarded-For": "1.1.1.1"})
            self.assertEqual(r.status_code, 200)
        r = client.get("/ping", headers={"X-Forwarded-For": "1.1.1.1"})
        self.assertEqual(r.status_code, 429, "exhausted IP should be limited")
        r = client.get("/ping", headers={"X-Forwarded-For": "2.2.2.2"})
        self.assertEqual(r.status_code, 200, "fresh IP should have its own bucket")

    def test_rate_limit_error_envelope(self) -> None:
        app = _make_app()
        client = TestClient(app)
        for _ in range(30):
            client.get("/ping", headers={"X-Forwarded-For": "3.3.3.3"})
        r = client.get("/ping", headers={"X-Forwarded-For": "3.3.3.3"})
        self.assertEqual(r.status_code, 429)
        body = r.json()
        self.assertFalse(body["success"])
        self.assertIsNone(body["data"])
        self.assertEqual(body["error"]["code"], "RATE_LIMITED")
        self.assertIsInstance(body["error"]["message"], str)
        self.assertIn("metadata", body)
        self.assertEqual(body["metadata"]["module"], "a1")

    def test_rate_limit_disabled_in_test_env(self) -> None:
        app = _make_app(test_env=True)
        client = TestClient(app)
        for i in range(50):
            r = client.get("/ping", headers={"X-Forwarded-For": "4.4.4.4"})
            self.assertEqual(r.status_code, 200, f"Request {i + 1} should not be limited")


if __name__ == "__main__":
    unittest.main()
