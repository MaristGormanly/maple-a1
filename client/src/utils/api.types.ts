export interface SubmissionData {
  submission_id: string;
  github_url: string;
  assignment_id: string | null;
  rubric_digest: string;
  status: string;
  local_repo_path: string;
  commit_hash: string;
}

export interface TestSummary {
  framework: string;
  passed: number;
  failed: number;
  errors: number;
  skipped: number;
}

export interface LanguageInfo {
  language: string;
  version: string | null;
  source: string | null;
  override_applied: boolean;
}

export interface EvaluationResult {
  deterministic_score: number | null;
  ai_feedback: { summary?: string } | null;
  metadata?: {
    language: LanguageInfo | null;
    test_summary: TestSummary | null;
  };
}

// Shape returned by GET /api/v1/code-eval/submissions/:id
export interface SubmissionStatusData {
  submission_id: string;
  assignment_id: string | null;
  student_id: string;
  github_repo_url: string;
  commit_hash: string | null;
  status: string;
  created_at: string;
  evaluation?: EvaluationResult;
}

export interface SubmissionStatusResponse {
  success: boolean;
  data: SubmissionStatusData | null;
  error: ApiError | null;
  metadata: ResponseMetadata;
}

export interface ResponseMetadata {
  timestamp: string;
  module: string;
  version: string;
}

export interface ApiError {
  code: string;
  message: string;
}

export interface SubmissionResponse {
  success: boolean;
  data: SubmissionData | null;
  error: ApiError | null;
  metadata: ResponseMetadata;
}
