# API Specification

## `POST /api/v1/code-eval/evaluate`

Accepts a GitHub repository URL and a rubric file for ingestion and submission creation.

- Content type: `multipart/form-data`
- Authentication: Bearer JWT required

### Request fields

| Field | Type | Required | Notes |
| :--- | :--- | :--- | :--- |
| `github_url` | string | Yes | Must be an `https://github.com/<owner>/<repo>` or `https://www.github.com/<owner>/<repo>` URL |
| `assignment_id` | string | Yes | Must be a valid UUID for an existing assignment |
| `rubric` | file upload | Yes | UTF-8 text or JSON file containing the rubric content |

### Example request

```bash
curl -X POST "http://localhost:8000/api/v1/code-eval/evaluate" \
  -H "Authorization: Bearer <jwt>" \
  -F "github_url=https://github.com/student/example-assignment" \
  -F "assignment_id=11111111-2222-3333-4444-555555555555" \
  -F "rubric=@rubric.json;type=application/json"
```

### Success response

```json
{
  "success": true,
  "data": {
    "submission_id": "b2b9f3fd-b1a5-42af-91ea-0c9852f573bc",
    "github_url": "https://github.com/student/example-assignment",
    "assignment_id": "11111111-2222-3333-4444-555555555555",
    "rubric_digest": "671645837593b2bf77542e91add6f3bcb47919cf6218a7697220cccac81195b4",
    "status": "cloned",
    "local_repo_path": "data/raw/student-example-assignment-abc123-1a2b3c4d",
    "commit_hash": "abc123def456"
  },
  "error": null,
  "metadata": {
    "timestamp": "2026-04-01T12:00:00Z",
    "module": "a1",
    "version": "1.0.0"
  }
}
```

### Validation notes

- `github_url` is accepted.
- `rubric` is accepted as a file upload.
- Requests sent as JSON instead of `multipart/form-data` will be rejected by the endpoint.
- The API returns MAPLE-formatted validation errors for malformed URLs, invalid assignment IDs, missing assignments, or invalid rubric encoding.