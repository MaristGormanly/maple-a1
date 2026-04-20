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

export type ScoreLevel =
  | 'Exemplary'
  | 'Proficient'
  | 'Developing'
  | 'Beginning'
  | 'NEEDS_HUMAN_REVIEW';

export interface RecommendationObject {
  file_path: string;
  line_range: { start: number; end: number };
  original_snippet: string;
  revised_snippet: string;
  diff: string;
  rationale?: string;
}

export interface CriterionScore {
  criterion_name: string;
  score: number;
  level: ScoreLevel;
  justification: string;
  confidence: number;
  recommendation?: RecommendationObject;
}

export interface AiFeedback {
  criteria_scores: CriterionScore[];
  flags: string[];
  metadata: {
    style_guide_version?: string | string[];
    language?: string;
  };
  recommendations: RecommendationObject[];
}

export interface EvaluationResult {
  deterministic_score: number | null;
  review_status?: string;
  ai_feedback?: AiFeedback | null;
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

export interface ReviewRequest {
  action: 'approve' | 'reject';
  instructor_notes?: string;
}
