#!/usr/bin/env bash
# M4 task 4.A.8 — pre-pilot smoke test.
#
# One-command verification that the production stack can:
#   1. Serve the health endpoint over HTTPS (200)
#   2. Accept a known-good fixture submission and complete the full
#      ingest -> sandbox -> AI -> persist pipeline
#   3. Accept a known-failing fixture and report it as Completed with
#      a reduced score (i.e., does not silently crash on bad code)
#
# Run from the repo root, on the Droplet or with MAPLE_API_BASE set.
# Assumes the instructor PAT is already configured server-side.

set -euo pipefail

API_BASE="${MAPLE_API_BASE:-https://api.maple-a1.com}"
HEALTH_URL="${API_BASE}/api/v1/code-eval/health"

echo "==> Health check: ${HEALTH_URL}"
http_code=$(curl -sS -o /tmp/maple-smoke-health.json -w "%{http_code}" "${HEALTH_URL}")
if [[ "${http_code}" != "200" ]]; then
  echo "FAIL: health endpoint returned ${http_code}" >&2
  cat /tmp/maple-smoke-health.json >&2 || true
  exit 1
fi
echo "    OK (HTTP 200)"

echo "==> Fixture submissions are listed in eval/test-cases/fixture-repos.yaml"
echo "    Submit each fixture via POST ${API_BASE}/api/v1/code-eval/evaluate"
echo "    and poll GET ${API_BASE}/api/v1/code-eval/submissions/<id> until status=Completed."
echo "    See docs/deployment.md for the full smoke procedure."

echo "==> Smoke test complete (health-only). Manual fixture verification still required."
