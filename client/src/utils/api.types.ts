export interface SubmissionData {
  submission_id: string;
  github_url: string;
  assignment_id: string | null;
  rubric_digest: string;
  status: string;
  local_repo_path: string;
  commit_hash: string;
}

export interface TestCase {
  name: string;
  status: 'passed' | 'failed' | 'error' | 'skipped';
  message: string | null;
}

export interface TestSummary {
  framework: string;
  passed: number;
  failed: number;
  errors: number;
  skipped: number;
  tests?: TestCase[];
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
  instructor_notes?: string | null;
  ai_feedback?: AiFeedback | null;
  metadata?: {
    language: LanguageInfo | null;
    test_summary: TestSummary | null;
  };
}

export interface RubricLevel {
  label: string;
  points: number;
  description: string;
}

export interface RubricCriterion {
  name: string;
  max_points: number;
  levels: RubricLevel[];
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
  rubric_criteria?: RubricCriterion[] | null;
}

export interface SubmissionStatusResponse {
  success: boolean;
  data: SubmissionStatusData | null;
  error: ApiError | null;
  metadata: ResponseMetadata;
}

export interface SubmissionSummary {
  submission_id: string;
  assignment_id: string | null;
  student_id: string;
  student_email: string | null;
  student_name: string | null;
  github_repo_url: string;
  status: string;
  created_at: string;
  deterministic_score: number | null;
  ai_score: number | null;
}

export interface SubmissionListResponse {
  success: boolean;
  data: { submissions: SubmissionSummary[] } | null;
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

export interface AssignmentData {
  assignment_id: string;
  title: string;
  instructor_id: string;
  test_suite_repo_url: string | null;
  rubric_id: string | null;
  enable_lint_review: boolean;
  language_override: string | null;
  submission_count: number;
}

export interface AssignmentListResponse {
  success: boolean;
  data: { assignments: AssignmentData[] } | null;
  error: ApiError | null;
  metadata: ResponseMetadata;
}

export interface AssignmentDetailResponse {
  success: boolean;
  data: AssignmentData | null;
  error: ApiError | null;
  metadata: ResponseMetadata;
}

export interface DeleteResponse {
  success: boolean;
  data: { deleted: string } | null;
  error: ApiError | null;
  metadata: ResponseMetadata;
}
